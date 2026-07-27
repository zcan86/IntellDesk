# 阶段 6：测试 + Docker + GitHub

> 目标：编写测试用例、Docker 化部署、准备 GitHub 仓库。

---

## 1. 阶段 6 做了什么

### 新建文件

| 文件 | 说明 |
|---|---|
| `tests/test_rag.py` | RAG 索引构建 + 检索测试（7 个用例） |
| `tests/test_tools.py` | 计算器 + 时间工具测试（9 个用例） |
| `tests/test_api.py` | API 接口测试（5 个用例，含 Memory 集成测试） |
| `Dockerfile` | Python 3.12-slim 单容器镜像 |
| `docker-compose.yaml` | 一键启动编排 |
| `.dockerignore` | 排除 venv/git/logs 等 |
| `README.md` | 完整项目文档 |

---

## 2. 测试结果

```
tests/test_rag.py::TestRAGIndex::test_build_index PASSED
tests/test_rag.py::TestRAGIndex::test_build_index_skips_when_ready PASSED
tests/test_rag.py::TestRAGIndex::test_build_index_nonexistent_dir PASSED
tests/test_rag.py::TestRAGSearch::test_search_returns_results PASSED
tests/test_rag.py::TestRAGSearch::test_search_irrelevant_query PASSED
tests/test_rag.py::TestRAGSearch::test_search_top_k PASSED
tests/test_rag.py::TestRAGSearch::test_search_empty_query PASSED
tests/test_tools.py::TestCalculator::test_basic_arithmetic PASSED
tests/test_tools.py::TestCalculator::test_multiplication PASSED
tests/test_tools.py::TestCalculator::test_complex_expression PASSED
tests/test_tools.py::TestCalculator::test_sqrt PASSED
tests/test_tools.py::TestCalculator::test_division_by_zero PASSED
tests/test_tools.py::TestCalculator::test_syntax_error PASSED
tests/test_tools.py::TestCalculator::test_no_dangerous_code PASSED
tests/test_tools.py::TestGetCurrentTime::test_returns_time PASSED
tests/test_tools.py::TestGetCurrentTime::test_returns_weekday PASSED
tests/test_api.py::test_health_check PASSED
tests/test_api.py::test_chat_without_tools PASSED
tests/test_api.py::test_chat_empty_message PASSED
tests/test_api.py::test_chat_session_memory PASSED
tests/test_api.py::test_documents_reindex PASSED

============================= 21 passed =============================
```

---

## 3. Docker 部署

### 构建和启动

```bash
docker compose up -d
```

服务运行在 `http://localhost:8000`。

### 单容器设计

因为项目不需要数据库（TF-IDF 是内存索引），所以一个容器就够了。`Dockerfile` 基于 `python:3.12-slim` 镜像，启动时自动构建知识库索引。

---

## 4. GitHub 上传

```bash
cd D:\IntellDesk
git init
git add .
git commit -m "init: IntelliDesk — 智能客服 Agent v0.4.0"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/intellidesk.git
git push -u origin main
```

### 上传前确认

- [x] `.env` 在 `.gitignore` 中（密钥不会泄露）
- [x] `venv/` 在 `.gitignore` 中
- [x] `README.md` 完整
- [x] 21 个测试通过

---

## 5. 项目完整检查清单

- [x] 环境搭建 + DeepSeek 连通
- [x] Agent 对话骨架
- [x] RAG 知识库（TF-IDF + 3 份产品文档）
- [x] 4 工具路由（知识库 + 天气 + 计算 + 时间）
- [x] SSE 流式输出 + Memory 多轮记忆
- [x] 前端聊天界面 + 历史会话
- [x] 21 个测试用例全部通过
- [x] Docker 一键部署
- [x] README.md 完整文档
- [x] 6 份知识文档（docs/knowledge/）
