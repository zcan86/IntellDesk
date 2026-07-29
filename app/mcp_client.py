# -*- coding: utf-8 -*-
"""MCP Client — HTTP transport

连接 MCP Server 的 HTTP 接口，获取工具列表并封装为 LangChain Tool。

MCP 协议核心流程：
  GET  /mcp/tools  → 发现工具（name + description + inputSchema）
  POST /mcp/call   → 调用工具（name + arguments → content）

架构价值：工具定义与 Agent 解耦。
  - 直接模式：from app.tools import tool → 硬编码依赖
  - MCP 模式：HTTP 发现 → 工具可独立部署、独立扩缩容、跨语言复用
"""

import json
from typing import Any

import httpx
from langchain.tools import tool
from loguru import logger

from app.config import settings


def _build_langchain_tool(tool_def: dict, server_url: str) -> callable:
    """将 MCP 工具定义封装为 LangChain @tool

    Args:
        tool_def: MCP 工具定义 {"name": "...", "description": "...", "inputSchema": {...}}
        server_url: MCP Server 地址

    Returns:
        LangChain Tool 对象
    """
    t_name = tool_def["name"]
    t_desc = tool_def.get("description", "")

    @tool(t_name, description=t_desc)
    def _mcp_wrapper(**kwargs) -> str:
        """调用远程 MCP Server 执行工具"""
        try:
            resp = httpx.post(
                f"{server_url}/mcp/call",
                json={"name": t_name, "arguments": kwargs},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            # 提取 text content
            texts = []
            for item in data.get("content", []):
                if item.get("type") == "text":
                    texts.append(item["text"])
            return "\n".join(texts) if texts else json.dumps(data)
        except Exception as e:
            logger.error(f"MCP 工具 {t_name} 调用失败: {e}")
            return f"工具调用失败: {str(e)[:200]}"

    return _mcp_wrapper


def load_mcp_tools(server_url: str | None = None) -> list:
    """从 MCP Server 加载工具列表并封装为 LangChain Tool

    Args:
        server_url: MCP Server 地址，默认 http://127.0.0.1:8100

    Returns:
        LangChain Tool 列表
    """
    if server_url is None:
        server_url = getattr(settings, "MCP_SERVER_URL", "http://127.0.0.1:8100")

    logger.info(f"  连接 MCP Server: {server_url}")

    try:
        resp = httpx.get(f"{server_url}/mcp/tools", timeout=10)
        resp.raise_for_status()
        tools_def = resp.json().get("tools", [])
    except Exception as e:
        logger.error(f"  连接失败: {e}")
        return []

    all_tools = []
    for td in tools_def:
        lc_tool = _build_langchain_tool(td, server_url)
        all_tools.append(lc_tool)
        logger.info(f"    ✓ {td['name']}")

    logger.info(f"  MCP 模式：加载 {len(all_tools)} 个工具")
    return all_tools
