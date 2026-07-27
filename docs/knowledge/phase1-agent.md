# 阶段 1：搭建最简 Agent 对话骨架

> 目标：做一个能对话的 Agent——没有 RAG、没有工具，就是纯对话。用户发消息 → Agent 回复。

---

## 1. 核心文件

```
app/
├── agent.py        ← 新建：Agent 创建逻辑
└── routers/
    └── chat.py     ← 重写：新增 POST /api/chat
```

整个阶段的调用链路：

```
浏览器
  │  POST /api/chat {"message": "退货怎么退？"}
  ▼
chat.py → ChatRequest 校验
  │
  ▼
get_agent() → create_intellidesk_agent()
  │
  ├── ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com")
  │
  ▼
agent.invoke({"messages": [("user", "...")]})
  │
  ▼
从 messages 中提取 type="ai" 的最后一条
  │
  ▼
ChatResponse(reply="你好！关于退货流程...")
  │
  ▼
浏览器收到 JSON → 显示
```

---

## 2. create_agent API（LangChain 新 Agent）

### 旧 API vs 新 API

```python
# 已弃用（langgraph.prebuilt）
from langgraph.prebuilt import create_react_agent
agent = create_react_agent(model=llm, tools=tools, prompt=prompt)

# 新 API（langchain.agents）
from langchain.agents import create_agent
agent = create_agent(model=llm, tools=tools, system_prompt=prompt)
```

参数名变了：`prompt` → `system_prompt`，其余一致。

### 函数签名

```python
def create_agent(
    model: str | BaseChatModel,       # LLM 实例或字符串标识
    tools: Sequence[BaseTool] | None,  # 工具列表（先空着）
    system_prompt: str | None,         # 系统提示词
) -> CompiledStateGraph:              # 返回编译好的 LangGraph
```

### 内部做了什么？

`create_agent` 内部自动做了三件事：

1. 创建一个 LangGraph StateGraph
2. 在图中注册两个节点：`llm_call`（调模型）和 `tool_execute`（执行工具）
3. 设置条件路由：LLM 返回 tool_call → 执行工具 → 再调 LLM；LLM 返回 text → 结束

因为你还没给工具，所以实际流程是 `llm_call → 结束`，相当于一次普通的 LLM 调用带 System Prompt。

---

## 3. 用 ChatOpenAI 连接 DeepSeek

```python
llm = ChatOpenAI(
    model="deepseek-chat",                      # DeepSeek 模型名
    api_key=settings.DEEPSEEK_API_KEY,           # 从 .env 加载
    base_url="https://api.deepseek.com",         # 指向 DeepSeek
    temperature=0.7,                             # 控制随机性
    max_tokens=4096,                             # 最大回复长度
    timeout=120,                                 # 超时（秒）
)
```

### 为什么 ChatOpenAI 能调 DeepSeek？

`ChatOpenAI` 本质上就是发一个 HTTP POST 到 `{base_url}/v1/chat/completions`，只要返回格式是 OpenAI 兼容的就能用。DeepSeek、Kimi、Qwen、Gemini（通过中转）都遵循这个格式。

### LangChain 在中间做了什么？

```
你的代码
  agent.invoke({"messages": [...]})
      │
      ▼
LangChain Agent 层（create_agent）
  思考 → 决定下一步
      │
      ▼
ChatOpenAI 适配器层
  把 LangChain 的 messages 转成 HTTP JSON
      │
      ▼
HTTP POST https://api.deepseek.com/v1/chat/completions
      │
      ▼
DeepSeek 服务器处理
      │
      ▼
HTTP Response（JSON）
      │
      ▼
ChatOpenAI 适配器层
  把 JSON 转成 LangChain 的 AIMessage 对象
      │
      ▼
LangChain Agent 层
  判断是否需要继续（调工具）还是结束
      │
      ▼
你的代码接收到返回
```

**LangChain 不是黑魔法，它只是一层适配器**——帮你管理 messages、处理 tool calling、循环控制。底层还是 HTTP 调用。

---

## 4. System Prompt 设计

```python
SYSTEM_PROMPT = """你是一个专业、友好的智能客服助手，名叫「小智」。

## 你的职责
- 耐心回答用户的问题
- 如果涉及产品使用、退换货、售后服务等，请给出清晰的操作指引
- 如果遇到你无法确定的信息，请诚实告知，不要编造

## 你的风格
- 语气亲切但不啰嗦
- 回答结构清晰，适当使用分点列举
- 优先给出用户可以直接操作的步骤

## 当前限制
- 你目前还不能查询订单或知识库，这些功能正在开发中
- 对于需要查询系统的问题，请告知用户你暂时无法查询
"""
```

