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
    logger.info(f" 查询订单: {order_id}")
    from app.database import get_order
    order = get_order(order_id)

    if not order:
        return f"未找到订单 {order_id}。请确认订单号是否正确。"

    shipping_map = {
        "待付款": " 待付款",
        "待发货": " 待发货",
        "运输中": " 运输中",
        "已签收": " 已签收",
        "已取消": " 已取消",
    }
    status_text = shipping_map.get(order["status"], order["status"])

    lines = [
        f" 订单 {order_id}",
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
    logger.info(f" 物流查询: {order_id}")
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
            f" 订单 {order_id}\n"
            f"  快递单号：{tn}\n"
            f"  发货地：浙江杭州耐克仓库\n"
            f"  目的地：{address}\n"
            f"  状态： 已签收"
        )

    # 运输中 — 模拟轨迹节点
    now = datetime.now()
    product = order["product_name"]
    return (
        f" 订单 {order_id} — {product}\n"
        f"  快递单号：{tn}\n"
        f"  发货地：浙江杭州耐克仓库\n"
        f"  目的地：{address}\n\n"
        f"  物流轨迹：\n"
        f"  ● {now.strftime('%m-%d %H:%M')}  快件到达【{dest}分拨中心】，准备派送\n"
        f"  ● {(now - timedelta(hours=6)).strftime('%m-%d %H:%M')}  快件到达【{dest}中转站】\n"
        f"  ● {(now - timedelta(hours=18)).strftime('%m-%d %H:%M')}  快件离开【杭州集散中心】\n"
        f"  ● {(now - timedelta(hours=24)).strftime('%m-%d %H:%M')}  【浙江杭州耐克仓库】已揽件\n\n"
        f"  预计今天到达，请保持电话畅通 "
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
    logger.info(f" 退换货申请: {order_id} {return_type} ({reason})")
    from app.database import create_return_request

    result = create_return_request(order_id, reason, return_type)

    if result["success"]:
        return (
            f" {return_type}申请\n"
            f"  订单: {result['order']}\n"
            f"  签收天数: {result['days_since_sign']} 天\n"
            f"  原因: {reason}\n\n"
            f"{result['steps']}"
        )
    else:
        return f" 无法申请{return_type}\n{result['reason']}"


@tool
def product_search(keyword: str) -> str:
    """搜索耐克鞋款。支持颜色/尺码/价格/品类筛选。

    例如："白色42码1000以内跑步鞋" → 精准匹配

    Args:
        keyword: 搜索关键词
    """
    logger.info(f" 商品搜索: {keyword}")

    catalog = {
        1:  ("Nike Air Max 97", 1199, ["气垫鞋", "运动休闲"], ["银色"]),
        2:  ("Nike Air Force 1 '07", 899, ["运动休闲", "百搭经典"], ["白色"]),
        3:  ("Nike Dunk Low Retro", 799, ["运动休闲", "潮流"], ["黑色"]),
        4:  ("Nike Air Jordan 1 Retro High OG", 1499, ["篮球鞋", "收藏级"], ["黑红"]),
        5:  ("Nike ZoomX Vaporfly 3", 2599, ["跑步鞋", "专业竞速"], ["荧光绿"]),
        6:  ("Nike React Infinity Run 4", 1099, ["跑步鞋", "日常训练"], ["白色", "黑色"]),
        7:  ("Nike Blazer Mid '77 Vintage", 749, ["运动休闲", "复古"], ["白色"]),
        8:  ("Nike Air Max 270 React", 1299, ["气垫鞋", "舒适"], ["黑白"]),
    }

    # 尺码统一
    all_sizes = list(range(36, 45))

    # 解析筛选条件
    import re
    kw = keyword.lower()

    # 价格：1000以内 / 800-1200 / 1000以上
    max_price = None
    min_price = None
    m = re.search(r"(\d+)\s*以内", kw)
    if m: max_price = int(m.group(1))
    m = re.search(r"(\d+)\s*以上", kw)
    if m: min_price = int(m.group(1))
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)", kw)
    if m: min_price, max_price = int(m.group(1)), int(m.group(2))

    # 尺码
    target_size = None
    m = re.search(r"(\d{2})\s*码", kw)
    if m:
        sz = int(m.group(1))
        if 36 <= sz <= 44: target_size = sz

    # 颜色
    colors = ["白色", "黑色", "银色", "黑红", "荧光绿", "黑白"]
    target_color = None
    for c in colors:
        if c in keyword:
            target_color = c
            break

    results = []
    for idx, (name, price, tags, item_colors) in catalog.items():
        # 价格过滤
        if max_price and price > max_price: continue
        if min_price and price < min_price: continue
        # 颜色过滤
        if target_color and target_color not in item_colors: continue
        # 关键词匹配
        matched = False
        for t in tags:
            if t in kw: matched = True
        if any(w in name.lower() for w in kw.split()): matched = True
        # 价格/尺码/颜色查询不要求品类匹配
        if max_price or min_price or target_color or target_size: matched = True
        if matched:
            results.append((idx, name, price, tags, item_colors))

    if not results:
        results = [(idx, name, price, tags, item_colors) for idx, (name, price, tags, item_colors) in catalog.items()]

    lines = []
    filters = []
    if target_color: filters.append(target_color)
    if target_size: filters.append(f"{target_size}码")
    if max_price: filters.append(f"{max_price}以内")
    if min_price and max_price: filters.append(f"{min_price}-{max_price}")
    filter_str = f"（{'/'.join(filters)}）" if filters else ""

    lines.append(f" 「{keyword}」{filter_str}共 {len(results)} 款：")
    for idx, name, price, tags, colors in results[:5]:
        color_str = "/".join(colors)
        lines.append(f"  #{idx} {name} — ¥{price} | {color_str} | {tags[0]} | EU36-44")
    return "\n".join(lines)



def _estimate_delivery(order_date: str, status: str) -> str:
    """估算送达时间"""
    if status == "已签收":
        return "已签收"
    if status == "待发货":
        return "预计 2-4 天"
    return "预计今天送达"
