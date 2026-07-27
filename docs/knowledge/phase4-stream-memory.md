# 阶段 4：SSE 流式输出 + 多轮对话 Memory

> 目标：让 Agent 回复像打字机一样逐字输出，同时记住跨轮对话上下文。

---

## 1. 阶段 4 改了什么

### 修改文件

| 文件 | 改动 |
|---|---|
| `app/agent.py` | 新增 `MemorySaver` checkpointer |
| `app/routers/chat.py` | 新增 `POST /api/chat/stream` SSE 接口；`POST /api/chat` 支持 `session_id` |

---

## 2. Memory：多轮对话记忆

### 2.1 原理

```python
from langgraph.checkpoint.memory import MemorySaver

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=MemorySaver(),  # ← 这一行
)
```

`MemorySaver` 是 LangGraph 内置的内存级 checkpointer。每次 `agent.invoke()` 或 `agent.astream_events()` 时传入 `thread_id`，checkpointer 自动：

- **调用前**：从内存中加载该 thread 的历史 messages，拼到当前 messages 前面
- **调用后**：把本轮的新 messages 追加保存

### 2.2 使用方式

```python
# 第一轮：不传 session_id，自动创建
POST /api/chat {"message": "我叫张三"}
→ {"reply": "你好张三！", "session_id": "abc123"}

# 第二轮：带上 session_id
POST /api/chat {"message": "我叫什么？", "session_id": "abc123"}
→ {"reply": "你叫张三，我记得！", "session_id": "abc123"}

# 新会话：不传 session_id
POST /api/chat {"message": "我叫什么？"}
→ {"reply": "你还没告诉我你的名字", "session_id": "def456"}
```

### 2.3 thread_id 如何工作

```
thread_id = "abc123"

第 1 轮 invoke:
  config = {"configurable": {"thread_id": "abc123"}}
  → MemorySaver 查找 thread "abc123" → 空，从头开始
  → 调用结束：保存 [HumanMsg("我叫张三"), AIMsg("你好张三！")]

第 2 轮 invoke:
  config = {"configurable": {"thread_id": "abc123"}}
  → MemorySaver 查找 thread "abc123" → 加载历史 messages
  → 实际发给 LLM 的 messages:
    [SystemMsg, HumanMsg("我叫张三"), AIMsg("你好张三！"), HumanMsg("我叫什么？")]
  → 调用结束：追加 [AIMsg("你叫张三！")]

第 3 轮 invoke (新 thread "def456"):
  → MemorySaver 查找 thread "def456" → 空
  → 不记得张三
```

---

## 3. SSE 流式输出

### 3.1 标准 vs 流式

| | 普通 `/api/chat` | 流式 `/api/chat/stream` |
|---|---|---|
| 调用方式 | `agent.invoke()` | `agent.astream_events()` |
| 响应方式 | 等全部完成，一次返回 JSON | 实时推送事件流 |
| 首字延迟 | 等 LLM 完整回复 | <1 秒 |
| 用户体验 | 空白等待 | 打字机效果 |

### 3.2 SSE 事件格式

```
data: {"type":"tool_start","tool":"search_knowledge_base"}

data: {"type":"tool_end","tool":"search_knowledge_base"}

data: {"type":"token","content":"根据"}

data: {"type":"token","content":"知识"}

data: {"type":"token","content":"库"}

...

data: {"type":"done","session_id":"abc12345"}
```

### 3.3 事件类型

| type | 触发时机 | 前端可以用它做什么 |
|---|---|---|
| `tool_start` | Agent 开始调用工具 | 显示"正在查询知识库..." |
| `tool_end` | 工具调用完成 | 隐藏加载提示 |
| `token` | LLM 输出文本片段 | 逐字追加到聊天气泡 |
| `done` | 本轮处理完成 | 返回 session_id，前端保存 |
| `error` | 处理出错 | 显示错误提示 |

### 3.4 流式 + 工具调用的兼容处理

**核心问题**：Agent 调用工具时，LLM 可能会输出一些"思考"文本，这些要不要发给用户？

```
Agent 内部流程：
  LLM 调用 1："我来帮您查询一下..." → tool_call: search_knowledge_base
  工具执行：search_knowledge_base → 返回结果
  LLM 调用 2：基于结果生成最终回复
```

**策略**：全部 stream。LLM 调用 1 的"思考文本"（如"我来帮您查询..."）也发给用户——这其实是好的 UX，让用户知道 Agent 在干什么。`tool_start`/`tool_end` 事件让前端展示更清晰的进度。

### 3.5 关键代码

```python
async def event_generator():
    async for event in agent.astream_events(
        {"messages": [("user", message)]},
        config=config,        # 传入 thread_id → Memory 生效
        version="v2",
    ):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield f"data: {json.dumps({'type':'token','content':chunk.content})}\n\n"

        elif kind == "on_tool_start":
            yield f"data: {json.dumps({'type':'tool_start','tool':event['name']})}\n\n"

        elif kind == "on_tool_end":
            yield f"data: {json.dumps({'type':'tool_end','tool':event['name']})}\n\n"

    yield f"data: {json.dumps({'type':'done','session_id':session_id})}\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 3.6 三个响应头的作用

```python
headers={
    "Cache-Control": "no-cache",       # 禁止浏览器/代理缓存 SSE 数据
    "Connection": "keep-alive",         # 保持 TCP 连接打开
    "X-Accel-Buffering": "no",          # 禁用 Nginx 缓冲（否则 Nginx 会攒够数据再发）
}
```

没有这三个头，SSE 在反向代理（Nginx）后面会退化成"等 30 秒一次性返回"。

---

## 4. 验证结果

### Memory 测试

| 轮次 | 输入 | session | Agent 回复 | 结果 |
|---|---|---|---|---|
| 1 | 「我叫张三」 | 新 session A | "你好张三！" | ✅ 记住了 |
| 2 | 「我叫什么名字？」 | 同 session A | "你叫张三，我记得！" | ✅ 跨轮记忆 |
| 3 | 「我叫什么名字？」 | 新 session B | "你还没告诉我你的名字" | ✅ 隔离 |

### SSE 流式测试

```
POST /api/chat/stream {"message": "免费版价格？"}

HTTP 200 (text/event-stream)

data: {"type":"token","content":"我来帮您查询..."}
data: {"type":"tool_start","tool":"search_knowledge_base"}
data: {"type":"tool_end","tool":"search_knowledge_base"}
data: {"type":"token","content":"根据"}
data: {"type":"token","content":"知识库"}
...
data: {"type":"done","session_id":"cee8a168"}
```

---

## 5. 踩坑：Agent 迭代次数过多

测试中 Agent 连续调了 6 次 `search_knowledge_base`，这是因为 LLM 对检索结果不满意反复重试。

**临时缓解**：在 System Prompt 中加入 "多次检索无果后请诚实地告诉用户未找到信息"。

后续可配置 LangGraph 的 `recursion_limit` 硬限制，但当前影响不大（最终答案仍正确），留到优化阶段处理。

---

## 6. 阶段 4 检查清单

- [x] `POST /api/chat` 支持 session_id，同一 session 内跨轮记忆
- [x] 不同 session 之间上下文隔离
- [x] `POST /api/chat/stream` SSE 流式推送 token
- [x] `tool_start` / `tool_end` 事件正常推送
- [x] `done` 事件包含 session_id
- [x] 反向代理缓冲头已配置
