# IntelliDesk — 项目开发约定

耐克电商客服 Agent：FastAPI + LangGraph + Adaptive-RAG + MCP + Vue3。

## 开发文档约定（必须遵守）

**每次实质性改动，同步更新开发文档：**

| 改动类型 | 必须更新 |
|---|---|
| Feature / Bugfix / 架构 | `docs/dev/` 对应 phase 文档 + `CHANGELOG.md` |
| 小修（格式/注释/配置） | 仅 `CHANGELOG.md` |

- `docs/dev/` 是开发历史文档（phase 系列），`docs/products/` 是 RAG 知识源（**只有后者被索引**，勿把开发文档放进去）
- CHANGELOG 格式：`## [版本] - 日期`，分 `Added / Fixed / Changed / Removed`

## 运行环境（实测关键事实）

- **venv 用 Python 3.14 重建过**（原 miniconda 环境已失效）。启动：`venv/Scripts/python.exe`（Windows）
- 依赖已升级支持 3.14：`pydantic`、`langchain-core 1.4.9`（**勿升 1.5.x**，会引入工具调用回归）、`langgraph 1.2.9`、`chromadb`、`scikit-learn`
- 启动三件套：`python mcp_server/server.py`（:8100）→ `python main.py`（:8000）→ `cd frontend && npm run dev`（:5173）

## 架构要点

- Agent 用 `create_agent` + **自定义 `AgentState`**（`messages` / `order_context` / `intent`），订单上下文由 `analyze_request` 播种并注入 `【订单上下文】` SystemMessage
- 工具走 MCP（HTTP :8100），`app/mcp_client.py` 的 `_make_args_model` 必须从 inputSchema 生成具名参数 schema——**勿改回 `**kwargs` 空壳**，否则 DeepSeek 间歇性不调工具
- 知识库 `build_index` 幂等 + 并发加固：校验已有索引失败时**跳过重建**，勿回退 `from_texts` 追加

## 提交纪律

- `data/orders.db` 是演示数据，**测试跑过后会写入脏数据，提交前先 `git checkout -- data/orders.db`**
- `.env`（API 密钥）、`venv/`、`data/chroma_db/`、`frontend/dist/` 在 gitignore 中，勿提交
- 开发文档（phase*）与业务文档（products/*）目录分离，勿混放
