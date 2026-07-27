# 🤖 IntelliDesk — 智能客服 Agent

基于 **LangChain Agent + RAG + 多工具调用** 的 SaaS 产品智能客服系统。

用户输入自然语言问题 → Agent 自主判断意图 → 检索知识库或调用外部工具 → SSE 流式返回答案。

---

## 功能演示

![IntelliDesk Screenshot]()

启动后在浏览器打开 `http://localhost:8000`：

- 💬 **自然语言对话**：用户用中文提问，Agent 理解意图后回复
- 📚 **RAG 知识库检索**：上传产品文档，Agent 基于文档回答（不编造）
- 🔧 **多工具调用**：自动路由到天气查询、数学计算、时间查询等工具
- ⚡ **SSE 流式输出**：打字机效果，工具调用过程实时可见
- 🧠 **多轮对话记忆**：跨轮记住上下文，支持追问和澄清
- 📂 **历史会话管理**：侧边栏保存历史对话，可切换、删除

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
┌──────┐┌─────┐┌──────┐┌──────────┐
│知识库││天气 ││计算器││当前时间   │
│RAG   ││wttr ││eval  ││datetime  │
│TF-IDF││.in  ││沙箱  ││          │
└──────┘└─────┘└──────┘└──────────┘
```

| 层级 | 技术 | 说明 |
|---|---|---|
| 前端 | HTML5 + CSS3 + Vanilla JS | 零框架，纯原生实现 |
| 后端 | FastAPI + Pydantic | 异步 HTTP 服务 |
| Agent | LangChain + LangGraph | ReAct Agent + MemorySaver |
| 检索 | scikit-learn TF-IDF | 零依赖检索，无需 Embedding 模型 |
| LLM | DeepSeek Chat (OpenAI 兼容) | 可替换为任意兼容服务 |

---

## 快速开始

### 1. 环境要求

- Python 3.12+
- DeepSeek API Key（[申请地址](https://platform.deepseek.com/)）

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
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxxxxxxx
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
│   │   └── loader.py         # 文档加载 → 切分 → TF-IDF 索引 → 检索
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
- [ ] 优化：Embedding 升级为硅基流动 BGE-M3
- [ ] 优化：工具调用迭代次数限制
- [ ] 优化：企业微信 / 飞书 Bot 接入

---

## License

MIT
