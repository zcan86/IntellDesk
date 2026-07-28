# -*- coding: utf-8 -*-
"""Agent 内置工具

提供三个通用工具：
- get_weather：查询城市天气（调用 wttr.in 免费 API）
- calculator：安全数学表达式计算
- get_current_time：返回当前日期时间
"""

from datetime import datetime

import requests
from langchain.tools import tool
from loguru import logger


@tool
def get_weather(city: str) -> str:
    """查询指定城市的当前天气状况。

    当用户询问某个城市的天气时，调用此工具。
    例如："北京今天天气怎么样？""上海下雨吗？"

    Args:
        city: 城市名称，中文或英文均可，如"北京""Shanghai""Tokyo"

    Returns:
        该城市当前的天气描述，包含温度、天气状况、湿度、风速
    """
    logger.info(f"🌤 查询天气: {city}")

    try:
        # 1. 先用城市名获取经纬度（Open-Meteo Geocoding API，免费无需 Key）
        geo_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh"},
            timeout=10,
            headers={"User-Agent": "IntelliDesk/1.0"},
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()

        results = geo_data.get("results", [])
        if not results:
            return f"抱歉，未找到「{city}」的位置信息，请确认城市名称是否正确。"

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        name = results[0].get("name", city)

        # 2. 用经纬度获取天气（Open-Meteo Weather API，免费无需 Key）
        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "Asia/Shanghai",
                "forecast_days": 1,
            },
            timeout=10,
            headers={"User-Agent": "IntelliDesk/1.0"},
        )
        weather_resp.raise_for_status()
        wdata = weather_resp.json()

        current = wdata.get("current", {})
        daily = wdata.get("daily", {})

        temp_c = current.get("temperature_2m", "未知")
        humidity = current.get("relative_humidity_2m", "未知")
        wind_speed = current.get("wind_speed_10m", "未知")
        weather_code = current.get("weather_code", 0)

        max_temp = daily.get("temperature_2m_max", ["未知"])[0] if daily.get("temperature_2m_max") else "未知"
        min_temp = daily.get("temperature_2m_min", ["未知"])[0] if daily.get("temperature_2m_min") else "未知"

        # WMO 天气码转中文描述
        weather_desc = _weather_code_to_text(weather_code)

        return (
            f"🌍 {name} 当前天气：\n"
            f"  天气状况：{weather_desc}\n"
            f"  当前温度：{temp_c}°C\n"
            f"  今日最高：{max_temp}°C / 最低：{min_temp}°C\n"
            f"  湿度：{humidity}%\n"
            f"  风速：{wind_speed} km/h"
        )

    except requests.RequestException as e:
        logger.error(f"天气查询失败: {e}")
        return f"天气查询失败，请稍后重试。错误详情: {str(e)[:200]}"
    except Exception as e:
        logger.error(f"天气数据解析失败: {e}")
        return f"天气数据解析失败，请稍后重试。"


def _weather_code_to_text(code: int) -> str:
    """WMO 天气码 → 中文描述"""
    code_map = {
        0: "晴天 ☀️", 1: "大部晴朗 🌤", 2: "多云 ⛅", 3: "阴天 ☁️",
        45: "有雾 🌫", 48: "雾凇 🌫", 51: "小毛毛雨 🌧", 53: "毛毛雨 🌧",
        55: "大毛毛雨 🌧", 61: "小雨 🌧", 63: "中雨 🌧", 65: "大雨 🌧",
        71: "小雪 ❄️", 73: "中雪 ❄️", 75: "大雪 ❄️", 77: "雪粒 ❄️",
        80: "阵雨 ⛈", 81: "中阵雨 ⛈", 82: "大阵雨 ⛈",
        85: "小阵雪 🌨", 86: "大阵雪 🌨", 95: "雷暴 ⛈", 96: "冰雹雷暴 ⛈",
        99: "强雷暴 ⛈",
    }
    return code_map.get(code, f"未知天气（码{code}）")


@tool
def calculator(expression: str) -> str:
    """执行数学计算。

    当用户需要进行数学运算时调用，支持加减乘除、乘方、括号等基本运算。
    例如："123 * 456 等于多少？""计算 (3.14 * 2) ^ 3"

    Args:
        expression: 数学表达式字符串，如 "123 * 456"、"sqrt(16)"、"2 ** 10"

    Returns:
        计算结果
    """
    logger.info(f"🔢 计算: {expression}")

    try:
        # 安全的白名单函数
        safe_globals = {
            "__builtins__": {},
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            "int": int,
            "float": float,
        }

        # 从 math 引入常用函数
        import math
        safe_globals.update({
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "pi": math.pi,
            "e": math.e,
            "ceil": math.ceil,
            "floor": math.floor,
        })

        result = eval(expression, safe_globals, {})

        # 格式化输出
        if isinstance(result, float):
            result_str = f"{result:.6f}".rstrip("0").rstrip(".")
        else:
            result_str = str(result)

        return f"📐 {expression} = {result_str}"

    except SyntaxError:
        return f"表达式「{expression}」语法错误，请输入合法的数学表达式。"
    except ZeroDivisionError:
        return "除数不能为零。"
    except Exception as e:
        return f"计算失败: {str(e)[:200]}"


@tool
def get_current_time(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前的日期和时间。

    当用户询问当前时间、日期、星期几等信息时调用。
    例如："现在几点了？""今天是几号？""今天星期几？"

    Args:
        format_str: 时间格式字符串，一般不需要传，使用默认值即可

    Returns:
        当前日期时间的格式化字符串
    """
    logger.info("🕐 查询当前时间")

    now = datetime.now()
    weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

    return (
        f"🕐 当前时间：{now.strftime(format_str)}\n"
        f"   {weekday_map[now.weekday()]}"
    )
