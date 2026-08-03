# 阶段 13：Agent 状态显式建模 + 系统性加固

> 目标：把订单上下文从"消息文本里的隐式信息"升级为 AgentState 的显式字段，并修复检索/工具链路的多处隐性 bug。

---

## 一、为什么做

### 之前的问题

```
Agent 状态只有 messages：
  订单号、意图、知识片段全部藏在消息文本里

  用户: "DD20240731002 退款这笔"
  → 订单号只在用户消息里 → LLM 靠 SystemPrompt 规则 2 从历史里"猜"

痛点:
  1. 订单上下文不可显式读取（工具/代码拿不到 state["order_context"]）
  2. LLM 偶尔不按规则推断，指代"这笔"时拿错订单号
  3. 检索/工具链路有隐性 bug（见下）
```

### 本阶段还修复的隐性 bug

| Bug | 根因 | 修复 |
|---|---|---|
| DeepSeek 间歇性不调工具 | `**kwargs` 签名 → langchain 生成空壳 schema | `_make_args_model` 用 MCP inputSchema 生成具名参数 |
| 知识库无限膨胀 | `build_index` 用 `from_texts` 每次追加 | 优先加载已有索引，幂等 |
| 前端新对话不切页 | sessionId 为 null 时不触发 watch | resetKey 递增计数强制清空 |

---

## 二、改动清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `app/agent.py` | 修改 | 新增 `AgentState`（messages/order_context/intent），`create_agent(state_schema=...)` |
| `app/router.py` | 修改 | 新增 `analyze_request()`：正则提订单号 + 关键词判意图 |
| `app/routers/chat.py` | 修改 | `_build_state_input()` 播种显式字段 + 注入 `【订单上下文】` SystemMessage；路由命中写记忆时同步播种 |
| `app/mcp_client.py` | 修改 | `_make_args_model()` 从 inputSchema 生成 pydantic 参数模型 |
| `app/rag/loader.py` | 修改 | `build_index` 幂等（先加载已有索引） |
| `tests/test_context.py` | 新建 | 7 例：上下文分析 + 状态播种 |
| `tests/test_mcp_client.py` | 新建 | 4 例：工具 schema 回归 |
| `frontend/*` | 修改 | 盒中速递设计系统 + 新对话/历史 bug 修复 |

---

## 三、新状态模型

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # 对话记忆
    order_context: dict                       # 订单号 + 意图（显式）
    intent: str                               # 意图分类
```

### 播种流程

```
用户消息
  → analyze_request(text)
      → 正则提订单号 DD\d{9,12}
      → 关键词判意图 return/order/product/shipping/general
  → _build_state_input(text)
      → state["order_context"] = {order_id, intent}   ← 显式字段
      → state["intent"] = intent
      → messages 前插 【订单上下文】 SystemMessage     ← 让 LLM 直接读取
```

### 效果

```
用户: "DD20240731002 退款这笔"（第 1 轮）
  → agent 第一眼看到【订单上下文】{order_id:"DD20240731002", intent:"return"}
  → 直接调 query_order，不再猜订单号

用户: "那这笔能退吗"（第 2 轮）
  → 显式 order_context 已在 state / 消息历史中 → 指代命中
```

### 路由命中路径的一致性

非流式对话命中路由缓存（零 LLM 成本）时，写记忆也同步播种 `order_context`/`intent`，
保证显式字段在多轮对话中不因"走了缓存"而断链。

---

## 四、验证

- 测试 32 例全过（25 原 + 7 上下文 + 补充 MCP schema 回归）
- 端到端多轮：查订单 → "那这笔能退吗" → 正确识别订单并回答退货政策
- 模型输入探针确认收到 `【订单上下文】` 消息
- 工具调用恢复 100%（schema 修复）
- 知识库索引 8085 → 35 块（幂等）

---

## 五、后续方向

- [ ] `order_context` 驱动 `process_return` 预校验（免 query_order 往返）
- [ ] MemorySaver → SqliteSaver（记忆跨重启持久化）
- [ ] `intent` 参与请求路由决策
