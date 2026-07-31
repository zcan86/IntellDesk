# -*- coding: utf-8 -*-
"""请求分级路由

Layer 1: 规则匹配（精确/正则/关键词）→ 毫秒级，零 LLM 成本
Layer 2: 透传 Agent（复杂问题/多跳推理）
"""

import re
import numpy as np
from loguru import logger

# ── 语义匹配（延迟初始化，复用 ChromaDB 基础设施）─────────────

_semantic_ready = False
_semantic_qa: list[tuple[str, str]] = []  # [(question, answer), ...]
_semantic_matrix = None
_semantic_vectorizer = None


def _init_semantic():
    """初始化语义 QA 缓存（使用轻量 TF-IDF，复用已有依赖）"""
    global _semantic_ready, _semantic_matrix, _semantic_vectorizer, _semantic_qa
    if _semantic_ready:
        return

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    # FAQ 问答对（问题 → 答案）
    _semantic_qa = [
        ("退货流程", "签收7天内可无理由退货。流程：App申请→审核→寄回→仓库签收→1-3工作日退款。"),
        ("换货流程", "签收15天内质量问题可换货。流程：App申请换货→审核→寄回→2-3工作日寄出新商品。"),
        ("包邮条件", "全国满¥99包邮，偏远地区(新疆/西藏/青海/宁夏)满¥199包邮。"),
        ("发货时间", "当日16:00前下单当天发货，16:00后次日发货。"),
        ("尺码范围", "EU 36-44码，男女款均有。请提供具体商品名查询库存。"),
        ("支付方式", "支持微信、支付宝、银行卡、平台余额。不支持货到付款。"),
        ("退款到账时间", "微信/支付宝1-3工作日，银行卡3-7工作日，余额即时到账。"),
        ("会员权益", "普通(注册享包邮)/银卡(年消费¥2000+,9.5折)/金卡(¥5000+,9折免运费)/钻石(¥10000+,8.5折)"),
        ("门店地址", "线下体验店：北京/上海/广州/深圳/杭州。"),
        ("客服电话", "人工客服：400-888-6666（每天9:00-21:00）。"),
    ]

    _semantic_vectorizer = TfidfVectorizer(ngram_range=(1, 2), analyzer="char_wb")
    questions = [q for q, _ in _semantic_qa]
    _semantic_matrix = _semantic_vectorizer.fit_transform(questions)
    _semantic_ready = True
    logger.info(f"语义路由就绪: {len(_semantic_qa)} 条FAQ")


def _semantic_match(text: str, threshold: float = 0.35) -> str | None:
    """TF-IDF 语义匹配"""
    _init_semantic()
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        q_vec = _semantic_vectorizer.transform([text])
        scores = cosine_similarity(q_vec, _semantic_matrix).flatten()
        best_idx = int(np.argmax(scores))
        if scores[best_idx] >= threshold:
            logger.info(f"  [路由] 语义命中: {_semantic_qa[best_idx][0]} (score={scores[best_idx]:.3f})")
            return _semantic_qa[best_idx][1]
    except Exception:
        pass
    return None

# ── Layer 1: 精确匹配缓存 ────────────────────────────────────

EXACT_CACHE = {
    "你好": "你好！我是耐克旗舰店智能客服小速 👋 有什么可以帮您？",
    "在吗": "在的！有什么可以帮您？",
    "在？": "在的！有什么可以帮您？",
    "谢谢": "不客气！还有其他问题随时问我～ 😊",
    "谢谢你": "不客气！还有其他问题随时问我～ 😊",
    "感谢": "不客气！还有其他问题随时问我～ 😊",
    "再见": "再见！祝您生活愉快～ 👋",
    "拜拜": "再见！祝您生活愉快～ 👋",
}

# ── Layer 1: 关键词直接回答 ──────────────────────────────────

