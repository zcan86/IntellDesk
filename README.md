# 🤖 IntelliDesk — 智能客服 Agent

基于 **LangGraph 多智能体 + Adaptive-RAG + MCP 协议 + 电商工具链** 的电商智能客服系统。7 类意图自动路由，8 个工具覆盖订单/物流/退换货/商品推荐全场景。

用户输入自然语言问题 → Agent 自主判断意图 → 检索知识库或调用外部工具 → SSE 流式返回答案。

---

## 功能演示

![IntelliDesk Screenshot]()

启动后在浏览器打开 `http://localhost:8000`：

- 💬 **自然语言对话**：用户用中文提问，Agent 理解意图后回复
- 📚 **Adaptive-RAG 检索**：混合检索（BM25 + BGE-m3）+ RRF 融合 + LLM Rerank + Self-RAG 反思
- 🔧 **多工具调用**：自动路由到天气查询、数学计算、时间查询等工具
- ⚡ **SSE 流式输出**：打字机效果，工具调用过程实时可见
- 🧠 **多轮对话记忆**：跨轮记住上下文，支持追问和澄清
- 📂 **历史会话管理**：侧边栏保存历史对话，可切换、删除
- 🔌 **MCP 协议支持**：三种工具模式（直接/MCP本地/MCP远程），配置文件一键切换

---

## 技术架构

```
┌──────────────────────┐
│    前端 (Vanilla JS)  │  SSE 流式消费 + Markdown 渲染 + localStorage 会话管理
└──────────┬───────────┘
           │ POST /api/chat/stream
┌──────────▼───────────┐
│   FastAPI 服务层      │  路由分发 + 会话管理 + 静态文件
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  LangGraph Agent     │  ReAct 循环: 思考 → 决策 → 工具调用 → 综合回答
│  (MemorySaver)       │  多轮记忆: thread_id 隔离会话上下文
└──────────┬───────────┘
           │
    ┌──────┼──────┬──────────┐
    ▼      ▼      ▼          ▼
┌──────────┐┌─────┐┌──────┐┌──────────┐
│ 知识库    ││天气 ││计算器││当前时间   │
│ ChromaDB ││wttr ││eval  ││datetime  │
│ BGE-m3   ││.in  ││沙箱  ││          │
└──────────┘└─────┘└──────┘└──────────┘
```

| 层级 | 技术 | 说明 |
|---|---|---|
| 前端 | HTML5 + CSS3 + Vanilla JS | 零框架，纯原生实现 |
| 后端 | FastAPI + Pydantic | 异步 HTTP 服务 |
| Agent | LangChain + LangGraph | ReAct Agent + MemorySaver |
| 检索 | Adaptive-RAG (ChromaDB + BGE-m3 + BM25 + RRF + LLM Rerank) | 混合检索融合 + 重排序 + Self-RAG 反思 |
| 工具协议 | **MCP** (Model Context Protocol) | HTTP transport，工具可独立部署为 McpToolServer |
| LLM | DeepSeek Chat (OpenAI 兼容) | 可替换为任意兼容服务 |

---

## 快速开始

### 1. 环境要求

