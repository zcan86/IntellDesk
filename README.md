# 🤖 IntelliDesk — 电商智能客服 Agent

基于 **LangGraph Agent + Adaptive-RAG + MCP 协议 + SQLite** 的耐克电商客服系统。网关鉴权、4层请求路由、7工具、订单/退款/物流全链路、服务评价。

---

## 功能

- 📚 **Adaptive-RAG 检索**：BM25 + BGE-m3 混合检索 + RRF 融合 + LLM Rerank
- 🛍️ **电商工具链**：订单查询、物流跟踪、退换货处理、商品搜索
- ⚡ **SSE 流式输出**：打字机效果 + 工具调用过程实时可见
- 🧠 **多轮记忆**：5轮滑动窗口 + 60分钟 TTL + 手动清除
- 🛡️ **网关层**：API Key 鉴权 + IP 限流（30次/分钟）
- 🎯 **4层请求路由**：精确→关键词→语义→Agent，40%请求零LLM成本
- 📊 **Token统计** + **用户画像** + **服务评价**

---

## 技术架构

```
用户请求
  → 网关 (鉴权 + 限流)
  → 路由 (精确14条 → 关键词12条 → 语义FAQs → Agent)
  → 执行 (ReAct + 工具限制 + MCP Server)
  → 输出 (SSE流式 + Token统计)
  → 反馈 (打星 + 评论)
```

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3 + Element Plus + Vite |
| 后端 | FastAPI + Pydantic |
| Agent | LangGraph + DeepSeek |
| 检索 | BM25 + BGE-m3 + RRF + LLM Rerank |
| 工具协议 | MCP (HTTP, McpToolServer) |
| 数据库 | SQLite (用户/订单/退款/反馈) |

---

## 快速开始

```bash
# 终端 1: MCP Server
python mcp_server/server.py          # → :8100

# 终端 2: Agent
cp .env.example .env                 # 填入 API Keys
python main.py                       # → :8000

# 终端 3: 前端
cd frontend && npm install && npm run dev  # → :5173
```

---

## 项目结构

```
├── app/
│   ├── agent.py              # Agent System Prompt
│   ├── config.py             # 全局配置
│   ├── database.py           # SQLite (users/orders/returns/feedback)
│   ├── gateway.py            # 鉴权 + 限流
│   ├── router.py             # 4层请求路由
│   ├── stats.py              # Token统计
│   ├── rag/                  # 检索（ChromaDB+BM25+RRF+Rerank）
│   ├── routers/chat.py       # 全部 API 端点
│   ├── tools/                # 工具实现（不直接import,走MCP）
│   └── mcp_client.py         # MCP Client
├── mcp_server/               # MCP Tool Server (独立进程)
├── frontend/                 # Vue 3 前端
├── docs/                     # 12份知识文档 + 产品文档
├── tests/                    # 21个测试
└── data/                     # SQLite DB + 商品图片
```

---

## API 总览

| 方法 | 端点 | 说明 |
|---|---|---|
| POST | `/api/chat` | 对话 |
| POST | `/api/chat/stream` | SSE 流式 |
| POST | `/api/chat/upload` | 多模态上传 |
| GET | `/api/orders/{user_id}` | 用户订单 |
| GET | `/api/order/{id}` | 订单详情 |
| GET | `/api/profile/{user_id}` | 用户画像 |
| GET | `/api/stats` | Token 统计 |
| POST | `/api/feedback` | 提交评价 |
| GET | `/api/feedback/stats` | 评价统计 |
| DELETE | `/api/session/{id}` | 清除会话 |
| POST | `/api/documents/reindex` | 重建知识库 |

---

## 开发路线

- [x] Agent 骨架 + RAG + 工具 + SSE + Memory + 前端
- [x] ChromaDB + BGE-m3 语义检索
- [x] MCP 协议集成
- [x] Adaptive-RAG (BM25+BGE-m3+RRF+Rerank)
- [x] 电商客服（7工具：知识库/订单/物流/退换货/商品/计算/时间）
- [x] Vue 3 前端重构
- [x] SQLite 订单数据库 + 退款退货 + 物流跟踪
- [x] 4层请求路由 + 网关鉴权限流
- [x] 服务评价 + Token统计 + 用户画像

---

## 性能数据

| 指标 | 数值 |
|---|---|
| 路由命中率 | 95% (21/22) |
| 缓存响应 | 0.1ms |
| Agent 响应 | 2-5s |
| Token 节省 | 88% (vs 全走Agent) |
| 测试覆盖 | 21 用例 |

---

## License

MIT
