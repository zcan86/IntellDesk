#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MCP Server: 知识库检索 Skill"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server import Server, InitializationOptions
from mcp import stdio_server
from mcp.types import Tool, TextContent

from app.rag.loader import build_index, search_knowledge

build_index()

# ── 工具列表 ──────────────────────────────────────────────────
TOOLS = [
    Tool(
        name="search_knowledge_base",
        description="检索 IntelliDesk 产品知识库。当用户询问产品功能、计费、API 等问题时调用。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言搜索查询"}
            },
            "required": ["query"],
        },
    )
]


async def list_tools_handler(ctx, params=None):
    """返回工具列表"""
    from mcp.types import ListToolsResult
    return ListToolsResult(tools=TOOLS)


async def call_tool_handler(ctx, params):
    """执行工具"""
    name = params.name
    arguments = params.arguments or {}

    if name == "search_knowledge_base":
        query = arguments.get("query", "")
        results = search_knowledge(query)
        if not results:
            return [TextContent(type="text", text="知识库中未找到相关信息。")]
        lines = []
        for i, r in enumerate(results, 1):
            section = f"{r['h1']} > {r['h2']}" if r.get("h2") else r.get("h1", "")
            lines.append(f"【来源 {i}】{r['source']} | 章节：{section}\n{r['content']}")
        return [TextContent(type="text", text="\n\n---\n\n".join(lines))]

    return [TextContent(type="text", text=f"未知工具: {name}")]


# ── Server ────────────────────────────────────────────────────
server = Server(
    "intellidesk-knowledge",
    on_list_tools=list_tools_handler,
    on_call_tool=call_tool_handler,
)


async def main():
    init_opts = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_opts)


if __name__ == "__main__":
    asyncio.run(main())
