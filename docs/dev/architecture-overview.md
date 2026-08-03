# IntelliDesk 架构解析：从 0 到 1

> 目标：完整解析项目分层架构、每项技术选型的理由、以及从 0 到 1 的整体搭建顺序。

---

## 一、项目定位

**IntelliDesk 是什么**：耐克官方旗舰店的智能客服 Agent。核心命题一句话：

> **用尽量少的 LLM 成本，答好尽量多的客服问题。**

这决定了整个架构的走向：**能规则短路就规则短路（零 LLM 成本），必须 AI 理解才进 Agent**。95% 的请求在路由层零成本返回，只有复杂/多跳问题才花钱调 DeepSeek。

两个要解决的痛点：
- **FAQ 长尾命中率低**：关键词/精确匹配覆盖不了用户的各种问法 → 语义检索 + LLM
- **常规 RAG 幻觉严重**：检索质量不可控 → Adaptive-RAG（策略路由 + 反思）

---

## 二、分层架构总览（9 层）

按数据流方向，从入口到最底层：

```
┌───────────────────────────────────────────────────────────┐
│ L9  前端  Vue3 + Element Plus + Vite（盒中速递设计系统）     │
├───────────────────────────────────────────────────────────┤
│ L8  API 层  app/routers/chat.py（SSE流式/多模态/订单/评价）  │
├───────────────────────────────────────────────────────────┤
│ L4  Agent 层  LangGraph + DeepSeek + 显式 AgentState        │
│     ↕ MCP HTTP                                             │
│ L5  工具层  MCP Server(:8100) ← app/tools/ 业务实现         │
├───────────────────────────────────────────────────────────┤
│ L6  RAG 层  Adaptive-RAG（混合检索+RRF+Rerank+Self-RAG）    │
│ L7  数据层  SQLite（users/orders/returns/feedback）         │
├───────────────────────────────────────────────────────────┤
│ L3  路由层  app/router.py（4层短路，95%零LLM成本）           │
│ L2  网关层  app/gateway.py（鉴权+限流）                     │
│ L1  配置层  app/config.py（pydantic-settings + .env）       │
│ L0  入口    main.py（FastAPI + lifespan + 中间件）          │
└───────────────────────────────────────────────────────────┘
```

| 层 | 模块 | 职责 | 关键点 |
|---|---|---|---|
| L0 入口 | `main.py` | FastAPI 应用 + 生命周期 | lifespan 初始化索引/数据库 |
| L1 配置 | `app/config.py` | 全局配置单例 | pydantic-settings，.env 加载 |
| L2 网关 | `app/gateway.py` | 鉴权 + 限流 | API Key + IP 滑动窗口 |
| L3 路由 | `app/router.py` | 4 层请求短路 | 精确→关键词→订单正则→语义 |
| L4 Agent | `app/agent.py` | ReAct 状态机 | AgentState(messages/order_context/intent) |
| L5 工具 | `mcp_server/` + `app/tools/` + `app/mcp_client.py` | 工具执行 | 独立进程 + HTTP 协议 |
| L6 RAG | `app/rag/` | 检索增强 | Adaptive-RAG 五步流水线 |
| L7 数据 | `app/database.py` | 业务数据 | SQLite 四表 |
| L8 API | `app/routers/chat.py` | HTTP 出口 | SSE 流式 + 并发排队 |
| L9 前端 | `frontend/` | 用户界面 | SSE 消费 + 设计系统 |

---

## 三、技术选型理由

### 后端框架：FastAPI + Uvicorn + Pydantic

| 选择 | 理由 |
|---|---|
| **FastAPI** | 原生 async 支持 SSE 流式；自动 OpenAPI 文档；Pydantic 类型校验集成，请求/响应模型声明即文档 |
| **Uvicorn** | ASGI 服务器，配 FastAPI 标准组合；`reload=True` 开发热重载 |
| **Pydantic v2 + pydantic-settings** | 配置类型化（`Settings` 单例），.env 自动加载；`Field(..., description=)` 即文档 |

**替代考虑**：Flask/Django 同步模型不适合 SSE 长连接高并发；纯 Node 后端则丢失 Python AI 生态。

