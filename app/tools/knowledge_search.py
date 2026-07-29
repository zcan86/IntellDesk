# -*- coding: utf-8 -*-
"""知识库检索 Tool（v2 — Adaptive-RAG）

v1: 单一 ChromaDB 语义检索
v2: Adaptive-RAG: 查询分析 → 混合检索 → RRF融合 → LLM Rerank → Self-RAG反思
"""

from langchain.tools import tool
from loguru import logger

from app.config import settings
from app.rag.adaptive_rag import adaptive_search


@tool
def search_knowledge_base(query: str) -> str:
    """检索 IntelliDesk 产品知识库。

    当用户询问以下类型的问题时，**必须**调用此工具：
    - 产品功能、使用方法、操作步骤
    - 计费方案、价格、套餐差异
    - API 集成、技术文档
    - 账号、安全、隐私相关问题
    - 故障排查、常见问题

    Args:
        query: 用自然语言描述的搜索查询

    Returns:
        知识库中相关的文档片段，已通过 Adaptive-RAG 优化排序
    """
    logger.info(f"🔍 Adaptive-RAG 检索: {query[:100]}...")

    results = adaptive_search(query, top_k=settings.TOP_K_RETRIEVAL)

    if not results:
        return "知识库中未找到相关信息。请告知用户该问题暂时无法回答，建议联系人工客服。"

    formatted = []
    for i, r in enumerate(results, 1):
        source = r.get("source", "unknown")
        section = f"{r.get('h1', '')} > {r.get('h2', '')}" if r.get("h2") else r.get("h1", "")
        formatted.append(
            f"【来源 {i}】{source} | 章节：{section}\n{r['content']}"
        )

    return "\n\n---\n\n".join(formatted)
