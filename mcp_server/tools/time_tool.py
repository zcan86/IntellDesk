# -*- coding: utf-8 -*-
"""时间工具"""

from datetime import datetime


def get_current_time(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """返回当前日期和时间"""
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return f"🕐 当前时间：{now.strftime(fmt)}\n   {weekdays[now.weekday()]}"
