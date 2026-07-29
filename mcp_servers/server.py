#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MCP Server — HTTP transport

将 IntelliDesk 的 4 个工具以 MCP 协议暴露为 HTTP 接口：

GET  /mcp/tools          → 返回工具列表（name + description + inputSchema）
POST /mcp/call           → 执行工具调用（{"name": "...", "arguments": {...}}）

可作为独立进程运行，也可挂载到 FastAPI 主应用。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ── 复用已有工具逻辑 ──────────────────────────────────────────
from app.rag.loader import build_index, search_knowledge
from app.tools.builtin_tools import get_weather as _weather_fn
from app.tools.builtin_tools import calculator as _calc_fn
from app.tools.builtin_tools import get_current_time as _time_fn

build_index()

# ── FastAPI ────────────────────────────────────────────────────
mcp_app = FastAPI(title="IntelliDesk MCP Server", version="2.0.0")

# ── 工具定义 ──────────────────────────────────────────────────
TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": "检索 IntelliDesk 产品知识库。查询产品功能、计费、API、使用方法等问题时调用。",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "自然语言搜索查询"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_weather",
        "description": "查询指定城市的当前天气。例如：'北京今天天气怎么样？'",
        "inputSchema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名称，中英文均可"}},
            "required": ["city"],
        },
    },
    {
        "name": "calculator",
        "description": "执行数学计算。支持加减乘除、乘方、sqrt、sin、cos、pi 等。",
        "inputSchema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "数学表达式"}},
            "required": ["expression"],
        },
    },
    {
        "name": "get_current_time",
        "description": "获取当前日期和时间。用户询问时间、日期、星期几时调用。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ── MCP 协议接口 ──────────────────────────────────────────────

@mcp_app.get("/mcp/tools")
async def list_tools():
    """MCP list_tools：返回所有可用工具"""
    return {"tools": TOOLS}


class CallToolRequest(BaseModel):
    name: str
    arguments: dict = {}


@mcp_app.post("/mcp/call")
async def call_tool(req: CallToolRequest):
    """MCP call_tool：执行指定工具"""
    name = req.name
    args = req.arguments

    if name == "search_knowledge_base":
        results = search_knowledge(args.get("query", ""))
        if not results:
            return {"content": [{"type": "text", "text": "知识库中未找到相关信息。"}]}
        lines = []
        for i, r in enumerate(results, 1):
            section = f"{r['h1']} > {r['h2']}" if r.get("h2") else r.get("h1", "")
            lines.append(f"【来源 {i}】{r['source']} | {section}\n{r['content']}")
        return {"content": [{"type": "text", "text": "\n\n---\n\n".join(lines)}]}

    elif name == "get_weather":
        result = _weather_fn.invoke(args.get("city", ""))
        return {"content": [{"type": "text", "text": result}]}

    elif name == "calculator":
        result = _calc_fn.invoke(args.get("expression", ""))
        return {"content": [{"type": "text", "text": result}]}

    elif name == "get_current_time":
        result = _time_fn.invoke({})
        return {"content": [{"type": "text", "text": result}]}

    raise HTTPException(404, f"未知工具: {name}")


# ── 直接运行 ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp_app, host="127.0.0.1", port=8100, log_level="info")
