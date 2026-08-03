# -*- coding: utf-8 -*-
"""聊天路由

POST /api/chat              — 普通对话（阶段 1-3，阶段 4 增加 session 记忆）
POST /api/chat/stream       — SSE 流式对话（阶段 4 新增）
POST /api/documents/reindex — 重建知识库索引
"""

import json
import uuid

import asyncio
import json as json_module
from pathlib import Path

from langchain_core.messages import SystemMessage

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

# LLM 并发控制信号量
_sem: asyncio.Semaphore | None = None
_waiters = 0


def _sem_get() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(settings.LLM_MAX_CONCURRENT)
    return _sem

from app.agent import create_intellidesk_agent
from app.config import settings
from app.rag.loader import build_index, get_index_status
from app.router import route, analyze_request
from app.stats import record as stats_record
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
_session_timestamps: dict[str, float] = {}  # thread_id → 创建时间


def _build_state_input(text: str) -> dict:
    """构建 Agent 初始状态：播种订单上下文 / 意图到显式 state 字段

    - order_context / intent 写入 AgentState（显式建模，供工具/后续读取）
    - 同时以「【订单上下文】」SystemMessage 注入对话，
      LLM 直接读取，不再从历史文本里推断订单号（跨轮记忆天然保留）
    """
    ctx = analyze_request(text)
    state: dict = {"messages": [("user", text)]}
    if ctx.get("order_id") or ctx["intent"] != "general":
        state["order_context"] = ctx
        state["intent"] = ctx["intent"]
        state["messages"].insert(
            0,
            SystemMessage(
                content=f"【订单上下文】{json.dumps(ctx, ensure_ascii=False)}"
            ),
        )
    return state

import time as _time


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
    global _agent, _session_timestamps
    _agent = None
    _session_timestamps.clear()
    logger.info("Agent 已重置")


def _prune_session(agent, thread_id: str) -> bool:
    """检查并清理过期/超长会话

    Returns:
        True = 会话已被清除，需要创建新会话
    """
    now = _time.time()

    # 1. TTL 过期检查
    created = _session_timestamps.get(thread_id)
    if created and (now - created) > settings.SESSION_TTL_MINUTES * 60:
        try:
            agent.update_state(
                {"configurable": {"thread_id": thread_id}},
                {"messages": []},
            )
        except Exception:
            pass
        _session_timestamps.pop(thread_id, None)
        logger.info(f"[{thread_id[:8]}] 会话过期，已清除")
        return True

    # 2. 轮数裁剪
    try:
        state = agent.get_state({"configurable": {"thread_id": thread_id}})
        if state and state.values:
            msgs = list(state.values.get("messages", []))
            human_ai = [m for m in msgs if hasattr(m, "type") and m.type in ("human", "ai")]
            if len(human_ai) >= settings.SESSION_MAX_TURNS * 2:
                system_msgs = [m for m in msgs if hasattr(m, "type") and m.type == "system"]
                trimmed = system_msgs + human_ai[-(settings.SESSION_MAX_TURNS * 2):]
                agent.update_state(
                    {"configurable": {"thread_id": thread_id}},
                    {"messages": trimmed},
                )
                logger.info(f"[{thread_id[:8]}] 记忆裁剪: {len(human_ai)}→{settings.SESSION_MAX_TURNS*2}")
    except Exception:
        pass

    return False


# ── 健康检查 ────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    status = get_index_status()
    kb_str = f"{status['chunk_count']} chunks" if status["ready"] else "not indexed"
    return {
        "status": "ok", "service": "IntelliDesk",
        "knowledge_base": kb_str,
        "queue": {
            "max_concurrent": settings.LLM_MAX_CONCURRENT,
            "waiting": _waiters or 0,
        },
    }


