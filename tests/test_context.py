# -*- coding: utf-8 -*-
"""请求上下文分析 + Agent state 播种的回归测试

守护架构改进：订单上下文显式建模进 AgentState（order_context / intent），
不再依赖 LLM 从文本推断。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.router import analyze_request
from app.routers.chat import _build_state_input


class TestAnalyzeRequest:
    """analyze_request: 订单号提取 + 意图分类"""

    def test_extract_order_id(self):
        ctx = analyze_request("帮我查一下 DD20240725001")
        assert ctx["order_id"] == "DD20240725001"

    def test_returns_intent_by_keyword(self):
        ctx = analyze_request("这笔要退货")
        assert ctx["intent"] == "return"

    def test_product_intent(self):
        ctx = analyze_request("推荐一款跑步鞋")
        assert ctx["intent"] == "product"

    def test_general_intent_no_keyword(self):
        ctx = analyze_request("你好呀")
        assert ctx["intent"] == "general"
        assert ctx["order_id"] is None


class TestBuildStateInput:
    """_build_state_input: 播种显式 state 字段 + 注入上下文消息"""

    def test_seeds_order_context_fields(self):
        state = _build_state_input("DD20240731002 退款")
        assert state["order_context"]["order_id"] == "DD20240731002"
        assert state["order_context"]["intent"] == "return"
        assert state["intent"] == "return"

    def test_injects_context_system_message(self):
        state = _build_state_input("DD20240731002 退款")
        first = state["messages"][0]
        assert first.content.startswith("【订单上下文】")
        assert "DD20240731002" in first.content

    def test_general_chat_no_context(self):
        state = _build_state_input("你好")
        assert "order_context" not in state
        assert "intent" not in state
        # 不注入上下文消息
        assert all(
            not getattr(m, "content", "").startswith("【订单上下文】")
            for m in state["messages"]
        )
