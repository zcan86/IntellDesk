# -*- coding: utf-8 -*-
"""知识库检索 Tool — 快速混合检索

BM25 + BGE-m3 + RRF 融合，毫秒级返回，无 LLM 额外调用。
"""

from langchain.tools import tool
from loguru import logger
from app.config import settings
from app.rag.hybrid_retriever import hybrid_search


@tool
def search_knowledge_base(query: str) -> str:
    """检索知识库（退换货政策/配送规则/FAQ等）。当用户询问政策类问题时调用。

    Args:
        query: 自然语言搜索查询
    """
    logger.info(f" 检索: {query[:100]}...")
    results = hybrid_search(query, top_k=settings.TOP_K_RETRIEVAL)

    if not results:
        return "知识库中未找到相关信息。"

    formatted = []
    for i, r in enumerate(results, 1):
        source = r.get("source", "unknown")
        section = f"{r.get('h1', '')} > {r.get('h2', '')}" if r.get("h2") else r.get("h1", "")
        formatted.append(f"【来源 {i}】{source} | {section}\n{r['content']}")
    return "\n\n---\n\n".join(formatted)