# ── 普通对话接口（支持 Memory）─────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """普通对话接口（非流式，支持多轮记忆）

    - 首次调用不传 session_id，服务端自动创建新会话
    - 后续调用传入 session_id 以在同一会话中继续对话
    """
    try:
        t0 = _time.time()
        session_id = req.session_id or str(uuid.uuid4())

        cached = route(req.message)
        if cached:
            reply, source = cached
            stats_record(session_id, source, len(req.message), _time.time() - t0)
            # 写入 Agent 记忆，让后续对话能引用上下文
            try:
                from langchain_core.messages import HumanMessage, AIMessage
                agent = get_agent()
                agent.update_state(
                    {"configurable": {"thread_id": session_id}},
                    {"messages": [HumanMessage(content=req.message), AIMessage(content=reply)]},
                )
            except Exception as e:
                logger.warning(f"写入记忆失败: {e}")
            return ChatResponse(reply=reply, session_id=session_id)

        # ── Agent ──
        agent = get_agent()
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": settings.AGENT_MAX_ITERATIONS * 2 + 3,
        }

        if session_id not in _session_timestamps:
            _session_timestamps[session_id] = _time.time()

        expired = _prune_session(agent, session_id)
        if expired:
            _session_timestamps[session_id] = _time.time()

        logger.info(f"[{session_id[:8]}] Agent: {req.message[:100]}...")

        # LLM 并发控制：排队 + 超时
        global _waiters
        queue_start = _time.time()
        _waiters += 1
        async with _sem_get():
            _waiters -= 1
            wait_ms = (_time.time() - queue_start) * 1000
            if wait_ms > 100:
                logger.info(f"[{session_id[:8]}] LLM排队等待: {wait_ms:.0f}ms (并发{settings.LLM_MAX_CONCURRENT})")

            try:
                result = await asyncio.wait_for(
                    agent.ainvoke(
                        _build_state_input(req.message),
                        config=config,
                    ),
                    timeout=settings.LLM_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                raise HTTPException(
                    status_code=503,
                    detail=f"服务繁忙，请稍后重试（超时 {settings.LLM_TIMEOUT_SECONDS}s）。当前排队: {_waiters or 0} 人",
                )

        messages = result.get("messages", [])
        reply = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.type == "ai" and msg.content:
                reply = msg.content
                break

        if not reply:
            reply = "抱歉，我暂时无法处理您的请求，请稍后再试。"

        tokens_est = len(reply) // 2  # 粗略估算（中文约2字符=1token）
        stats_record(session_id, "agent", len(req.message), _time.time() - t0, tokens_est)
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
        session_id = req.session_id or str(uuid.uuid4())

        # ── 路由检查 ──
        cached = route(req.message)
        if cached:
            reply, source = cached
            logger.info(f"[{session_id[:8]}] SSE路由命中[{source}]: {req.message[:50]}")

            async def cached_generator():
                yield f"data: {json.dumps({'type': 'token', 'content': reply}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"
            return StreamingResponse(cached_generator(), media_type="text/event-stream")

        # ── Agent ──
        agent = get_agent()
        config = {
            "configurable": {"thread_id": session_id},
            "recursion_limit": settings.AGENT_MAX_ITERATIONS * 2 + 3,
        }

        logger.info(f"[{session_id[:8]}] SSE Agent: {req.message[:100]}...")

        async def event_generator():
            """异步生成器：逐事件推送给前端"""
            try:
                async for event in agent.astream_events(
                    _build_state_input(req.message),
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

                # ── 完成 ──
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"

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
                    _build_state_input(full_msg), config=config, version="v2"
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


# ── 用户画像 ────────────────────────────────────────────────

@router.get("/profile/{user_id}")
async def user_profile(user_id: str):
    """用户画像：基本信息 + 订单汇总 + 偏好"""
    from app.database import get_user, get_user_orders

    user = get_user(user_id)
    if not user:
        return {"error": "用户不存在"}

    orders = get_user_orders(user_id)
    total_spent = sum(o["price"] for o in orders)
    status_count = {}
    for o in orders:
        s = o["status"]
        status_count[s] = status_count.get(s, 0) + 1

    # 偏好分析
    products = [o["product_name"] for o in orders]
    favorite = max(set(products), key=products.count) if products else "暂无"

    # 可退换订单
    from datetime import datetime
    returnable = []
    for o in orders:
        if o["status"] == "已签收":
            try:
                sign = datetime.strptime(o["created_at"][:10], "%Y-%m-%d")
                days = (datetime.now() - sign).days
                if days <= 7:
                    returnable.append(o["order_id"])
            except Exception:
                pass

    return {
        "user": user,
        "total_orders": len(orders),
        "total_spent": total_spent,
        "favorite_product": favorite,
        "status_breakdown": status_count,
        "returnable_orders": returnable,
        "member_level": (
            "钻石" if total_spent >= 10000 else
            "金卡" if total_spent >= 5000 else
            "银卡" if total_spent >= 2000 else "普通"
        ),
    }


# ── 统计 ────────────────────────────────────────────────────

@router.get("/stats")
async def api_stats():
    """Token 用量 + 请求统计"""
    from app.stats import get_summary
    return get_summary()


# ── 用户反馈 ────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    session_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str = ""


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """提交服务评价"""
    from app.database import save_feedback
    return save_feedback(req.session_id, req.rating, req.comment)


@router.get("/feedback/stats")
async def feedback_stats():
    """反馈统计"""
    from app.database import get_feedback_stats
    return get_feedback_stats()


# ── 会话管理 ────────────────────────────────────────────────

@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """清除指定会话的记忆"""
    _session_timestamps.pop(session_id, None)
    agent = get_agent()
    try:
        agent.update_state(
            {"configurable": {"thread_id": session_id}},
            {"messages": []},
        )
        return {"status": "ok", "message": f"会话 {session_id[:8]} 已清除"}
    except Exception:
        return {"status": "ok", "message": "会话不存在或已过期"}


# ── 订单查询 API ────────────────────────────────────────────

@router.get("/orders/{user_id}")
async def list_orders(user_id: str):
    """查询用户的所有订单"""
    from app.database import get_user_orders, get_user
    user = get_user(user_id)
    if not user:
        return {"error": "用户不存在", "user_id": user_id}
    orders = get_user_orders(user_id)
    return {"user": user, "orders": orders, "count": len(orders)}


@router.get("/order/{order_id}")
async def order_detail(order_id: str):
    """查询单个订单详情"""
    from app.database import get_order
    order = get_order(order_id)
    if not order:
        return {"error": "订单不存在"}
    return {"order": order}


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
