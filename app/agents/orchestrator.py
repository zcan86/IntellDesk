# -*- coding: utf-8 -*-
"""多 Agent 编排器

将用户请求路由到专业 Agent，并实时广播调度过程。

Agent 团队：
  OrderAgent     — 订单查询/修改/取消
  ReturnAgent    — 退换货/退款/售后
  ProductAgent   — 商品推荐/对比/搜索
  ShippingAgent  — 物流/配送/运费
  PaymentAgent   — 支付/发票
  AccountAgent   — 账号/会员/优惠券
  GeneralAgent   — 问候/闲聊/兜底
"""

import json
from dataclasses import dataclass, field
from openai import OpenAI
from loguru import logger
from app.config import settings
from app.agents.router import classify_intent, SPECIALIST_PROMPTS, INTENT_CATEGORIES

_client: OpenAI | None = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
    return _client


@dataclass
class AgentAction:
    """记录一次 Agent 调度"""
    agent_name: str
    intent: str
    action: str          # "planned" | "executing" | "completed"
    detail: str = ""


class Orchestrator:
    """多 Agent 编排器 — 规划 → 分派 → 汇总"""

    def __init__(self):
        self.actions: list[AgentAction] = []
        self.plan: list[str] = []         # 需要调用的 Agent 列表

    def plan_task(self, query: str) -> list[str]:
        """分析查询，规划需要哪些 Agent 参与

        Returns:
            需要调用的 Agent 名称列表
        """
        # Step 1: 主意图分类
        intent_result = classify_intent(query)
        primary_intent = intent_result.get("intent", "general")
        confidence = intent_result.get("confidence", 0.5)
        keywords = intent_result.get("keywords", [])

        self.actions.append(AgentAction(
            "Orchestrator", "planning",
            "planned",
            f"主意图: {primary_intent} (置信度 {confidence:.0%}), 关键词: {keywords}"
        ))

        # Step 2: 判断是否需要多个 Agent
        plan = [primary_intent]

        # 规则：某些场景需要额外 Agent
        if primary_intent == "return":
            plan.append("shipping")  # 退货需要告知物流方式
        elif primary_intent == "product":
            if any(k in str(keywords).lower() for k in ["价格", "便宜", "多少钱", "推荐"]):
                plan.append("payment")  # 商品询问可能涉及支付
        elif primary_intent == "order":
            # 订单查询可能涉及物流
            if any(k in str(keywords).lower() for k in ["物流", "快递", "到哪", "配送"]):
                plan.append("shipping")

        self.plan = plan
        self.actions.append(AgentAction(
            "Orchestrator", "planning",
            "planned",
            f"调度计划: {' → '.join(plan)}"
        ))
        return plan

    def get_specialist_context(self, agent_name: str) -> str:
        """获取专业 Agent 的 System Prompt"""
        return SPECIALIST_PROMPTS.get(agent_name, SPECIALIST_PROMPTS["general"])

    def get_specialist_tools(self, agent_name: str) -> list[str]:
        """获取专业 Agent 推荐的工具"""
        tool_map = {
            "order": ["query_order", "track_delivery", "search_knowledge_base"],
            "return": ["return_guide", "search_knowledge_base"],
            "shipping": ["track_delivery", "search_knowledge_base"],
            "product": ["product_search", "search_knowledge_base"],
            "payment": ["search_knowledge_base"],
            "account": ["search_knowledge_base"],
            "general": ["get_weather", "calculator", "get_current_time"],
        }
        return tool_map.get(agent_name, ["search_knowledge_base"])

    def log_action(self, agent_name: str, action: str, detail: str = ""):
        self.actions.append(AgentAction(agent_name, "", action, detail))

    def get_trace(self) -> list[dict]:
        """返回调度轨迹"""
        return [
            {"agent": a.agent_name, "action": a.action, "detail": a.detail}
            for a in self.actions
        ]


# ── 全局单例 ──────────────────────────────────────────────────
_orchestrator = Orchestrator()


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    return _orchestrator


def reset_orchestrator():
    global _orchestrator
    _orchestrator = Orchestrator()
