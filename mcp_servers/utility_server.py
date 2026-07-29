#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MCP Server: 通用工具 Skill（天气 / 计算 / 时间）"""

import asyncio
import sys
from datetime import datetime
from math import sqrt, sin, cos, tan, log, log10, pi, e, ceil, floor

import requests
from mcp.server import Server, InitializationOptions
from mcp import stdio_server
from mcp.types import Tool, TextContent, ListToolsResult


# ── 工具实现 ──────────────────────────────────────────────────

def _weather_code_to_text(code: int) -> str:
    m = {0: "晴天 ☀️", 1: "大部晴朗 🌤", 2: "多云 ⛅", 3: "阴天 ☁️",
         45: "有雾 🌫", 48: "雾凇 🌫", 61: "小雨 🌧", 63: "中雨 🌧",
         65: "大雨 🌧", 71: "小雪 ❄️", 73: "中雪 ❄️", 75: "大雪 ❄️",
         80: "阵雨 ⛈", 95: "雷暴 ⛈"}
    return m.get(code, f"未知（码{code}）")


def _get_weather(city: str) -> str:
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1, "language": "zh"},
                         timeout=10, headers={"User-Agent": "IntelliDesk-MCP/1.0"}).json()
        r = g.get("results", [])
        if not r: return f"未找到「{city}」的位置信息。"
        lat, lon, name = r[0]["latitude"], r[0]["longitude"], r[0].get("name", city)
        w = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": lat, "longitude": lon,
                                 "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                                 "daily": "temperature_2m_max,temperature_2m_min",
                                 "timezone": "Asia/Shanghai", "forecast_days": 1},
                         timeout=10, headers={"User-Agent": "IntelliDesk-MCP/1.0"}).json()
        c, d = w.get("current", {}), w.get("daily", {})
        return (f"🌍 {name} 当前天气：\n  天气状况：{_weather_code_to_text(c.get('weather_code',0))}\n"
                f"  当前温度：{c.get('temperature_2m','?')}°C\n"
                f"  今日最高：{d.get('temperature_2m_max',['?'])[0]}°C / 最低：{d.get('temperature_2m_min',['?'])[0]}°C\n"
                f"  湿度：{c.get('relative_humidity_2m','?')}%\n  风速：{c.get('wind_speed_10m','?')} km/h")
    except Exception as e:
        return f"天气查询失败: {str(e)[:200]}"


def _calculator(expression: str) -> str:
    safe = {"__builtins__": {}, "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "int": int, "float": float,
            "sqrt": sqrt, "sin": sin, "cos": cos, "tan": tan,
            "log": log, "log10": log10, "pi": pi, "e": e, "ceil": ceil, "floor": floor}
    try:
        r = eval(expression, safe, {})
        s = f"{r:.6f}".rstrip("0").rstrip(".") if isinstance(r, float) else str(r)
        return f"📐 {expression} = {s}"
    except SyntaxError: return f"表达式「{expression}」语法错误。"
    except ZeroDivisionError: return "除数不能为零。"
    except Exception as e: return f"计算失败: {str(e)[:200]}"


def _get_current_time(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    n = datetime.now()
    w = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
    return f"🕐 当前时间：{n.strftime(fmt)}\n   {w[n.weekday()]}"


# ── 工具定义 ──────────────────────────────────────────────────
TOOLS = [
    Tool(name="get_weather", description="查询指定城市的当前天气。",
         inputSchema={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}),
    Tool(name="calculator", description="执行数学计算。",
         inputSchema={"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}),
    Tool(name="get_current_time", description="获取当前日期和时间。",
         inputSchema={"type": "object", "properties": {}}),
]

# ── Handler ───────────────────────────────────────────────────

async def list_tools_handler(ctx, params=None):
    return ListToolsResult(tools=TOOLS)


async def call_tool_handler(ctx, params):
    name = params.name
    args = params.arguments or {}
    handlers = {
        "get_weather": lambda: _get_weather(args.get("city", "")),
        "calculator": lambda: _calculator(args.get("expression", "")),
        "get_current_time": lambda: _get_current_time(),
    }
    h = handlers.get(name)
    if h: return [TextContent(type="text", text=h())]
    return [TextContent(type="text", text=f"未知工具: {name}")]


# ── Server ────────────────────────────────────────────────────
server = Server(
    "intellidesk-utility",
    on_list_tools=list_tools_handler,
    on_call_tool=call_tool_handler,
)


async def main():
    init_opts = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_opts)


if __name__ == "__main__":
    asyncio.run(main())
