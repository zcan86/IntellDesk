# -*- coding: utf-8 -*-
"""LLM 重排序器

对检索结果进行精排，过滤不相关文档，提升 Precision。

核心思路：用 LLM 判断每个文档是否回答了用户问题。
对比 Cohere Rerank API 的免费替代方案。
"""

import json
from openai import OpenAI
from loguru import logger

from app.config import settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    return _client


def rerank(
    query: str,
    documents: list[dict],
    top_k: int = 3,
    threshold: float = 3,
) -> list[dict]:
    """LLM 重排序

    将每个文档和查询配对，让 LLM 打分（1-5），过滤低分文档。

    Args:
        query: 用户问题
        documents: 检索结果列表 [{"content":..., "source":..., "score":...}, ...]
        top_k: 返回数量
        threshold: LLM 评分过滤阈值（1-5 分制，低于此值丢弃）

    Returns:
        重排序并过滤后的结果列表
    """
    if len(documents) <= top_k:
        return documents

    docs_to_rank = documents[:min(len(documents), 8)]  # 最多重排 8 个

    # 构建评分 prompt
    docs_text = ""
    for i, doc in enumerate(docs_to_rank, 1):
        content = doc["content"][:300]  # 每个文档截取 300 字符
        docs_text += f"[{i}] {content}\n\n"

    prompt = f"""评估以下文档片段对用户问题的相关度。

用户问题：{query}

文档片段：
{docs_text}

对每个文档打分（1-5 分）：
5 = 完全回答了问题
4 = 高度相关
3 = 部分相关
2 = 略有关联
1 = 完全无关

只返回 JSON 数组，格式：[{{"id": 1, "score": 3}}, {{"id": 2, "score": 5}}, ...]"""

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
            timeout=30,
        )
        content = resp.choices[0].message.content.strip()

        # 提取 JSON
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        scores = json.loads(content)
    except Exception as e:
        logger.warning(f"  Rerank LLM 调用失败，跳过重排: {e}")
        return documents[:top_k]

    # 映射评分回文档
    scored = []
    for item in scores:
        idx = item["id"] - 1
        if 0 <= idx < len(docs_to_rank):
            llm_score = item["score"]
            if llm_score >= threshold:
                doc = dict(docs_to_rank[idx])
                # 综合原始检索分 + LLM 评分
                doc["rerank_score"] = llm_score
                doc["score"] = round(doc.get("score", 0) * 0.4 + (llm_score / 5.0) * 0.6, 4)
                scored.append(doc)

    # 按新分数降序
    scored.sort(key=lambda x: x["score"], reverse=True)

    logger.debug(
        f"  Rerank: {len(documents)} → {len(scored)} (阈值 {threshold})"
    )
    return scored[:top_k] if scored else documents[:top_k]
