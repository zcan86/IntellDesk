# -*- coding: utf-8 -*-
"""Adaptive-RAG + Self-RAG 自适应检索

核心流程：
1. 查询分析: LLM 判断问题复杂度，决定检索策略
2. 策略路由: 简单问题 → 直接检索, 复杂问题 → 分解子问题 + 混合检索
3. 检索执行: 混合检索（语义 + 关键词 + RRF）
4. 重排序: LLM Rerank 精排
5. 自我反思: 检查检索质量，不满足则改写查询重试（最多 2 次）
6. 上下文压缩: Token 预算管理
"""

import json
from openai import OpenAI
from loguru import logger

from app.config import settings
from app.rag.hybrid_retriever import hybrid_search
from app.rag.reranker import rerank

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _client


# ── 查询分析 ──────────────────────────────────────────────────

def analyze_query(query: str) -> dict:
    """LLM 分析查询，返回复杂度评估和检索策略建议"""
    prompt = f"""分析以下用户查询，返回 JSON：

{{
  "complexity": "simple|medium|complex",
  "needs_decomposition": true/false,
  "sub_queries": ["子问题1", "子问题2"] 或 [],
  "retrieval_focus": "产品功能/计费价格/技术API/使用帮助/售后政策"
}}

查询：{query}

只返回 JSON。"""

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
            timeout=20,
        )
        content = resp.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception:
        return {"complexity": "medium", "needs_decomposition": False, "sub_queries": []}


# ── 自我反思 ──────────────────────────────────────────────────

def reflect_on_results(query: str, results: list[dict]) -> dict:
    """检查检索结果是否充分回答了问题

    Returns:
        {"sufficient": bool, "reason": str, "rewritten_query": str | None}
    """
    if not results:
        return {"sufficient": False, "reason": "无检索结果", "rewritten_query": None}

    context = "\n\n".join([r["content"][:200] for r in results[:3]])

    prompt = f"""判断以下检索结果是否能回答用户问题。

用户问题：{query}

检索结果：
{context}

返回 JSON：
{{
  "sufficient": true/false,
  "reason": "一句话说明是否充分",
  "rewritten_query": "如果 insufficient，给出改写后的查询关键词"
}}

只返回 JSON。"""

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
            timeout=20,
        )
        content = resp.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception:
        return {"sufficient": True, "reason": "默认通过", "rewritten_query": None}


# ── 自适应检索入口 ────────────────────────────────────────────

def adaptive_search(
    query: str,
    top_k: int = 3,
    max_reflections: int = 2,
) -> list[dict]:
    """自适应检索 + Self-RAG

    1. 分析查询 → 确定检索策略
    2. 复杂查询 → 分解为子查询分别检索
    3. 混合检索 → RRF 融合
    4. LLM Rerank → 精排
    5. 自我反思 → 不够则改写重试
    """
    # Step 1: 查询分析
    analysis = analyze_query(query)
    complexity = analysis.get("complexity", "medium")
    sub_queries = analysis.get("sub_queries", [])
    logger.info(f"  [Adaptive-RAG] 查询复杂度: {complexity}")

    # Step 2: 策略路由
    all_raw_results = []

    if complexity == "complex" and sub_queries:
        # 分解子问题，分别检索
        for sq in sub_queries:
            logger.debug(f"    子查询: {sq}")
            sub_results = hybrid_search(sq, top_k=3)
            all_raw_results.extend(sub_results)
        # 去重
        seen = set()
        unique_results = []
        for r in all_raw_results:
            if r["content"] not in seen:
                seen.add(r["content"])
                unique_results.append(r)
        all_raw_results = unique_results
    else:
        # 简单/中等: 直接混合检索
        all_raw_results = hybrid_search(query, top_k=5)

    # Step 3: 重排序
    reranked = rerank(query, all_raw_results, top_k=top_k)

    # Step 4: 自我反思
    for reflection_round in range(max_reflections):
        reflection = reflect_on_results(query, reranked)

        if reflection["sufficient"]:
            logger.info(f"  [Self-RAG] 检索充分 ✓")
            break

        # 不充分 → 改写查询重试
        rewritten = reflection.get("rewritten_query")
        if rewritten and reflection_round < max_reflections - 1:
            logger.info(f"  [Self-RAG] 检索不充分，改写查询: {rewritten}")
            extra_results = hybrid_search(rewritten, top_k=3)
            # 合并去重
            existing = {r["content"] for r in reranked}
            for r in extra_results:
                if r["content"] not in existing:
                    reranked.append(r)
            reranked = rerank(query, reranked, top_k=top_k)
        else:
            logger.info(f"  [Self-RAG] 达到最大反思次数，返回当前结果")

    return reranked[:top_k]
