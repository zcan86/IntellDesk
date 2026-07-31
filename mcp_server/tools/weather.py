# -*- coding: utf-8 -*-
"""天气工具 — Open-Meteo 免费 API"""

import requests


def _weather_code_to_text(code: int) -> str:
    m = {0: "晴天 ☀️", 1: "大部晴朗 🌤", 2: "多云 ⛅", 3: "阴天 ☁️",
         45: "有雾 🌫", 48: "雾凇 🌫", 61: "小雨 🌧", 63: "中雨 🌧",
         65: "大雨 🌧", 71: "小雪 ❄️", 73: "中雪 ❄️", 75: "大雪 ❄️",
         80: "阵雨 ⛈", 95: "雷暴 ⛈"}
    return m.get(code, f"未知（码{code}）")


def get_weather(city: str) -> str:
    """查询城市天气"""
    try:
        g = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh"},
            timeout=10, headers={"User-Agent": "McpToolServer/1.0"},
        ).json()
        results = g.get("results", [])
        if not results:
            return f"未找到「{city}」的位置信息。"

        r = results[0]
        lat, lon, name = r["latitude"], r["longitude"], r.get("name", city)
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "Asia/Shanghai", "forecast_days": 1,
            },
            timeout=10, headers={"User-Agent": "McpToolServer/1.0"},
        ).json()
        c, d = w.get("current", {}), w.get("daily", {})
        return (
            f"🌍 {name} 当前天气：\n"
            f"  天气状况：{_weather_code_to_text(c.get('weather_code', 0))}\n"
            f"  当前温度：{c.get('temperature_2m', '?')}°C\n"
            f"  今日最高：{d.get('temperature_2m_max', ['?'])[0]}°C / "
            f"最低：{d.get('temperature_2m_min', ['?'])[0]}°C\n"
            f"  湿度：{c.get('relative_humidity_2m', '?')}%\n"
            f"  风速：{c.get('wind_speed_10m', '?')} km/h"
        )
    except Exception as e:
        return f"天气查询失败: {str(e)[:200]}"