### Agent 框架：LangChain + LangGraph

| 选择 | 理由 |
|---|---|
| **LangGraph** | 把 ReAct 循环建模成显式状态机（节点 + 边 + 检查点），可扩展自定义 state；`MemorySaver` 按 thread_id 持久化会话；`astream_events` 原生流式事件（SSE 依赖） |
| **LangChain `create_agent`** | 预置 ReAct 图，不用手写节点/边路由；支持 `state_schema` 自定义状态 |
| **DeepSeek** | 中文客服场景性价比最高；OpenAI 兼容协议（换 base_url 即切换）；`deepseek-chat` 工具调用能力满足 ReAct |

**关键决策**：从"消息隐式承载上下文"升级为 **`AgentState` 显式建模**（`messages` / `order_context` / `intent`），订单上下文由请求层分析器播种并注入 `【订单上下文】` SystemMessage，LLM 不再从文本猜订单号。

### 检索：ChromaDB + BGE-m3 + scikit-learn

| 选择 | 理由 |
|---|---|
| **ChromaDB** | 纯 Python 免部署的向量库（无需起服务）；本地持久化 `data/chroma_db`；API 简单 |
| **BGE-m3** | 中英双语 SOTA 的 Embedding；走硅基流动 API 免下载本地模型（原设计下载 ~24MB 本地模型，后改 API） |
| **scikit-learn** | 用 TfidfVectorizer 近似实现 **BM25** 关键词检索 + 语义 TF-IDF 路由，零额外重型依赖（numpy 已有） |

**混合检索设计**：语义（BGE-m3）+ 关键词（BM25）双通道 → RRF 倒数排名融合 → LLM Rerank 精排 → Self-RAG 反思。弥补纯语义对精确关键词不敏感的缺陷。

### 工具协议：MCP（自建 HTTP）

| 选择 | 理由 |
|---|---|
| **MCP 协议模式**（工具发现 `/mcp/tools` + 调用 `/mcp/call`） | 标准化的工具集成协议；工具独立成进程（:8100）与 Agent 解耦，可独立演进/部署 |
| **自建 HTTP 而非官方 SDK** | 更轻量可控，符合"工具调用"这一简单需求；官方 SDK 的 streamable-http 是更重方案 |
| **`_make_args_model` 动态生成 schema** | 关键修复：从 MCP inputSchema 生成 pydantic 具名参数模型，替代 `**kwargs` 空壳 schema（否则 DeepSeek 间歇性不调工具） |

### 数据：SQLite

零依赖、零配置、单文件存储，对演示数据（4 表）完全够用；WAL 模式支持并发读。生产化可平滑迁移 PostgreSQL（当前 `MemorySaver` TODO 升级 SqliteSaver 同理）。

### 前端：Vue 3 + Element Plus + Vite + fontsource

| 选择 | 理由 |
|---|---|
| **Vue 3 + Vite** | 组合式 API + TS 支持好；Vite 开发热重载快；生态成熟 |
| **Element Plus** | 中文场景组件库，表格/按钮/消息开箱即用 |
| **fontsource 本地字体** | ZCOOL 黄油体（display）+ Noto Sans SC + JetBrains Mono，本地打包免外网 CDN（国内网络友好） |
| **盒中速递设计系统** | 墨黑 × 鞋盒橙 × 暖白 + 橙色 swoosh 签名，避免 AI 模板 UI |

### 为什么用 OpenAI SDK 调非 OpenAI 模型

`openai` 库是**厂商无关的协议客户端**——DeepSeek、硅基流动、阿里百炼都提供 OpenAI 兼容端点。只改 `base_url` + `api_key` 即可切换厂商，一套代码三种用途：DeepSeek（主 LLM/意图/反思）、硅基流动（BGE-m3 Embedding）、阿里百炼（Qwen-VL-Max 图片识别）。

---

## 四、从 0 到 1 搭建顺序

### 推荐搭建路径（给复刻者的行动顺序）