KEYWORD_ANSWERS = {
    "退货流程": (
        "📋 退货流程：\n"
        "1. App → 我的订单 → 申请退货\n"
        "2. 填写退货原因并提交\n"
        "3. 1-2个工作日审核\n"
        "4. 审核通过后获取退货地址\n"
        "5. 寄回商品 → 仓库签收 → 1-3工作日退款\n\n"
        "⚠️ 条件：签收7天内、商品未使用、包装完好。\n"
        "如需办理，请提供订单号。"
    ),
    "换货流程": (
        "📋 换货流程：\n"
        "1. App → 我的订单 → 申请换货\n"
        "2. 填写换货原因并提交\n"
        "3. 审核通过后寄回商品\n"
        "4. 仓库收到后 2-3 工作日寄出新商品\n\n"
        "⚠️ 条件：签收15天内、质量问题。\n"
        "如需办理，请提供订单号。"
    ),
    "包邮": "📦 全国满 ¥99 包邮，偏远地区（新疆/西藏/青海/宁夏）满 ¥199 包邮。自提点全部免运费。",
    "运费": "📦 全国满 ¥99 包邮，偏远地区满 ¥199 包邮。不满包邮门槛的订单，运费 ¥6 起（中通/圆通）。",
    "尺码": "👟 耐克鞋款尺码：EU 36-44，男女款均有。具体款式库存请提供商品名查询。",
    "发货时间": "🚚 当日 16:00 前下单当天发货，16:00 后次日发货。预售商品按页面标注时间发货。",
    "支付方式": "💳 支持微信支付、支付宝、银行卡、平台余额。暂不支持货到付款。",
    "退款时间": "💵 退款到账时间：微信/支付宝 1-3 工作日，银行卡 3-7 工作日，平台余额即时到账。",
    "会员": (
        "👑 会员权益：\n"
        "普通会员：注册即享，满 ¥99 包邮\n"
        "银卡会员：年消费 ¥2000+，9.5折+优先发货\n"
        "金卡会员：年消费 ¥5000+，9折+免运费+专属客服\n"
        "钻石会员：年消费 ¥10000+，8.5折+生日礼"
    ),
    "门店": "📍 线下体验店：北京/上海/广州/深圳/杭州。具体地址请告知城市。",
    "客服": "📞 人工客服热线：400-888-6666（每天 9:00-21:00）",
}


def _match_keywords(text: str) -> str | None:
    """关键词匹配：包含任一关键词即命中"""
    for keyword, answer in KEYWORD_ANSWERS.items():
        if keyword in text:
            logger.info(f"  [路由] 关键词命中: {keyword}")
            return answer
    return None


# ── Layer 1: 正则匹配（订单号）────────────────────────────────

ORDER_PATTERN = re.compile(r"(DD\d{10})", re.IGNORECASE)


def _query_order_direct(text: str) -> str | None:
    """订单号正则匹配 → 直接查数据库格式化返回"""
    match = ORDER_PATTERN.search(text)
    if not match:
        return None

    order_id = match.group(1)
    # 关键词判断：问物流 vs 问状态 vs 退货
    is_tracking = any(w in text for w in ["物流", "快递", "到哪", "配送", "运输"])
    is_return = any(w in text for w in ["退货", "退款", "换货", "退换"])

    from app.database import get_order
    order = get_order(order_id)
    if not order:
        return f"未找到订单 {order_id}。请确认订单号是否正确。"

    if is_return:
        return None  # 退货需要AI判断条件，透传

    if is_tracking:
        from app.tools.ecommerce import track_delivery
        return track_delivery.invoke(order_id)

    # 默认：显示订单状态
    status_map = {"待付款": "⏳ 待付款", "待发货": "📦 待发货", "运输中": "🚚 运输中", "已签收": "✅ 已签收"}
    s = status_map.get(order["status"], order["status"])
    return (
        f"📦 订单 {order_id}\n"
        f"  商品：{order['product_name']}\n"
        f"  金额：¥{order['price']}\n"
        f"  下单：{order['created_at'][:10]}\n"
        f"  状态：{s}\n"
        f"  尺码：EU {order.get('shoe_size', '-')}"
    )


# ── 路由入口 ──────────────────────────────────────────────────

def route(text: str) -> tuple[str, str] | None:
    """分级路由

    Returns:
        (response_text, source) 或 None（透传 Agent）
        source: "cache" | "keyword" | "db" | "agent"
    """
    msg = text.strip()

    # 1. 精确匹配
    if msg in EXACT_CACHE:
        logger.info(f"  [路由] 精确匹配: {msg[:30]}")
        return (EXACT_CACHE[msg], "cache")

    # 2. 订单号正则
    result = _query_order_direct(msg)
    if result:
        return (result, "db")

    # 3. 关键词
    result = _match_keywords(msg)
    if result:
        return (result, "keyword")

    # 4. 语义匹配（Layer 2）
    result = _semantic_match(msg)
    if result:
        return (result, "semantic")

    # 5. 未命中 → 透传 Agent
    return None
