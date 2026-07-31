# -*- coding: utf-8 -*-
"""IntelliDesk — FastAPI 后端入口（纯 API，前后端分离）

启动: python main.py  →  http://0.0.0.0:8000
前端: cd frontend && npm run dev  →  http://localhost:5173
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.routers import chat
from app.gateway import check_auth, check_rate_limit


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动 / 关闭生命周期"""
    logger.info(f"IntelliDesk API 启动 → http://{settings.HOST}:{settings.PORT}")
    logger.info(f"LLM 模型: {settings.DEEPSEEK_MODEL_NAME}")

    try:
        from app.rag.loader import build_index
        logger.info("初始化知识库索引...")
        build_index()
    except Exception as e:
        logger.warning(f"知识库索引初始化失败: {e}")

    try:
        from app.database import init_db
        init_db()
    except Exception as e:
        logger.warning(f"数据库初始化失败: {e}")

    yield
    logger.info("IntelliDesk 已关闭")


app = FastAPI(
    title="IntelliDesk API — 多智能体电商客服",
    version="3.3.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# 网关中间件
@app.middleware("http")
async def gateway_middleware(request, call_next):
    check_auth(request)
    check_rate_limit(request)
    return await call_next(request)


# API 路由
app.include_router(chat.router)


# ── 直接运行 ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info",
    )
