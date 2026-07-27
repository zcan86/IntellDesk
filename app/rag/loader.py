# -*- coding: utf-8 -*-
"""RAG 文档加载与检索

使用 scikit-learn TF-IDF + 余弦相似度做本地检索：
- 无需下载任何模型，零网络依赖
- 启动瞬时完成
- 对产品文档这类关键词密集文本效果良好

职责：
1. 加载 docs/products/ 下的 Markdown 文档
2. 按标题层级切分
3. 构建 TF-IDF 索引
4. 提供检索接口
"""

import pickle
from pathlib import Path

import numpy as np
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings, PROJECT_ROOT

# ── 全局状态 ──────────────────────────────────────────────────
_chunks: list[dict] = []           # 所有文档块
_vectorizer: TfidfVectorizer | None = None
_tfidf_matrix = None               # 文档 TF-IDF 矩阵
_index_ready: bool = False


def _load_and_split_docs(docs_dir: Path) -> list[dict]:
    """加载目录下所有 .md 文件，按标题 + 字符数两层切分

    Returns:
        [{"content": "...", "metadata": {...}}, ...]
    """
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "h1"),
            ("##", "h2"),
            ("###", "h3"),
        ],
        strip_headers=False,
    )

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,        # 500
        chunk_overlap=settings.CHUNK_OVERLAP,   # 50
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )

    all_chunks = []
    md_files = sorted(docs_dir.glob("*.md"))

    if not md_files:
        logger.warning(f"目录 {docs_dir} 中没有找到 .md 文件")
        return []

    for md_file in md_files:
        logger.info(f"  加载: {md_file.name}")
        text = md_file.read_text(encoding="utf-8")
        md_chunks = md_splitter.split_text(text)

        for chunk in md_chunks:
            sub_chunks = char_splitter.split_text(chunk.page_content)
            for i, sub in enumerate(sub_chunks):
                all_chunks.append({
                    "content": sub,
                    "metadata": {
                        "source": md_file.name,
                        "h1": chunk.metadata.get("h1", ""),
                        "h2": chunk.metadata.get("h2", ""),
                        "h3": chunk.metadata.get("h3", ""),
                        "chunk_index": i,
                    },
                })

    logger.info(f"  文档切分完成: {len(md_files)} 个文件 → {len(all_chunks)} 个块")
    return all_chunks


def build_index(docs_dir: str | None = None, force_rebuild: bool = False) -> bool:
    """构建 TF-IDF 索引

    Args:
        docs_dir: 文档目录，默认 docs/products/
        force_rebuild: 是否强制重建

    Returns:
        True 表示索引构建成功
    """
    global _chunks, _vectorizer, _tfidf_matrix, _index_ready

    if _index_ready and not force_rebuild:
        return True

    if docs_dir is None:
        docs_dir = str(PROJECT_ROOT / "docs" / "products")

    docs_path = Path(docs_dir)
    if not docs_path.exists():
        logger.error(f"文档目录不存在: {docs_dir}")
        return False

    # 1. 加载并切分
    _chunks = _load_and_split_docs(docs_path)
    if not _chunks:
        logger.warning("没有可索引的文档块")
        _index_ready = False
        return False

    # 2. 构建 TF-IDF 向量
    logger.info("  构建 TF-IDF 索引...")
    contents = [c["content"] for c in _chunks]
    _vectorizer = TfidfVectorizer(
        max_features=5000,              # 词汇表上限
        ngram_range=(1, 2),             # 单字 + 双字组合
        analyzer="char_wb",             # 字符级（中英文兼容）
        strip_accents="unicode",
    )
    _tfidf_matrix = _vectorizer.fit_transform(contents)
    _index_ready = True

    logger.info(f"  TF-IDF 索引就绪: {len(_chunks)} 个块, 词汇量 {len(_vectorizer.vocabulary_)}")
    return True


def get_index_status() -> dict:
    """返回索引状态"""
    return {
        "ready": _index_ready,
        "chunk_count": len(_chunks),
        "vocab_size": len(_vectorizer.vocabulary_) if _vectorizer else 0,
    }


def search_knowledge(query: str, top_k: int | None = None) -> list[dict]:
    """TF-IDF + 余弦相似度检索

    Args:
        query: 用户问题
        top_k: 返回数量

    Returns:
        [{"content": "...", "source": "...", "score": 0.85}, ...]
    """
    if not _index_ready or _vectorizer is None:
        return []

    if top_k is None:
        top_k = settings.TOP_K_RETRIEVAL

    try:
        # 查询向量化
        query_vec = _vectorizer.transform([query])

        # 余弦相似度
        scores = cosine_similarity(query_vec, _tfidf_matrix).flatten()

        # Top-K
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < 0.01:  # 过滤完全不相关的结果
                continue
            chunk = _chunks[idx]
            results.append({
                "content": chunk["content"],
                "source": chunk["metadata"].get("source", "unknown"),
                "h1": chunk["metadata"].get("h1", ""),
                "h2": chunk["metadata"].get("h2", ""),
                "score": round(score, 4),
            })

        return results

    except Exception as e:
        logger.error(f"检索失败: {e}")
        return []
