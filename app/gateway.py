# -*- coding: utf-8 -*-
"""网关层：API Key 鉴权 + 简单限流"""

import time
from collections import defaultdict
from fastapi import HTTPException, Request
from loguru import logger
from app.config import settings

# ── API Key 鉴权 ──────────────────────────────────────────────

VALID_KEYS = {
    "sk-intellidesk-demo": "demo",
    "sk-intellidesk-admin": "admin",
}


def check_auth(request: Request):
    """验证 API Key（从 Header 或 Query 参数读取）"""
    # 健康检查和文档接口免鉴权
    if request.url.path in ("/api/health", "/docs", "/openapi.json", "/redoc"):
        return

    # localhost/测试环境免鉴权
    if request.client and request.client.host in ("127.0.0.1", "localhost", "testclient"):
        return

    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if not api_key or api_key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="缺少或无效的 API Key。请在 Header 中添加 X-API-Key")


# ── 简单限流（滑动窗口）──────────────────────────────────────

_rate_limits: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 30   # 每分钟最多请求数
RATE_WINDOW = 60  # 窗口秒数


def check_rate_limit(request: Request):
    """基于 IP 的简单限流"""
    if request.url.path in ("/api/health", "/docs"):
        return

    client_ip = request.client.host if request.client else "unknown"
    if client_ip in ("127.0.0.1", "localhost", "testclient"):
        return
    now = time.time()
    window_start = now - RATE_WINDOW

    # 清理过期记录
    _rate_limits[client_ip] = [t for t in _rate_limits[client_ip] if t > window_start]

    if len(_rate_limits[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")

    _rate_limits[client_ip].append(now)
