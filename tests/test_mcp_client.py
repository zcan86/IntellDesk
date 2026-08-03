# -*- coding: utf-8 -*-
"""MCP Client 回归测试

守护 `app/mcp_client.py` 的工具参数 schema 生成逻辑。
若 `_make_args_model` 被移除或退回 `**kwargs` 空壳 schema，
以下测试必须失败（对应线上 bug：DeepSeek 间歇性放弃调用工具）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.utils.function_calling import convert_to_openai_tool

from app.mcp_client import _make_args_model, _build_tool


class TestArgsModel:
    """_make_args_model 从 MCP inputSchema 生成 pydantic 模型"""

    def test_required_field_present(self):
        model = _make_args_model({
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "订单号"}},
            "required": ["order_id"],
        })
        schema = model.model_json_schema()
        assert "order_id" in schema["properties"]
        assert schema["required"] == ["order_id"]

    def test_optional_field_not_required(self):
        """reason 未在 required 中 → 不应进 required 列表"""
        model = _make_args_model({
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["order_id"],
        })
        schema = model.model_json_schema()
        assert "reason" in schema["properties"]
        assert schema["required"] == ["order_id"]

    def test_empty_schema_ok(self):
        """无参数工具（如 get_current_time）不应抛错"""
        model = _make_args_model({"type": "object", "properties": {}})
        assert model.model_json_schema()["properties"] == {}


class TestToolSchema:
    """convert_to_openai_tool 生成的 OpenAI schema 不能是 kwargs 空壳"""

    def _build(self, schema: dict):
        return _build_tool(
            {"name": "query_order", "description": "查订单", "inputSchema": schema},
            "http://127.0.0.1:8100",
        )

    def test_named_properties_not_kwargs_shell(self):
        """核心回归：必须产出具名参数，禁止回到 {kwargs: {type: object}} 空壳"""
        t = self._build({
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        })
        params = convert_to_openai_tool(t)["function"]["parameters"]
        assert "kwargs" not in params.get("properties", {})
        assert "order_id" in params["properties"]
        assert params["required"] == ["order_id"]