```
阶段 A  骨架：FastAPI 跑通 + 配置层 + 最小 LLM 调用        → 先证明"能对话"
阶段 B  Agent：LangGraph 单 Agent + 记忆 + SSE 流式         → 先证明"能流式聊"
阶段 C  检索：ChromaDB + Embedding + 语义检索               → 再让回答"有依据"
阶段 D  工具：电商工具 + MCP 协议解耦                       → 让 Agent"能办事"
阶段 E  路由：4 层请求短路                                   → 让成本"降下来"
阶段 F  加固：Adaptive-RAG + 网关 + 测试 + Docker           → 让系统"能上线"
阶段 G  前端：Vue3 界面 + 设计系统                           → 让用户"用起来"
阶段 H  演进：AgentState 显式建模 + 并发/可靠性加固           → 让架构"更健壮"
```

### 项目实际 phase 序列（docs/dev/）

| Phase | 内容 | 对应上面的 |
|---|---|---|
| 0 | 环境搭建 + FastAPI + LLM 调用 | A |
| 1 | 最简 Agent 对话骨架（无 RAG 无工具） | B |
| 2 | RAG 语义检索（ChromaDB + BGE-m3） | C |
| 3 | 电商工具链 | D |
| 4 | SSE 流式 + 多轮记忆 | B |
| 5 | Vanilla JS 前端 | G |
| 6 | 测试 + Docker | F |
| 7 | MCP 协议集成 | D |
| 8 | Adaptive-RAG（混合检索 + RRF + Rerank + Self-RAG） | F |
| 9 | 电商多 Agent 编排 | H |
| 10 | 前端重构（Vue 3） | G |
| 11 | 多 Agent 可视化 | H |
| 12 | 生产化升级（网关 + 并发排队） | F |
| 13 | AgentState 显式建模 + 系统性加固 | H |

> 搭建顺序的核心思想：**每一步都产出一个"能跑的版本"**，而不是先铺基础设施再填业务。骨架 → 对话 → 检索 → 工具 → 降本 → 加固 → 体验。

---

## 五、一次请求的完整旅程

以「DD20240725001 到哪了？」为例贯穿 9 层：

```
前端输入框
 → L9  ChatView 发 fetch SSE
 → L2  网关 校验 API Key + 限流
 → L3  路由 含订单号 → 透传 Agent（不短路，让 Agent 记住上下文）
 → L1  配置 读取 DeepSeek/Embedding 配置
 → L4  Agent ReAct：收到【订单上下文】→ 决策调 track_delivery
 → L5  MCP Client → HTTP → MCP Server → app/tools/ecommerce.py → 查 SQLite
 → L6  （若需政策）RAG 混合检索返回知识片段
 → L4  Agent 基于真实轨迹组织回答
 → L8  SSE 推送 tool_start → token → done 事件
 → L9  打字机渲染完整答复
 → 横切：stats 记 Token、MemorySaver 存状态、order_context 进显式字段
```

---

## 六、关键设计决策与取舍

| 决策 | 选择 | 取舍 |
|---|---|---|
| 请求短路 vs 全走 Agent | 4 层路由短路 95% | 省 88% Token，代价是路由表需维护 |
| 工具集成 | MCP 独立进程 | 解耦好，代价是多一层网络调用 |
| Agent 状态 | messages 隐式 → AgentState 显式 | 显式可读可测，代价是请求层需分析播种 |
| 向量库 | ChromaDB 本地 | 免部署，代价是超大规模需换 Milvus/pgvector |
| 记忆 | MemorySaver 内存态 | 简单，代价是重启丢失（TODO SqliteSaver） |
| Embedding | API 调用（硅基流动） | 免下载模型，代价是依赖网络 + 第三方 |

---

## 七、当前状态与后续方向

- ✅ 全链路可用：路由短路、Agent 工具调用、RAG 检索、SSE 流式、多模态、评价统计
- ✅ 测试 32 例，索引幂等（35 块稳定），AgentState 显式建模
- 🔲 `order_context` 驱动 `process_return` 预校验（免 query_order 往返）
- 🔲 MemorySaver → SqliteSaver（记忆跨重启持久化）
- 🔲 `intent` 参与请求路由决策
