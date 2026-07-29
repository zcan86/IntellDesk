# -*- coding: utf-8 -*-
"""混合检索器：BM25 关键词 + BGE-m3 语义 + RRF 融合

解决单一语义检索的盲区：
- 语义检索擅长理解同义改写（"不花钱"≈"免费"）
- BM25 擅长精确匹配（"API" 不会被同义词干扰）
- RRF 融合两者结果，取长补短
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from loguru import logger

from app.rag.loader import search_knowledge as semantic_search

# ── BM25 实现（基于 TF-IDF，轻量零依赖）─────────────────────

class BM25Retriever:
    """轻量 BM25 检索器

    使用 scikit-learn TfidfVectorizer + 自定义 IDF 修正实现 BM25 评分
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.vectorizer: TfidfVectorizer | None = None
        self.doc_matrix = None
        self.documents: list[str] = []
        self.avg_dl: float = 0

    def fit(self, documents: list[str]):
        """构建 BM25 索引"""
        self.documents = documents
        self.vectorizer = TfidfVectorizer(
            max_features=5000, ngram_range=(1, 2),
            analyzer="char_wb", strip_accents="unicode",
        )
        self.doc_matrix = self.vectorizer.fit_transform(documents)
        # 计算平均文档长度
        doc_lengths = [len(d) for d in documents]
        self.avg_dl = np.mean(doc_lengths) if doc_lengths else 1
        logger.info(f"  BM25 索引: {len(documents)} 文档, 词汇 {len(self.vectorizer.vocabulary_)}")

    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        """BM25 检索，返回 [(doc_index, score), ...]"""
        if self.vectorizer is None or self.doc_matrix is None:
            return []

        query_vec = self.vectorizer.transform([query])
        # TF-IDF 余弦相似度 → 近似 BM25
        from sklearn.metrics.pairwise import cosine_similarity
        scores = cosine_similarity(query_vec, self.doc_matrix).flatten()

        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(int(idx), float(scores[idx])) for idx in top_indices if scores[idx] > 0.001]


# ── 全局 BM25 索引 ──────────────────────────────────────────

_bm25: BM25Retriever | None = None


def init_hybrid_index(documents: list[str]):
    """初始化混合检索索引（启动时调用一次）"""
    global _bm25
    _bm25 = BM25Retriever()
    _bm25.fit(documents)


# ── RRF 融合算法 ────────────────────────────────────────────

def reciprocal_rank_fusion(
    semantic_results: list[dict],
    keyword_results: list[tuple[int, float]],
    bm25_docs: list[str],
    k: int = 60,
) -> list[dict]:
    """RRF (Reciprocal Rank Fusion)

    将语义检索和关键词检索的结果按倒数排名融合。

    公式: RRF(d) = Σ 1/(k + rank_i(d))
    其中 k=60 是经验值，用于平滑排名差异。

    Args:
        semantic_results: 语义检索结果 [{"content":..., "source":..., "score":...}, ...]
        keyword_results: BM25 结果 [(doc_index, score), ...]
        bm25_docs: BM25 索引的文档列表（用于 content 映射）
        k: RRF 平滑参数

    Returns:
        融合后的结果列表
    """
    scores = {}  # content_hash → {"score": float, "data": dict}

    # 语义检索的排名贡献
    for rank, item in enumerate(semantic_results, 1):
        key = item["content"]
        scores[key] = {
            "score": 1.0 / (k + rank),
            "data": item,
            "sem_rank": rank,
            "kw_rank": 999,
        }

    # 关键词检索的排名贡献
    for rank, (doc_idx, _) in enumerate(keyword_results, 1):
        content = bm25_docs[doc_idx] if doc_idx < len(bm25_docs) else ""
        if content in scores:
            scores[content]["score"] += 1.0 / (k + rank)
            scores[content]["kw_rank"] = rank
        else:
            scores[content] = {
                "score": 1.0 / (k + rank),
                "data": {"content": content, "source": "关键词匹配", "h1": "", "h2": "", "score": 0.5},
                "sem_rank": 999,
                "kw_rank": rank,
            }

    # 按 RRF 分数降序排列
    sorted_items = sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    # 更新 score 为融合分数
    results = []
    for item in sorted_items:
        data = item["data"]
        data["score"] = round(item["score"], 4)
        results.append(data)

    return results


# ── 混合检索入口 ─────────────────────────────────────────────

def hybrid_search(query: str, top_k: int = 5) -> list[dict]:
    """混合检索：语义 + 关键词 + RRF 融合

    三步流程:
    1. 语义检索: ChromaDB + BGE-m3 → Top-5
    2. 关键词检索: BM25 → Top-5
    3. RRF 融合: 取排名倒数加权
    """
    # Step 1: 语义检索
    semantic_results = semantic_search(query, top_k=top_k)

    # Step 2: 关键词检索
    keyword_results = []
    bm25_docs = []
    if _bm25 is not None:
        keyword_results = _bm25.search(query, top_k=top_k)
        bm25_docs = _bm25.documents

    # Step 3: RRF 融合
    if keyword_results:
        fused = reciprocal_rank_fusion(semantic_results, keyword_results, bm25_docs)
        logger.debug(
            f"  混合检索: 语义 {len(semantic_results)} + 关键词 {len(keyword_results)}"
            f" → RRF 融合 {len(fused)}"
        )
        return fused[:top_k]

    return semantic_results
