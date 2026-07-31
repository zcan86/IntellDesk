# -*- coding: utf-8 -*-
"""知识库检索 — 独立的 ChromaDB + BGE-m3 检索引擎"""

import os
from pathlib import Path

import numpy as np
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ── 配置（从环境变量读取）─────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
PERSIST_DIR = BASE_DIR / "data" / "chroma_db"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K = 3

EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")

_vector_store: Chroma | None = None


def _get_embedding():
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=EMBEDDING_API_KEY,
        base_url=EMBEDDING_BASE_URL,
    )


def init_knowledge_base():
    """构建/加载知识库索引"""
    global _vector_store

    md_files = sorted(DOCS_DIR.glob("*.md"))
    if not md_files:
        logger.warning(f"docs/ 目录为空: {DOCS_DIR}")
        return

    # 切分
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
    )
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )

    chunks = []
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        for chunk in md_splitter.split_text(text):
            for i, sub in enumerate(char_splitter.split_text(chunk.page_content)):
                chunks.append({
                    "content": sub,
                    "metadata": {
                        "source": md_file.name,
                        "h1": chunk.metadata.get("h1", ""),
                        "h2": chunk.metadata.get("h2", ""),
                        "chunk_index": i,
                    },
                })

    contents = [c["content"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    _vector_store = Chroma.from_texts(
        texts=contents, metadatas=metadatas,
        embedding=_get_embedding(),
        persist_directory=str(PERSIST_DIR),
        collection_name="mcptool_docs",
    )
    logger.info(f"知识库就绪: {_vector_store._collection.count()} 个块")


def get_kb_status() -> str:
    if _vector_store is None:
        return "未初始化"
    return f"{_vector_store._collection.count()} chunks"


def search_knowledge(query: str) -> str:
    """检索知识库，返回格式化文本"""
    if _vector_store is None:
        return "知识库未初始化，请先放入 .md 文档到 docs/ 目录并重启服务。"

    results = _vector_store.similarity_search_with_score(query, k=TOP_K)
    if not results:
        return "知识库中未找到相关信息。"

    lines = []
    for doc, score in results:
        score_sim = round(1.0 - score, 4)
        section = f"{doc.metadata.get('h1', '')} > {doc.metadata.get('h2', '')}"
        lines.append(
            f"【{doc.metadata.get('source', '?')} | {section} | 相关度 {score_sim}】\n"
            f"{doc.page_content}"
        )
    return "\n\n---\n\n".join(lines)
