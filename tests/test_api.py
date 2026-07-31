# -*- coding: utf-8 -*-
"""API 接口测试（需要 MCP Server 运行）"""

import sys
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

_mcp_process = None


@pytest.fixture(scope="session", autouse=True)
def mcp_server():
    """自动启动 MCP Server（测试会话级别）"""
    global _mcp_process
    project_root = Path(__file__).parent.parent
    _mcp_process = subprocess.Popen(
        [sys.executable, str(project_root / "mcp_server" / "server.py")],
        cwd=str(project_root),
    )
    time.sleep(8)  # 等待 MCP Server 启动（含索引构建）
    yield
    _mcp_process.terminate()
    _mcp_process.wait()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_check():
    """GET /api/health 返回 200"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "IntelliDesk"
        assert "knowledge_base" in data


@pytest.mark.anyio
async def test_chat_without_tools():
    """POST /api/chat 简单对话（不应调工具）"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"message": "你好"})
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "session_id" in data
        assert len(data["reply"]) > 0


@pytest.mark.anyio
async def test_chat_empty_message():
    """空消息应返回 422"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chat", json={"message": ""})
        assert resp.status_code == 422


@pytest.mark.anyio
async def test_chat_session_memory():
    """多轮对话在同一 session 内保持记忆"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 第一轮
        r1 = await client.post("/api/chat", json={"message": "我叫王五"})
        sid = r1.json()["session_id"]

        # 第二轮（同一 session）
        r2 = await client.post("/api/chat", json={
            "message": "我叫什么名字？",
            "session_id": sid,
        })
        reply = r2.json()["reply"]
        assert "王五" in reply or "你叫" in reply


@pytest.mark.anyio
async def test_documents_reindex():
    """POST /api/documents/reindex 返回成功"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/documents/reindex")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["chunk_count"] > 0
