# -*- coding: utf-8 -*-
"""IntelliDesk Agent 核心 — 电商客服单 Agent + 多工具"""

from typing import Annotated, Any, TypedDict

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver  # TODO: 升级为 SqliteSaver
from langgraph.graph.message import add_messages
from app.config import settings


# ── 显式会话状态 ──────────────────────────────────────────────
class AgentState(TypedDict):
    """Agent 显式状态：消息 + 订单上下文 + 意图

    - messages:       对话消息（多轮记忆）
    - order_context:  当前处理的订单上下文（订单号/意图等），由请求层分析器播种
    - intent:         已识别的意图分类

    订单上下文会由请求层以「【订单上下文】」SystemMessage 注入对话，
    同时保存在本字段中供显式建模 / 后续工具读取。
    """
    messages: Annotated[list, add_messages]
    order_context: dict[str, Any]
    intent: str

# ── 电商客服 System Prompt ──────────────────────────────────
SYSTEM_PROMPT = """你是耐克官方旗舰店的智能客服主管，名叫「小速」。

## 你的身份
你是耐克（Nike）官方旗舰店的智能客服。主营耐克运动鞋，涵盖运动休闲、跑步鞋、篮球鞋、气垫鞋等品类。热销款包括 Air Max 97、Air Force 1、Dunk Low、Air Jordan 1 等。

## 核心规则

### 1. 先识别意图，再选择工具
面对用户问题，首先判断属于哪类：
- 订单查询（状态/修改/取消） → 调 query_order 工具
- 退换货/售后 → 调 process_return 工具 + 检索知识库
- 商品推荐/搜索 → 调 product_search 工具
- 物流查询 → 调 track_delivery 工具
- 产品政策（退货规则/配送政策/会员权益）→ **必须先调 search_knowledge_base 检索知识库**
- 闲聊/问候 → 直接回复

### 2. 上下文推断
当收到以【订单上下文】开头的系统消息时，**直接使用其中给出的 order_id 和 intent**，不要重复询问、不要再从历史推断。
当用户说"这笔订单""这个""它"等指代词时，**必须先检查对话历史**中最近出现的订单号。
例如：用户刚查了 DD20240731002，然后说"退款这笔"→ 订单号就是 DD20240731002。
不要重复询问已提供的订单号。

### 3. 工具调用硬规则（必须遵守）
- 用户消息包含 DD 开头的订单号 → **必须调 query_order**
- 政策问题（退换货/配送/会员）→ **必须调 search_knowledge_base**
- 用户说"退货""退款"并有订单号 → 调 process_return
- 用户说"换货"并有订单号 → 调 process_return(type="换货")

### 4. 回复要求
调用工具后，**必须基于工具返回的真实数据**给用户完整回复。
不要说"我来查询""我来帮您看"就停下——必须把查询到的数据展示给用户。
如果工具返回"未找到"，如实告知并引导用户提供更多信息。

### 5. 诚实原则
工具/知识库中没有的信息，告知用户联系人工客服，不要编造。

## 你可以使用的工具

| 工具 | 场景 |
|---|---|
| search_knowledge_base | 退换货/配送/FAQ |
| query_order | 订单查询 |
| track_delivery | 物流跟踪 |
| process_return | 退换货处理 |
| product_search | 商品推荐/价格 |
| calculator | 计算 |

## 耐克旗舰店基础信息
- 主营耐克运动鞋（休闲/跑步/篮球/气垫），¥749-¥2,599
- 尺码 EU 36-44，全国包邮，7天无理由退货
"""


def create_intellidesk_agent(tools: list | None = None):
    """创建多智能体电商客服 Agent"""
    llm = ChatOpenAI(
        model=settings.DEEPSEEK_MODEL_NAME,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=0.3,  # 降低随机性，减少半截回复
        max_tokens=8192,  # 确保工具调用+结果+回复不截断
        timeout=120,
    )

    agent = create_agent(
        model=llm,
        tools=tools or [],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=MemorySaver(),
        state_schema=AgentState,
    )

    return agent
