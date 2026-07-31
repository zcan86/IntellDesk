# -*- coding: utf-8 -*-
"""聊天路由

POST /api/chat              — 普通对话（阶段 1-3，阶段 4 增加 session 记忆）
POST /api/chat/stream       — SSE 流式对话（阶段 4 新增）
POST /api/documents/reindex — 重建知识库索引
"""

import json
import uuid

import json as json_module
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from app.agent import create_intellidesk_agent
from app.config import settings
from app.rag.loader import build_index, get_index_status
from app.agents.orchestrator import get_orchestrator, reset_orchestrator
from app.tools.multimodal import recognize_image, transcribe_audio, save_upload

router = APIRouter(prefix="/api", tags=["chat"])

# ── 请求 / 响应模型 ──────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="用户消息")
    session_id: str | None = Field(None, description="会话 ID，不传则自动创建新会话")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Agent 回复")
    session_id: str = Field(..., description="会话 ID，前端需保存用于后续请求")


class ReindexResponse(BaseModel):
    status: str
    message: str
    chunk_count: int | None = None


# ── Agent 单例 ──────────────────────────────────────────────
_agent = None


def get_agent():
    """延迟初始化 Agent — 工具全部通过 MCP Server 调用"""
    global _agent
    if _agent is None:
        logger.info("正在连接 MCP Server 加载工具...")
        from app.mcp_client import load_mcp_tools_sync
        tools = load_mcp_tools_sync()
        if not tools:
            raise RuntimeError(
                "MCP Server 未连接！请先启动: python mcp_server/server.py"
            )
        _agent = create_intellidesk_agent(tools=tools)
        logger.info(f"Agent 就绪（MCP: {len(tools)} 工具）")
    return _agent


def reset_agent():
    """重置 Agent"""
    global _agent
    _agent = None
    logger.info("Agent 已重置")


# ── 健康检查 ────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    status = get_index_status()
    kb_str = f"{status['chunk_count']} chunks" if status["ready"] else "not indexed"
    return {"status": "ok", "service": "IntelliDesk", "knowledge_base": kb_str}


