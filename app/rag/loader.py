# -*- coding: utf-8 -*-
"""RAG 文档加载与检索（ChromaDB + 硅基流动 BGE Embedding）

使用 ChromaDB 持久化向量索引 + 硅基流动 BAAI/bge-m3 嵌入 API：
- 语义理解：同义词、近义改写都能匹配
- 1024 维向量，中英双语 SOTA
- 无需下载本地模型，API 调用（免费额度）

职责：
1. 加载 docs/products/ 下的 Markdown 文档
2. 按标题层级切分
3. 调 SiliconFlow API 向量化并存入 ChromaDB
4. 提供语义检索接口
"""

from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from loguru import logger

from app.config import settings, PROJECT_ROOT

# ── 全局单例 ──────────────────────────────────────────────────
_vector_store: Chroma | None = None


def _get_embedding_function():
    """返回硅基流动 BGE 嵌入函数

    BAAI/bge-m3：
    - BGE 系列最强多语言模型，中英文 SOTA
    - 1024 维向量
    - 通过硅基流动 API 调用，无需本地 GPU/下载
    """
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL_NAME,
        api_key=settings.EMBEDDING_API_KEY,
        base_url=settings.EMBEDDING_BASE_URL,
    )


def _load_and_split_docs(docs_dir: Path) -> list[dict]:
    """加载目录下所有 .md 文件，按标题 + 字符数两层切分"""
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
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
    """构建（或加载）ChromaDB 向量索引

    - 首次构建：加载文档 → Embedding → 写入磁盘（需下载模型 ~24MB）
    - 后续启动：直接从磁盘加载已有索引（秒级）
    - force_rebuild=True：删除旧索引重新构建
    """
    global _vector_store

    if _vector_store is not None and not force_rebuild:
        return True

    if docs_dir is None:
        docs_dir = str(PROJECT_ROOT / "docs" / "products")

    persist_dir = str(PROJECT_ROOT / settings.CHROMA_PERSIST_DIR)
    docs_path = Path(docs_dir)

    if not docs_path.exists():
        logger.error(f"文档目录不存在: {docs_dir}")
        return False

    # 强制重建：删除旧索引（Windows 下文件可能被锁，最多重试 3 次）
    if force_rebuild and Path(persist_dir).exists():
        import shutil, time
        for attempt in range(3):
            try:
                shutil.rmtree(persist_dir)
                logger.info("  已清空旧向量索引")
                break
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.5)
                else:
                    logger.warning("  无法删除旧索引（文件被占用），跳过清理")

    embedding_fn = _get_embedding_function()

    # 1. 加载并切分（原始文本同时用于 BM25，无 Embedding API 成本）
    chunks = _load_and_split_docs(docs_path)
    if not chunks:
        logger.warning("没有可索引的文档块")
        return False
    contents = [c["content"] for c in chunks]

    # 2. 向量索引：优先加载已有索引，避免 from_texts 重复追加导致集合无限膨胀
    # 注意：加载/校验任何异常都跳过重建——多实例并发连同一 SQLite 时
    # count() 可能因锁报错，若此时回退 from_texts 会重复追加（历史 bug 根源）
    if not force_rebuild and Path(persist_dir).exists():
        try:
            _vector_store = Chroma(
                collection_name="intellidesk_docs",
                embedding_function=embedding_fn,
                persist_directory=persist_dir,
            )
            count = _vector_store._collection.count()
        except Exception as e:
            logger.warning(f"  校验已有索引失败（{e}），跳过重建以避免重复追加")
            return True
        if count > 0:
            logger.info(f"  加载已有向量索引: {count} 个块（跳过重复构建）")
            _init_bm25(contents)
            return True
        _vector_store = None  # 集合存在但为空 → 继续构建

    # 2'. 首次构建或强制重建
    logger.info(f"  正在构建 ChromaDB 向量索引（{len(chunks)} 个块）...")
    metadatas = [c["metadata"] for c in chunks]
    _vector_store = Chroma.from_texts(
        texts=contents,
        metadatas=metadatas,
        embedding=embedding_fn,
        persist_directory=persist_dir,
        collection_name="intellidesk_docs",
    )
    logger.info(f"  ChromaDB 索引就绪: {_vector_store._collection.count()} 个块, 持久化到 {persist_dir}")

    # 3. 同步初始化 BM25 索引（用于混合检索）
    _init_bm25(contents)
    return True


def _init_bm25(contents: list[str]):
    """初始化 BM25 关键词索引（混合检索用，纯文本无 API 成本）"""
    try:
        from app.rag.hybrid_retriever import init_hybrid_index
        init_hybrid_index(contents)
    except Exception as e:
        logger.warning(f"  BM25 索引初始化失败（混合检索降级为纯语义）: {e}")


def get_index_status() -> dict:
    """返回索引状态"""
    if _vector_store is None:
        return {"ready": False, "chunk_count": 0}
    try:
        count = _vector_store._collection.count()
        return {"ready": True, "chunk_count": count}
    except Exception:
        return {"ready": False, "chunk_count": 0}


def get_vector_store() -> Chroma | None:
    """获取当前向量库实例"""
    return _vector_store


def search_knowledge(query: str, top_k: int | None = None) -> list[dict]:
    """语义检索知识库

    使用 ChromaDB 的相似度搜索，基于 BGE 中文 Embedding 做语义匹配。
    同义词和近义改写都能有效召回。
    """
    if _vector_store is None:
        return []

    if top_k is None:
        top_k = settings.TOP_K_RETRIEVAL

    try:
        results = _vector_store.similarity_search_with_score(query, k=top_k)

        return [
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "h1": doc.metadata.get("h1", ""),
                "h2": doc.metadata.get("h2", ""),
                # ChromaDB 返回余弦距离（0=完全相同, 2=完全相反）
                # 转为相似度（1=完全相同, 0=无关），更直观
                "score": round(1.0 - score, 4),
            }
            for doc, score in results
        ]
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        return []
