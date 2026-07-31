#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""IntelliDesk MCP Server — 工具调用唯一入口

所有 Agent 工具通过此 Server 暴露，Agent 不直接 import 工具代码。

启动: python mcp_server/server.py → http://127.0.0.1:8100
接口: GET /mcp/tools  |  POST /mcp/call  |  GET /health
"""

import sys
from pathlib import Path

# 将 IntelliDesk 项目根目录加入 path，以便导入 app/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from loguru import logger

# ── 从 IntelliDesk 导入全部工具 ──────────────────────────────
from app.tools.knowledge_search import search_knowledge_base
from app.tools.builtin_tools import get_weather, calculator, get_current_time
from app.tools.ecommerce import query_order, track_delivery, return_guide, product_search

# 多模态工具（需要 VLM Key，不可用时不影响其他工具）
try:
    from app.tools.multimodal import recognize_image, transcribe_audio
except Exception:
    recognize_image = None
    transcribe_audio = None

# 知识库初始化
from app.rag.loader import build_index

app = FastAPI(title="IntelliDesk MCP Server", version="3.3.0")

# ── 工具注册表 ──────────────────────────────────────────────
TOOL_REGISTRY = {
    "search_knowledge_base": lambda **args: search_knowledge_base.invoke(args.get("query", "")),
    "query_order": lambda **args: query_order.invoke(args.get("order_id", "")),
    "track_delivery": lambda **args: track_delivery.invoke(args.get("order_id", "")),
    "return_guide": lambda **args: return_guide.invoke(args.get("reason", "")),
    "product_search": lambda **args: product_search.invoke(args.get("keyword", "")),
    "get_weather": lambda **args: get_weather.invoke(args.get("city", "")),
    "calculator": lambda **args: calculator.invoke(args.get("expression", "")),
    "get_current_time": lambda **args: get_current_time.invoke({}),
}

if recognize_image:
    TOOL_REGISTRY["recognize_image"] = lambda **args: recognize_image.invoke(args.get("image_path", ""))

if transcribe_audio:
    TOOL_REGISTRY["transcribe_audio"] = lambda **args: transcribe_audio.invoke(args.get("audio_path", ""))

# ── 工具定义（MCP 格式）─────────────────────────────────────
TOOLS = [
    {"name": "search_knowledge_base", "description": "检索知识库。查询退换货政策、配送规则、FAQ等。",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "query_order", "description": "查询订单状态。用户提供订单号时调用。",
     "inputSchema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}},
    {"name": "track_delivery", "description": "查询物流轨迹。用户询问快递到哪了时调用。",
     "inputSchema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}},
    {"name": "return_guide", "description": "退换货流程指引。用户询问如何退货/换货时调用。",
     "inputSchema": {"type": "object", "properties": {"reason": {"type": "string"}}}},
    {"name": "product_search", "description": "搜索耐克鞋款。用户询问鞋子推荐/价格时调用。",
     "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}}, "required": ["keyword"]}},
    {"name": "get_weather", "description": "查询城市天气。",
     "inputSchema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}},
    {"name": "calculator", "description": "数学计算。",
     "inputSchema": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}},
    {"name": "get_current_time", "description": "获取当前时间。",
     "inputSchema": {"type": "object", "properties": {}}},
]

if recognize_image:
    TOOLS.append({"name": "recognize_image", "description": "识别图片中的商品。用户上传图片时调用。",
                  "inputSchema": {"type": "object", "properties": {"image_path": {"type": "string"}}, "required": ["image_path"]}})

if transcribe_audio:
    TOOLS.append({"name": "transcribe_audio", "description": "语音转文字。用户发送语音时调用。",
                  "inputSchema": {"type": "object", "properties": {"audio_path": {"type": "string"}}, "required": ["audio_path"]}})

# ── MCP 端点 ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "IntelliDesk MCP Server", "tools": len(TOOL_REGISTRY)}

@app.get("/mcp/tools")
async def list_tools():
    return {"tools": TOOLS}

class CallToolRequest(BaseModel):
    name: str
    arguments: dict = {}

@app.post("/mcp/call")
async def call_tool(req: CallToolRequest):
    handler = TOOL_REGISTRY.get(req.name)
    if not handler:
        raise HTTPException(404, f"未知工具: {req.name}")
    try:
        result = handler(**req.arguments)
        return {"content": [{"type": "text", "text": result}]}
    except Exception as e:
        raise HTTPException(500, str(e)[:500])

# ── 启动 ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    logger.info("IntelliDesk MCP Server 启动中...")
    build_index()
    logger.info(f"已注册 {len(TOOL_REGISTRY)} 个工具")
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