- Python 3.12+
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）
- SiliconFlow API Key（[申请地址](https://cloud.siliconflow.cn/)，用于 Embedding）

### 2. 安装

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/intellidesk.git
cd intellidesk

# 创建虚拟环境
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入：
#   DEEPSEEK_API_KEY=sk-xxxxxxxx      （DeepSeek 大模型）
#   EMBEDDING_API_KEY=sk-xxxxxxxx     （硅基流动 Embedding）
```

### 3. 验证 LLM 连通性

```bash
python test_llm.py
# 看到 "✅ DeepSeek API 连接成功！" 即正常
```

### 4. 启动服务

```bash
python main.py
```

浏览器打开 `http://localhost:8000`。

### 5. Docker 部署（可选）

```bash
docker compose up -d
# 服务运行在 http://localhost:8000
```

---

## 项目结构

```
intellidesk/
├── app/
│   ├── agent.py              # Agent 核心（LLM + System Prompt + MemorySaver）
│   ├── config.py             # 全局配置（pydantic-settings）
│   ├── rag/
│   │   └── loader.py         # 文档加载 → 切分 → ChromaDB 向量索引 → 语义检索
│   ├── routers/
│   │   └── chat.py           # API 路由（chat / stream / reindex）
│   └── tools/
│       ├── knowledge_search.py  # 知识库检索 Tool
│       └── builtin_tools.py     # 天气 / 计算器 / 时间 Tool
├── static/
│   ├── index.html            # 聊天界面
│   ├── css/style.css         # 样式
│   └── js/chat.js            # 聊天逻辑（SSE + Markdown + localStorage）
├── docs/
│   ├── knowledge/            # 各阶段知识点文档
│   │   ├── phase0-setup.md
│   │   ├── phase1-agent.md
│   │   ├── phase2-rag.md
│   │   ├── phase3-tools.md
│   │   ├── phase4-stream-memory.md
│   │   └── phase5-frontend.md
│   └── products/             # 产品文档（RAG 知识库数据源）
│       ├── product-manual.md
│       ├── pricing.md
│       └── faq.md
├── tests/
│   ├── test_rag.py           # RAG 单元测试
│   ├── test_tools.py         # 工具单元测试
│   └── test_api.py           # API 集成测试
├── main.py                   # 应用入口
├── test_llm.py               # LLM 连通性测试
├── Dockerfile
├── docker-compose.yaml
└── requirements.txt
```

---

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/health` | 健康检查 + 知识库状态 |
| `POST` | `/api/chat` | 普通对话（非流式，支持 session_id） |
| `POST` | `/api/chat/stream` | SSE 流式对话 |
| `POST` | `/api/documents/reindex` | 重建知识库索引 |

### 流式响应事件类型

| type | 含义 |
|---|---|
| `token` | LLM 输出的文本片段 |
| `tool_start` | 开始调用工具（含工具名） |
| `tool_end` | 工具调用完成 |
| `done` | 本轮处理完成（含 session_id） |
| `error` | 处理出错 |

---

## 运行测试

```bash
# 全部测试
pytest tests/ -v

# 按模块测试
pytest tests/test_rag.py -v
pytest tests/test_tools.py -v
pytest tests/test_api.py -v
```

---

## 开发路线

- [x] 阶段 0：环境搭建 + DeepSeek 连通
- [x] 阶段 1：最简 Agent 对话骨架
- [x] 阶段 2：RAG 知识库检索（TF-IDF）
- [x] 阶段 3：多工具调用（天气 / 计算 / 时间）
- [x] 阶段 4：SSE 流式输出 + 多轮对话 Memory
- [x] 阶段 5：前端聊天界面
- [x] 阶段 6：测试 + Docker 部署
- [x] 优化：Embedding 升级为 ChromaDB + 硅基流动 BGE-m3 语义检索
- [x] 优化：MCP 协议集成 + 工具服务独立化（McpToolServer）
- [x] 优化：Adaptive-RAG 混合检索 + RRF 融合 + LLM Rerank + Self-RAG
- [x] 优化：专精为多智能体电商客服（意图路由 + 电商工具链 + 场景化知识库）
- [ ] 优化：工具调用迭代次数限制
- [ ] 优化：企业微信 / 飞书 Bot 接入

---

## MCP 工具模式

| 模式 | `.env` 配置 | 说明 |
|---|---|---|
| 直接模式（默认） | `USE_MCP=false` | 工具代码在 `app/tools/`，import 即用 |
| 本地 MCP | `USE_MCP=true` + `MCP_SERVER_URL=http://127.0.0.1:8100` | 工具由本地 McpToolServer 进程提供 |
| 远程 MCP | `USE_MCP=true` + `MCP_SERVER_URL=http://公网IP:8100` | 工具部署在独立云服务器 |

McpToolServer 独立项目：[McpToolServer](https://github.com/zcan86/McpToolServer) — 可被任何 Agent（Coze、Claude Desktop 等）复用。

---

## License

MIT
