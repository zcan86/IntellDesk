# -*- coding: utf-8 -*-
"""意图路由节点 — 多 Agent 调度核心

将用户问题分类为：订单 / 退换货 / 商品推荐 / 配送 / 通用
然后路由到对应的专业子 Agent 处理。
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


# ── 意图分类 ──────────────────────────────────────────────────

INTENT_CATEGORIES = {
    "order": "订单查询、订单状态、修改订单、取消订单、订单历史",
    "return": "退货、换货、退款、售后、质量问题、发错货、少发货",
    "product": "商品推荐、商品对比、商品详情、有没有卖、热销",
    "shipping": "配送方式、物流查询、快递、运费、包邮、发货时间",
    "payment": "支付方式、支付失败、货到付款、发票",
    "account": "账号、密码、手机号、注销、会员、优惠券",
    "general": "闲聊、问候、其他",
}


def classify_intent(query: str) -> dict:
    """LLM 意图识别，返回分类结果"""
    categories_desc = "\n".join([f"- {k}: {v}" for k, v in INTENT_CATEGORIES.items()])

    prompt = f"""你是电商客服的意图识别模块。将用户问题归类为以下之一：

{categories_desc}

用户：{query}

返回 JSON：{{"intent": "分类名", "confidence": 0.0-1.0, "keywords": ["关键词"]}}
只返回 JSON。"""

    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
            timeout=15,
        )
        content = resp.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception:
        return {"intent": "general", "confidence": 0.5, "keywords": []}


# ── 专业子 Agent Prompt ──────────────────────────────────────

SPECIALIST_PROMPTS = {
    "order": """你是速购电商的订单客服专员。
职责：回答订单状态、修改地址、取消订单等问题。
规则：引导用户提供订单号；不可查看真实订单数据时说明需人工协助。""",

    "return": """你是速购电商的售后客服专员。
职责：处理退货、换货、退款申请。
规则：先检索退换货政策，再引导用户操作；7天无理由退货、15天换货。""",

    "product": """你是速购电商的商品导购专员。
职责：推荐商品、对比商品、解答商品相关问题。
规则：先检索商品知识库；根据用户预算和需求推荐；不夸大商品功能。""",

    "shipping": """你是速购电商的物流客服专员。
职责：解答配送方式、物流查询、运费、发货时间等问题。
规则：满99包邮；当天16点前下单当天发货；偏远地区满199包邮。""",

    "payment": """你是速购电商的支付客服专员。
职责：解答支付方式、支付失败、发票等问题。
规则：支持微信/支付宝/银行卡/余额；不支持货到付款。""",

    "account": """你是速购电商的账号客服专员。
职责：解答账号、密码、手机号、会员、优惠券等问题。""",

    "general": """你是速购电商的综合客服专员。
职责：处理问候、闲聊及未分类问题；友好地引导用户说明具体需求。""",
}