# ── 普通对话接口（支持 Memory）─────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """普通对话接口（非流式，支持多轮记忆）

    - 首次调用不传 session_id，服务端自动创建新会话
    - 后续调用传入 session_id 以在同一会话中继续对话
    """
    try:
        agent = get_agent()
        session_id = req.session_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        logger.info(f"[{session_id[:8]}] 收到消息: {req.message[:100]}...")

        result = agent.invoke(
            {"messages": [("user", req.message)]},
            config=config,
        )

        # 提取最后一条 AI 消息
        messages = result.get("messages", [])
        reply = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.type == "ai" and msg.content:
                reply = msg.content
                break

        if not reply:
            reply = "抱歉，我暂时无法处理您的请求，请稍后再试。"

        logger.info(f"[{session_id[:8]}] 回复: {reply[:100]}...")
        return ChatResponse(reply=reply.strip(), session_id=session_id)

    except Exception as e:
        logger.exception(f"Agent 处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"处理请求时出错: {str(e)}")


# ── SSE 流式对话接口（阶段 4 核心）─────────────────────────────


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话接口

    实时推送 Agent 的思考和回复过程：

    事件类型：
    - agent_start: 编排器调度专业 Agent
    - agent_end:   专业 Agent 完成处理
    - tool_start:  Agent 开始调用工具
    - tool_end:    工具调用完成
    - token:       LLM 回复的文本片段
    - done:        本次请求处理完成

    前端示例：
        const eventSource = new EventSource('/api/chat/stream', {
            method: 'POST',
            body: JSON.stringify({message: '...', session_id: '...'})
        });
        eventSource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.type === 'token') appendText(data.content);
            if (data.type === 'done') finalize();
        };
    """
    try:
        agent = get_agent()
        session_id = req.session_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        logger.info(f"[{session_id[:8]}] SSE 开始: {req.message[:100]}...")

        # ── 多 Agent 调度 ──
        orch = get_orchestrator()
        plan = orch.plan_task(req.message)

        async def event_generator():
            """异步生成器：逐事件推送给前端"""
            # 先发送调度计划
            for agent_name in plan:
                label = {
                    "order": "订单Agent", "return": "售后Agent", "product": "商品Agent",
                    "shipping": "物流Agent", "payment": "支付Agent", "account": "账号Agent",
                    "general": "综合Agent"
                }.get(agent_name, agent_name)
                yield f"data: {json.dumps({'type': 'agent_start', 'agent': label, 'intent': agent_name}, ensure_ascii=False)}\n\n"

            try:
                async for event in agent.astream_events(
                    {"messages": [("user", req.message)]},
                    config=config,
                    version="v2",
                ):
                    kind = event.get("event", "")

                    # ── LLM 输出 token ──
                    if kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            yield f"data: {json.dumps({'type': 'token', 'content': chunk.content}, ensure_ascii=False)}\n\n"

                    # ── 工具开始执行 ──
                    elif kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        logger.info(f"[{session_id[:8]}] 🔧 调用工具: {tool_name}")
                        yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name}, ensure_ascii=False)}\n\n"

                    # ── 工具执行结束 ──
                    elif kind == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name}, ensure_ascii=False)}\n\n"

                # ── Agent 完成 + 轨迹 ──
                for agent_name in reversed(plan):
                    label = {
                        "order": "订单Agent", "return": "售后Agent", "product": "商品Agent",
                        "shipping": "物流Agent", "payment": "支付Agent", "account": "账号Agent",
                        "general": "综合Agent"
                    }.get(agent_name, agent_name)
                    yield f"data: {json.dumps({'type': 'agent_end', 'agent': label}, ensure_ascii=False)}\n\n"

                trace = orch.get_trace()
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'trace': trace}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.exception(f"SSE 流中断: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            },
        )

    except Exception as e:
        logger.exception(f"SSE 初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"流式请求失败: {str(e)}")


# ── 多模态上传 ──────────────────────────────────────────────

@router.post("/chat/upload")
async def upload_and_chat(
    file: UploadFile = File(...),
    message: str = Form(""),
    session_id: str | None = Form(None),
):
    """上传图片/音频并对话

    用户上传文件后，自动调用识别工具转为文字描述，
    再将文字作为消息发送给 Agent。
    """
    try:
        content = await file.read()
        filepath = save_upload(content, file.filename or "upload")
        ext = Path(filepath).suffix.lower()

        # 根据文件类型选择工具
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            extra_msg = recognize_image.invoke(filepath)
            msg_type = "图片识别"
        elif ext in (".mp3", ".wav", ".m4a", ".ogg", ".webm"):
            extra_msg = transcribe_audio.invoke(filepath)
            msg_type = "语音转文字"
        else:
            return {"error": f"不支持的文件格式: {ext}"}

        # 拼装消息
        full_msg = message
        if extra_msg and "失败" not in extra_msg and "不可用" not in extra_msg:
            full_msg = f"[{msg_type}结果] {extra_msg}\n\n[用户补充] {message}" if message else f"[{msg_type}结果] {extra_msg}"
        elif message:
            full_msg = message

        logger.info(f"多模态输入: {msg_type} → {str(filepath)}")

        # 走流式对话
        agent = get_agent()
        session_id = session_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": session_id}}

        def sse(data: dict) -> str:
            """生成 SSE 格式字符串"""
            return f"data: {json_module.dumps(data, ensure_ascii=False)}\n\n"

        async def event_generator():
            yield sse({"type": "token", "content": f"[{msg_type}] {file.filename}\n"})
            try:
                async for event in agent.astream_events(
                    {"messages": [("user", full_msg)]}, config=config, version="v2"
                ):
                    kind = event.get("event", "")
                    if kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            yield sse({"type": "token", "content": chunk.content})
                    elif kind == "on_tool_start":
                        yield sse({"type": "tool_start", "tool": event.get("name", "?")})
                    elif kind == "on_tool_end":
                        yield sse({"type": "tool_end", "tool": event.get("name", "?")})
            except Exception as e:
                yield sse({"type": "error", "message": str(e)[:200]})
            yield sse({"type": "done", "session_id": session_id})

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.exception(f"多模态处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 文档管理接口 ──────────────────────────────────────────────


@router.post("/documents/reindex", response_model=ReindexResponse)
async def reindex_documents():
    """重建知识库索引"""
    try:
        logger.info("收到重建索引请求")
        success = build_index(force_rebuild=True)

        if not success:
            return ReindexResponse(
                status="warning",
                message="没有找到可索引的文档，请检查 docs/products/ 目录",
                chunk_count=0,
            )

        reset_agent()
        status = get_index_status()
        return ReindexResponse(
            status="success",
            message=f"索引重建完成，共 {status['chunk_count']} 个文档块",
            chunk_count=status["chunk_count"],
        )

    except Exception as e:
        logger.exception(f"重建索引失败: {e}")
        raise HTTPException(status_code=500, detail=f"重建索引失败: {str(e)}")
