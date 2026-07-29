# 🤖 IntelliDesk — 多智能体电商客服 Agent

基于 **LangGraph 多智能体 + Adaptive-RAG + MCP 协议 + 电商工具链** 的电商智能客服系统。

7 类意图自动路由，8 个工具覆盖订单/物流/退换货/商品推荐全场景。

---

## 功能

启动后在浏览器打开 `http://localhost:8000`：

- 🧠 **多智能体协作**：LLM 意图识别 → 7 类子 Agent 路由（订单/售后/商品/物流/支付/账号/通用）
- 📚 **Adaptive-RAG 检索**：BM25 + BGE-m3 混合检索 + RRF 融合 + LLM Rerank + Self-RAG 反思
- 🛍️ **电商工具链**：订单查询、物流跟踪、退换货指引、商品搜索
- ⚡ **SSE 流式输出**：打字机效果，工具调用过程实时可见
- 🧠 **多轮对话记忆**：MemorySaver + thread_id 会话隔离
- 📂 **历史会话管理**：侧边栏 localStorage 保存/切换/删除
- 🔌 **MCP 协议支持**：三种工具模式（直接/MCP本地/MCP远程），配置切换

---

## 技术架构

```
用户 → 意图识别 (router.py)
        ├─ 订单 → OrderAgent      → query_order / track_delivery
        ├─ 售后 → ReturnAgent     → return_guide / search_knowledge_base
        ├─ 商品 → ProductAgent    → product_search
        ├─ 物流 → ShippingAgent   → search_knowledge_base
        ├─ 支付 → PaymentAgent    → 直接回复
        ├─ 账号 → AccountAgent    → 直接回复
        └─ 通用 → GeneralAgent    → 闲聊兜底
                  │
        ┌─────────┴──────────┐
        │  Adaptive-RAG 检索  │  BM25 + BGE-m3 + RRF + Rerank + Self-RAG
        │  8 工具自主路由      │  订单/物流/退换货/商品/天气/计算/时间/知识库
        │  MemorySaver 记忆    │  thread_id 会话隔离
        └────────────────────┘
                  │
          SSE 流式 → 前端打字机效果
```

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Element Plus + Vite |
| 后端 | FastAPI + Pydantic |
| 多 Agent | LangGraph + 意图路由 (7 类) |
| 检索 | Adaptive-RAG (BM25 + BGE-m3 + RRF + LLM Rerank + Self-RAG) |
| 工具协议 | MCP (HTTP transport) |
| LLM | DeepSeek Chat |

---

## 快速开始

```bash
git clone https://github.com/zcan86/IntellDesk.git
cd IntellDesk
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # 填入 DEEPSEEK_API_KEY + EMBEDDING_API_KEY
python main.py             # → http://localhost:8000
```

Docker: `docker compose up -d`

---

## 项目结构

```
├── app/
│   ├── agent.py              # 多智能体 System Prompt
│   ├── config.py             # 全局配置
│   ├── agents/
│   │   └── router.py         # 意图识别 + 7 类子 Agent Prompt
│   ├── rag/
│   │   ├── loader.py         # ChromaDB 索引 + BM25 初始化
│   │   ├── hybrid_retriever.py  # BM25+语义+RRF 混合检索
│   │   ├── reranker.py       # LLM 重排序
│   │   └── adaptive_rag.py   # 查询分析 + Self-RAG 反思
│   ├── routers/chat.py       # /chat /chat/stream /reindex
│   ├── tools/
│   │   ├── knowledge_search.py  # Adaptive-RAG 检索 Tool
│   │   ├── ecommerce.py      # 订单/物流/退换货/商品 Tool
│   │   └── builtin_tools.py  # 天气/计算/时间 Tool
│   └── mcp_client.py         # MCP 远程连接器
├── frontend/                 # Vue 3 + Element Plus 前端源码
├── static/                   # 前端构建产物
├── docs/
│   ├── knowledge/            # 9 份知识点文档
│   └── products/             # 电商知识库（退换货/配送/商品/FAQ）
├── tests/                    # 21 个测试
└── Dockerfile + docker-compose.yaml
```

---

## 开发路线

- [x] 阶段 0：环境搭建
- [x] 阶段 1：Agent 骨架
- [x] 阶段 2：RAG 知识库
- [x] 阶段 3：多工具调用
- [x] 阶段 4：SSE + Memory
- [x] 阶段 5：前端聊天界面
- [x] 阶段 6：测试 + Docker
- [x] ChromaDB + BGE-m3 语义检索
- [x] MCP 协议集成 + McpToolServer
- [x] Adaptive-RAG 混合检索 + 重排序
- [x] 多智能体电商客服（意图路由 + 电商工具链）
- [x] 前端重构 Vue 3 + Element Plus + TypeScript

---

## MCP 工具模式

IntelliDesk 的工具可通过 MCP 协议独立部署：[McpToolServer](https://github.com/zcan86/McpToolServer)

---

## License

MIT
