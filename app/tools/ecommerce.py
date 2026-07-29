# -*- coding: utf-8 -*-
"""电商专用工具

提供订单查询、物流跟踪、退换货指引、商品搜索等工具。
"""

import random
from datetime import datetime, timedelta

from langchain.tools import tool
from loguru import logger


# ── Mock 数据 ─────────────────────────────────────────────────
_ORDERS = {
    "DD20240001": {"status": "已签收", "date": "2025-07-20", "item": "蓝牙降噪耳机 Pro", "price": 299},
    "DD20240002": {"status": "运输中", "date": "2025-07-28", "item": "纯棉短袖T恤", "price": 59},
    "DD20240003": {"status": "待发货", "date": "2025-07-29", "item": "不锈钢保温杯", "price": 89},
}


@tool
def query_order(order_id: str) -> str:
    """查询订单状态和详情。

    当用户提供订单号并询问订单状态时调用。
    例如："帮我查一下 DD20240001 的订单状态"

    Args:
        order_id: 订单号，如 DD20240001
    """
    logger.info(f"📦 查询订单: {order_id}")
    order = _ORDERS.get(order_id)

    if not order:
        return f"未找到订单 {order_id}。请确认订单号是否正确（格式：DD + 8位数字）。"

    return (
        f"📦 订单 {order_id}\n"
        f"  商品：{order['item']}\n"
        f"  金额：¥{order['price']}\n"
        f"  下单时间：{order['date']}\n"
        f"  当前状态：{order['status']}\n"
        f"  预计送达：{_estimate_delivery(order['date'], order['status'])}"
    )


@tool
def track_delivery(order_id: str) -> str:
    """查询物流轨迹。

    当用户询问物流详情、快递到哪了时调用。

    Args:
        order_id: 订单号
    """
    logger.info(f"🚚 物流查询: {order_id}")
    order = _ORDERS.get(order_id)

    if not order:
        return f"未找到订单 {order_id}。"

    if order["status"] == "待发货":
        return f"订单 {order_id} 尚未发货，预计 24 小时内发出。"

    if order["status"] == "已签收":
        return f"订单 {order_id} 已于 {order['date']} 签收。"

    # Mock 物流轨迹
    now = datetime.now()
    return (
        f"🚚 订单 {order_id} 物流轨迹：\n"
        f"  {now.strftime('%m-%d %H:%M')}  快件到达【目的地分拨中心】\n"
        f"  {(now - timedelta(hours=5)).strftime('%m-%d %H:%M')}  快件离开【中转站】\n"
        f"  {(now - timedelta(hours=12)).strftime('%m-%d %H:%M')}  商家已揽件\n"
        f"  预计今天下午派送"
    )


@tool
def return_guide(reason: str = "") -> str:
    """查询退换货流程和条件。

    当用户询问如何退货、退货条件、退款时效时调用。

    Args:
        reason: 退货原因（可选），如"质量问题""尺码不合适"
    """
    logger.info(f"🔄 退换货指引: {reason}")

    base = (
        "🔄 速购电商退换货指引：\n\n"
        "**退货政策**：签收后 7 天内无理由退货（特殊商品除外）\n"
        "**换货政策**：签收后 15 天内质量问题可换货\n\n"
        "**退货流程**：\n"
        "1. App → 我的订单 → 申请退货\n"
        "2. 填写原因并提交\n"
        "3. 1-2 个工作日审核\n"
        "4. 审核通过后获取退货地址\n"
        "5. 寄回 → 仓库签收 → 1-3 工作日退款\n\n"
    )

    if "质量" in reason:
        base += "⚠️ 质量问题：请上传商品照片作为凭证，商家承担来回运费。\n"
    elif "尺码" in reason or "不合适" in reason:
        base += "👕 尺码问题：适用 7 天无理由退货，买家承担寄回运费。\n"
    elif "发错" in reason:
        base += "📦 发错货：商家承担退回运费并重新发货，联系客服优先处理。\n"

    base += "\n**退款时效**：微信/支付宝 1-3 工作日 | 银行卡 3-7 工作日 | 余额即时到账"

    return base


@tool
def product_search(keyword: str) -> str:
    """搜索耐克鞋款。当用户询问鞋子、运动鞋、推荐鞋款时调用。

    Args:
        keyword: 搜索关键词（如 Air Max/跑步/篮球/白色/便宜 等）
    """
    logger.info(f"🔍 商品搜索: {keyword}")

    catalog = {
        1:  ("Nike Air Max 97 银色子弹", 1199, "气垫鞋/运动休闲", "data/product_images/1.jpg"),
        2:  ("Nike Air Force 1 '07 白色", 899, "运动休闲/百搭经典", "data/product_images/2.jpg"),
        3:  ("Nike Dunk Low Retro 熊猫", 799, "运动休闲/潮流", "data/product_images/3.jpg"),
        4:  ("Nike Air Jordan 1 Retro High OG", 1499, "篮球鞋/收藏级", "data/product_images/4.jpg"),
        5:  ("Nike ZoomX Vaporfly 3 竞速", 2599, "跑步鞋/专业竞速", "data/product_images/5.jpg"),
        6:  ("Nike React Infinity Run 4", 1099, "跑步鞋/日常训练", "data/product_images/6.jpg"),
        7:  ("Nike Blazer Mid '77 Vintage", 749, "运动休闲/复古", "data/product_images/7.jpg"),
        8:  ("Nike Air Max 270 React", 1299, "气垫鞋/舒适", "data/product_images/8.jpg"),
    }

    # 关键词匹配
    kw = keyword.lower()
    results = []
    for idx, (name, price, tags, img) in catalog.items():
        if kw in name.lower() or any(t in name.lower() for t in kw.split()) or kw in tags:
            results.append((idx, name, price, tags, img))

    if not results:
        results = list(catalog.values())  # 无匹配则返回全部

    lines = [f"🔍 「{keyword}」搜索结果："]
    for idx, name, price, tags, img in results[:5]:
        lines.append(f"  #{idx} {name} — ¥{price} ({tags})")
    return "\n".join(lines)



def _estimate_delivery(order_date: str, status: str) -> str:
    """估算送达时间"""
    if status == "已签收":
        return "已签收"
    if status == "待发货":
        return "预计 2-4 天"
    return "预计今天送达"
