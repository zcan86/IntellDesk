# -*- coding: utf-8 -*-
"""MCP Client — 连接远程 McpToolServer

通过 HTTP 协议发现并调用工具，将远程工具封装为 LangChain Tool。

远程 MCP Server: http://127.0.0.1:8100
协议: GET /mcp/tools  → 发现工具
      POST /mcp/call → 执行工具
"""

import json
import httpx
from langchain.tools import tool
from loguru import logger
from app.config import settings


def _build_tool(tool_def: dict, server_url: str):
    """将远程工具定义封装为 LangChain Tool"""
    t_name = tool_def["name"]
    t_desc = tool_def.get("description", "")

    @tool(t_name, description=t_desc)
    def _wrapper(**kwargs) -> str:
        try:
            resp = httpx.post(
                f"{server_url}/mcp/call",
                json={"name": t_name, "arguments": kwargs},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            texts = [item["text"] for item in data.get("content", []) if item.get("type") == "text"]
            return "\n".join(texts) if texts else json.dumps(data)
        except Exception as e:
            logger.error(f"MCP 调用失败 [{t_name}]: {e}")
            return f"工具调用失败: {str(e)[:200]}"

    return _wrapper


def load_mcp_tools(server_url: str | None = None) -> list:
    """连接远程 MCP Server，加载全部工具

    Args:
        server_url: MCP Server 地址，默认从配置读取
    """
    if server_url is None:
        server_url = getattr(settings, "MCP_SERVER_URL", "http://127.0.0.1:8100")

    logger.info(f"  连接远程 MCP Server: {server_url}")

    try:
        resp = httpx.get(f"{server_url}/mcp/tools", timeout=10)
        resp.raise_for_status()
        tools_def = resp.json().get("tools", [])
    except Exception as e:
        logger.error(f"  连接失败: {e}")
        return []

    all_tools = [_build_tool(td, server_url) for td in tools_def]

    for t in all_tools:
        logger.info(f"    ✓ {t.name}")

    logger.info(f"  远程 MCP: 加载 {len(all_tools)} 个工具")
    return all_tools


# ── 同步包装 ──────────────────────────────────────────────────

def load_mcp_tools_sync(server_url: str | None = None) -> list:
    """MCP 工具加载 — 同步版本

    load_mcp_tools 本身就是同步的（httpx sync client），
    这个别名用于明确区分同步/异步调用场景。
    """
    return load_mcp_tools(server_url)
