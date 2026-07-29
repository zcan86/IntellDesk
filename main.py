# -*- coding: utf-8 -*-
"""IntelliDesk — FastAPI 应用入口

启动方式：
    python main.py
    或
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config import settings
from app.routers import chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动 / 关闭生命周期

    启动时自动构建知识库索引，确保 Agent 立即可用。
    """
    logger.info(f"IntelliDesk 启动 → http://{settings.HOST}:{settings.PORT}")
    logger.info(f"LLM 模型: {settings.DEEPSEEK_MODEL_NAME}")

    # ── 启动时自动构建向量索引 ──
    try:
        from app.rag.loader import build_index
        logger.info("正在初始化知识库索引...")
        build_index()
        logger.info("知识库索引就绪")
    except Exception as e:
        logger.warning(f"知识库索引初始化失败（服务仍可启动）: {e}")

    yield

    logger.info("IntelliDesk 已关闭")


app = FastAPI(
    title="速购电商 — 多智能体客服",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router)

# ── 静态文件 & SPA ──────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"

# 挂载 /static 目录，让 CSS/JS 可被浏览器加载
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    """返回前端首页"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>IntelliDesk API 已启动</h1>", status_code=200)


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