### 设计要点

1. **角色定义**：告诉模型它是谁 → "智能客服助手，名叫小智"
2. **行为边界**：什么能做、什么不能做 → "不要编造""无法查询的要告知"
3. **输出格式**：期望的回答风格 → "分点列举""操作步骤"
4. **诚实约束**：这个最重要——没有 RAG 之前，必须让 Agent 诚实地说不懂，而不是瞎编

---

## 5. Agent 调用方式

### 输入格式

```python
result = agent.invoke({
    "messages": [("user", "用户的原始问题")]
})
```

`("user", "content")` 是 LangGraph 的消息元组简写，内部自动转成 `HumanMessage`。

### 输出提取

```python
messages = result.get("messages", [])
for msg in reversed(messages):          # 从后往前找
    if msg.type == "ai":                # AI 消息
        reply = msg.content             # 提取文本
        break
```

Agent 返回的是一个消息列表：`[HumanMessage, AIMessage, ToolMessage, AIMessage, ...]`。因为目前没有工具，实际只有 `[HumanMessage, AIMessage]`，取最后一条 AI 消息就行。

---

## 6. 延迟初始化（Lazy Initialization）

```python
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = create_intellidesk_agent(tools=[])
    return _agent
```

### 为什么不用模块级单例？

```python
# 这样做的话：import 时就创建 Agent
# → 如果 .env 还没加载或配置有误，直接崩溃
# → 服务器启动变慢
agent = create_intellidesk_agent()
```

`get_agent()` 在**第一次 HTTP 请求进来时**才创建 Agent：
- import 阶段不会出错（语法错误例外）
- 启动速度快
- 如果配置有误，第一次请求时才会暴露

---

## 7. 踩坑记录：langgraph 版本冲突

### 现象

```python
from langgraph.prebuilt import create_react_agent
# ImportError: cannot import name 'ExecutionInfo' from 'langgraph.runtime'
```

### 原因

`langgraph==1.0.10` + `langchain==1.1.0` 之间有内部 API 不兼容，`langgraph.runtime` 缺少 `ExecutionInfo` 类。

### 解决

```bash
pip install --upgrade langgraph langchain langchain-core
# → langgraph==1.2.9, langchain==1.3.14
```

**教训**：Python AI 生态的包版本变化很快，遇到奇怪的 ImportError，先试 `pip install --upgrade`。

---

## 8. Data Flow 全链路图

```
┌─────────────────────────────────────────────┐
│  app/config.py                              │
│  Settings()  ← 读取 .env                    │
│  DEEPSEEK_API_KEY, BASE_URL, MODEL_NAME...  │
└───────────────┬─────────────────────────────┘
                │ settings 对象
┌───────────────▼─────────────────────────────┐
│  app/agent.py                               │
│                                             │
│  create_intellidesk_agent(tools=[])          │
│    │                                        │
│    ├── ChatOpenAI(                          │
│    │     model=settings.DEEPSEEK_MODEL_NAME  │
│    │     api_key=settings.DEEPSEEK_API_KEY   │
│    │     base_url=settings.DEEPSEEK_BASE_URL │
│    │   )                                    │
│    │                                        │
│    └── create_agent(                        │
│          model=llm,                         │
│          tools=[],         ← 阶段 1 为空    │
│          system_prompt=SYSTEM_PROMPT        │
│        )                                    │
│                                             │
│  返回：CompiledStateGraph（可 invoke）       │
└───────────────┬─────────────────────────────┘
                │ agent 实例（单例缓存）
┌───────────────▼─────────────────────────────┐
│  app/routers/chat.py                        │
│                                             │
│  POST /api/chat                            │
│    │                                        │
│    ├── ChatRequest(message=str) → 校验      │
│    │                                        │
│    ├── get_agent() → 单例 Agent             │
│    │                                        │
│    ├── agent.invoke({                       │
│    │     "messages": [("user", message)]    │
│    │   })                                   │
│    │                                        │
│    ├── 从 messages 提取 AI 回复             │
│    │                                        │
│    └── ChatResponse(reply=str) → JSON       │
└─────────────────────────────────────────────┘
```

---

## 阶段 1 检查清单

- [ ] `from langchain.agents import create_agent`（不是 `langgraph.prebuilt`）
- [ ] `ChatOpenAI(base_url=...)` 指向 DeepSeek，不是默认 OpenAI
- [ ] System Prompt 包含诚实约束（不懂就说不懂）
- [ ] Agent 用延迟初始化，不用模块级单例
- [ ] `POST /api/chat` 返回 200 且 Agent 回复合理
- [ ] 无弃用警告
