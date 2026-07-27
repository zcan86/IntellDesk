# -*- coding: utf-8 -*-
"""知识库检索 Tool

将 RAG 检索能力封装为 LangChain Tool，
Agent 在需要查询产品文档时自动调用。
"""

from langchain.tools import tool
from loguru import logger

from app.rag.loader import search_knowledge


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
        query: 用自然语言描述的搜索查询，建议提炼用户问题的关键词

    Returns:
        知识库中相关的文档片段，包含来源文件名
    """
    logger.info(f"🔍 Agent 检索知识库: {query[:100]}...")

    results = search_knowledge(query, top_k=3)

    if not results:
        return "知识库中未找到相关信息。请告知用户该问题暂时无法回答，建议联系人工客服。"

    # 格式化为 Agent 可读的文本
    formatted = []
    for i, r in enumerate(results, 1):
        source = r["source"]
        section = f"{r['h1']} > {r['h2']}" if r["h2"] else r["h1"]
        formatted.append(
            f"【来源 {i}】{source} | 章节：{section}\n{r['content']}"
        )

    return "\n\n---\n\n".join(formatted)
