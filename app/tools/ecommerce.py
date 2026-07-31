# -*- coding: utf-8 -*-
"""电商专用工具

提供订单查询、物流跟踪、退换货指引、商品搜索等工具。
"""

import random
from datetime import datetime, timedelta

from langchain.tools import tool
from loguru import logger


@tool
def query_order(order_id: str) -> str:
    """查询订单状态和详情。

    当用户提供订单号时调用。例如："帮我查一下 DD20240701001"

    Args:
        order_id: 订单号，如 DD20240701001
    """
    logger.info(f"📦 查询订单: {order_id}")
    from app.database import get_order
    order = get_order(order_id)

    if not order:
        return f"未找到订单 {order_id}。请确认订单号是否正确。"

    shipping_map = {
        "待付款": "⏳ 待付款",
        "待发货": "📦 待发货",
        "运输中": "🚚 运输中",
        "已签收": "✅ 已签收",
        "已取消": "❌ 已取消",
    }
    status_text = shipping_map.get(order["status"], order["status"])

    lines = [
        f"📦 订单 {order_id}",
        f"  用户：{order.get('user_name', '')}",
        f"  商品：{order['product_name']}",
        f"  尺码：EU {order['shoe_size']}" if order.get("shoe_size") else "",
        f"  数量：{order['quantity']}",
        f"  金额：¥{order['price']}",
        f"  下单时间：{order['created_at']}",
        f"  当前状态：{status_text}",
    ]
    if order.get("tracking_number"):
        lines.append(f"  快递单号：{order['tracking_number']}")
    if order.get("shipping_address"):
        lines.append(f"  收货地址：{order['shipping_address']}")

    return "\n".join([l for l in lines if l])


@tool
def track_delivery(order_id: str) -> str:
    """查询物流轨迹。当用户询问快递到哪了、物流详情时调用。"""
    logger.info(f"🚚 物流查询: {order_id}")
    from app.database import get_order
    order = get_order(order_id)

    if not order:
        return f"未找到订单 {order_id}。"

    status = order["status"]
    if status == "待付款":
        return f"订单 {order_id} 尚未付款，无法查询物流。"
    if status == "待发货":
        return f"订单 {order_id} 已付款，预计 24 小时内从【浙江杭州耐克仓库】发出。"

    tn = order.get("tracking_number", "")
    address = order.get("shipping_address", "")

    # 提取目的地城市
    dest = "目的地"
    if "北京" in (address or ""): dest = "北京"
    elif "上海" in (address or ""): dest = "上海"
    elif "广州" in (address or ""): dest = "广州"
    elif "深圳" in (address or ""): dest = "深圳"
    elif "杭州" in (address or ""): dest = "杭州"

    if status == "已签收":
        return (
            f"🚚 订单 {order_id}\n"
            f"  快递单号：{tn}\n"
            f"  发货地：浙江杭州耐克仓库\n"
            f"  目的地：{address}\n"
            f"  状态：✅ 已签收"
        )

    # 运输中 — 模拟轨迹节点
    now = datetime.now()
    product = order["product_name"]
    return (
        f"🚚 订单 {order_id} — {product}\n"
        f"  快递单号：{tn}\n"
        f"  发货地：浙江杭州耐克仓库\n"
        f"  目的地：{address}\n\n"
        f"  物流轨迹：\n"
        f"  ● {now.strftime('%m-%d %H:%M')}  快件到达【{dest}分拨中心】，准备派送\n"
        f"  ● {(now - timedelta(hours=6)).strftime('%m-%d %H:%M')}  快件到达【{dest}中转站】\n"
        f"  ● {(now - timedelta(hours=18)).strftime('%m-%d %H:%M')}  快件离开【杭州集散中心】\n"
        f"  ● {(now - timedelta(hours=24)).strftime('%m-%d %H:%M')}  【浙江杭州耐克仓库】已揽件\n\n"
        f"  预计今天到达，请保持电话畅通 📱"
    )


@tool
def process_return(order_id: str, reason: str = "", return_type: str = "退货退款") -> str:
    """处理退换货申请。

    当用户明确要求退货/退款/换货并提供了订单号时调用。
    Agent 必须先确认用户意图（退货退款 vs 换货），再调用此工具。

    Args:
        order_id: 订单号
        reason: 退换货原因（质量问题/尺码不合适/不想要/发错货）
        return_type: 退货退款 / 退货 / 换货
    """
    logger.info(f"🔄 退换货申请: {order_id} {return_type} ({reason})")
    from app.database import create_return_request

    result = create_return_request(order_id, reason, return_type)

    if result["success"]:
        return (
            f"🔄 {return_type}申请\n"
            f"  订单: {result['order']}\n"
            f"  签收天数: {result['days_since_sign']} 天\n"
            f"  原因: {reason}\n\n"
            f"{result['steps']}"
        )
    else:
        return f"❌ 无法申请{return_type}\n{result['reason']}"


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

    # 品类映射
    category_map = {
        "跑步": [5, 6], "篮球": [4], "气垫": [1, 8],
        "休闲": [1, 2, 3, 7], "运动": [1, 2, 3, 4, 5, 6, 7, 8],
        "复古": [7], "经典": [2, 7], "潮流": [3],
        "白色": [2], "黑色": [3], "银色": [1],
        "便宜": [3, 7], "贵": [4, 5], "专业": [5],
    }

    matched_ids = set()
    for cat, ids in category_map.items():
        if cat in kw:
            matched_ids.update(ids)

    if matched_ids:
        results = [(idx, *catalog[idx]) for idx in matched_ids]
    else:
        for idx, (name, price, tags, img) in catalog.items():
            if kw in name.lower() or any(t in name.lower() for t in kw.split()) or kw in tags:
                results.append((idx, name, price, tags, img))

    if not results:
        results = [(idx, *catalog[idx]) for idx in catalog]

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
