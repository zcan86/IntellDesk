# -*- coding: utf-8 -*-
"""Token 用量统计 + 请求日志"""

import time
from collections import defaultdict
from loguru import logger

_stats: list[dict] = []


def record(session_id: str, source: str, message_len: int, elapsed: float, tokens: int = 0):
    """记录一次请求"""
    entry = {
        "session": session_id[:8],
        "source": source,        # cache/db/keyword/agent/error
        "msg_len": message_len,
        "elapsed_ms": round(elapsed * 1000),
        "tokens": tokens,
        "time": time.strftime("%H:%M:%S"),
    }
    _stats.append(entry)
    # 只保留最近 1000 条
    if len(_stats) > 1000:
        _stats.pop(0)

    if tokens:
        logger.info(f"  Token: {tokens} | {elapsed:.1f}s | [{source}]")
    else:
        logger.info(f"  {elapsed*1000:.0f}ms | [{source}]")


def get_summary() -> dict:
    """返回统计摘要"""
    if not _stats:
        return {"total": 0, "total_tokens": 0, "sources": {}}

    # 按来源统计
    sources = defaultdict(lambda: {"count": 0, "total_ms": 0, "total_tokens": 0})
    for s in _stats:
        src = s["source"]
        sources[src]["count"] += 1
        sources[src]["total_ms"] += s["elapsed_ms"]
        sources[src]["total_tokens"] += s.get("tokens", 0)

    total_tokens = sum(s["tokens"] for s in _stats)
    total_calls = len(_stats)

    # 平均耗时
    for src in sources:
        sources[src]["avg_ms"] = round(sources[src]["total_ms"] / sources[src]["count"])

    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "sources": dict(sources),
    }
