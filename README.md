# IntelliDesk — 多模态电商客服 Agent

基于 **LangGraph Agent + Adaptive-RAG + MCP 协议 + SQLite** 的耐克电商客服系统。网关鉴权、4层请求路由、9工具、订单/退款/物流全链路、多模态识别、服务评价。

---

## 功能

- **Adaptive-RAG 检索**：BM25 + BGE-m3 混合检索 + RRF 融合 + LLM Rerank
- **电商工具链**：9工具 —— 订单查询、物流跟踪、退换货处理、商品搜索、知识库、图片识别、语音转文字、计算、时间
- **SSE 流式输出**：打字机效果 + 工具调用过程实时可见
- **多轮记忆**：5轮滑动窗口 + 60分钟 TTL + 手动清除
- **网关层**：API Key 鉴权 + IP 限流 + LLM 并发排队（Semaphore 5）
- **4层请求路由**：精确→关键词→语义→Agent，95%请求零LLM成本
- **多模态识别**：Qwen-VL-Max 图片识别 + Whisper 语音转文字，不可用时友好降级
- **前端设计系统**：「盒中速递」—— 墨黑 × 鞋盒橙 × 暖白，橙色勾形 swoosh 签名元素，暗色模式自适应
- **Token统计** + **用户画像** + **服务评价**

---

## 技术架构

```
用户请求
 → 网关 (鉴权 + 限流 + 排队)
 → 路由 (精确14条 → 关键词12条 → 语义FAQs → Agent)
 → 执行 (ReAct + 工具限制 + MCP Server)
 → 输出 (SSE流式 + Token统计)
 → 反馈 (打星 + 评论)
```

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3 + Element Plus + Vite + fontsource 字体（盒中速递设计系统） |
| 后端 | FastAPI + Pydantic |
| Agent | LangGraph + DeepSeek |
| 检索 | BM25 + BGE-m3 + RRF + LLM Rerank |
| 工具协议 | MCP (HTTP, 独立进程 :8100) |
| 多模态 | Qwen-VL-Max（阿里百炼）+ Whisper 语音转文字 |
| 数据库 | SQLite (用户/订单/退款/反馈) |

---

## 快速开始

```bash
# 0) 创建虚拟环境并安装依赖（已验证 Python 3.14，也可用 3.13）
python -m venv venv
venv/Scripts/pip install -r requirements.txt   # Windows 用 Scripts/，macOS/Linux 用 bin/

# 终端 1: MCP Server
venv/Scripts/python mcp_server/server.py      # → :8100

# 终端 2: Agent
cp .env.example .env         # 填入 API Keys
venv/Scripts/python main.py  # → :8000

# 终端 3: 前端
cd frontend && npm install && npm run dev     # → :5173
```

---

## 项目结构

```
├── app/
│  ├── agent.py       # Agent System Prompt（客服人设「小速」）
│  ├── agents/        # LLM 意图识别（7类）+ 多 Agent 编排器
│  ├── config.py       # 全局配置
│  ├── database.py      # SQLite (users/orders/returns/feedback)
│  ├── gateway.py      # 鉴权 + 限流
│  ├── router.py       # 4层请求路由
│  ├── stats.py       # Token统计
│  ├── rag/         # Adaptive-RAG（ChromaDB+BGE-m3+BM25+RRF+Rerank）
│  ├── routers/chat.py    # 全部 API 端点
│  ├── tools/        # 工具实现（不直接import,走MCP）
│  └── mcp_client.py     # MCP Client
├── mcp_server/        # MCP Tool Server (独立进程 :8100)
├── frontend/         # Vue 3 前端（盒中速递设计系统 + SwooshMark 签名）
├── docs/           # dev/ 开发文档 + products/ 业务文档（RAG 仅索引 products/）
├── tests/          # 25个测试（API 5 + 检索 7 + 工具 9 + MCP schema 4）
└── data/           # SQLite DB + 商品图片
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
- [x] 电商客服（9工具：知识库/订单/物流/退换货/商品/图片识别/语音/计算/时间）
- [x] Vue 3 前端重构
- [x] 前端「盒中速递」设计系统（SwooshMark 签名 + 暗色模式）
- [x] SQLite 订单数据库 + 退款退货 + 物流跟踪
- [x] 4层请求路由 + 网关鉴权限流
- [x] 服务评价 + Token统计 + 用户画像
- [x] LLM 并发排队 (Semaphore 5并发 + 超时降级 503)

---

## 性能数据

| 指标 | 数值 |
|---|---|
| 路由命中率 | 95% (21/22) |
| 缓存响应 | ~3ms（HTTP 实测） |
| Agent 响应 | 4.6s 平均（4.1-5.4s，含完整工具调用循环） |
| 工具调用可靠性 | 100%（3/3 复测，修复 MCP args_schema 后） |
| Token 节省 | 88% (vs 全走Agent) |
| 测试覆盖 | 25 用例 |

> 数据说明：缓存响应 3ms 为 HTTP 层实测（含网络往返）；Agent 响应为主模型（DeepSeek）两次推理往返耗时，本地工具调用为毫秒级。工具调用可靠性经修复 `app/mcp_client.py` 空壳 schema 后从 0-33% 提升至 100%。

---

## License

MIT
