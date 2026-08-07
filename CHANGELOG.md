# Changelog

本项目所有重要变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，语义化版本见 `main.py` / `mcp_server/server.py` 的 `version`。

## [3.4.0] - 2026-08-03

### Added
- **前端「盒中速递」设计系统**：墨黑 × 鞋盒橙 × 店内暖白，橙色勾形 swoosh 签名元素（`SwooshMark.vue`），暗色模式自适应、reduced-motion 支持
- 本地 fontsource 字体包（ZCOOL 黄油体 / Noto Sans SC / JetBrains Mono），不依赖外网 CDN
- `CHANGELOG.md`（本文件）
- **MCP schema 回归测试**（`tests/test_mcp_client.py`，4 例）：守护 `_make_args_model` 产出具名参数，防止退回 `**kwargs` 空壳 schema

### Fixed
- **移除全部回复中的 emoji**：工具输出（ecommerce/router/builtin_tools/knowledge_search）与 System Prompt 规则统一去掉 emoji 表情，避免测试断言时 emoji（如 ❌）与同形字符（如字母 X）肉眼难辨导致断言失败（`app/tools/*` / `app/router.py` / `app/agent.py`）
- **修复 MCP 工具间歇性不被调用**：`**kwargs` 签名使 langchain 从函数签名推断出空壳参数 schema（`{kwargs: {type: object, additionalProperties: true}}`），DeepSeek 拿到模糊参数间歇性放弃调用工具，只输出"我来查询"类承诺句而卡住。现从 MCP `inputSchema` 动态生成 pydantic `args_schema`（`app/mcp_client.py`），工具调用恢复稳定
- **修正 System Prompt 工具名笔误**：`return_guide` → `process_return`（`app/agent.py`），避免退换货查询误导模型
- **前端侧栏"新对话"按钮**：缩小尺寸、改为 6px 圆角，`white-space: nowrap` 保证文字单行（`frontend/src/components/Sidebar.vue`）
- **修复 reranker 阈值过滤失效**：`threshold=0.5` 在 1-5 分制下是空操作（所有分数都 ≥ 0.5），低分文档永不剔除。改为 `threshold=3`（丢弃"略有关联/完全无关"）（`app/rag/reranker.py`），新增 `tests/test_reranker.py`（4 例）守护过滤逻辑

### Changed
- 环境重建：原 venv 依赖的 miniconda 已移除，改用系统 Python 3.14 重建 venv 并重装依赖
- `langchain-core` 降至 **1.4.9**，匹配 `langchain 1.3.14` + `langchain-openai 1.4.0`（1.5.x 引入工具调用回归）
- README 同步：9 工具、多模态识别、设计系统、项目结构、环境搭建说明
- **Agent 状态显式建模**：新增 `AgentState`（`messages` + `order_context` + `intent`）传给 `create_agent`；请求层 `analyze_request` 提取订单号/意图播种状态，并以「【订单上下文】」SystemMessage 注入对话，LLM 不再从文本推断订单号；路由命中写记忆时同步播种显式字段（`app/agent.py` / `app/router.py` / `app/routers/chat.py`）
- 测试增至 32 例（新增 `tests/test_context.py` 守护订单上下文播种逻辑）
- **知识库并发加固**：`build_index` 只要索引目录存在就加载、**不判断 count**，杜绝多实例（后端 reload + MCP 双进程）并发访问同一 SQLite 时 `count()` 因锁/视图返回 0 或报错而误触发 `from_texts` 重复追加——从根上消除索引膨胀（`app/rag/loader.py`，实测并发下稳定 35 块）
- 开发文档新增 `docs/dev/phase13-agent-state-architecture.md`、`docs/dev/architecture-overview.md`（架构解析：分层/技术选型理由/搭建顺序）；**约定：后续每次改动同步更新开发文档**

### Removed
- 删除 `docs/项目总结-简历版.md`
- **开发文档迁出项目仓库**：`docs/dev/` 全部移入 Obsidian 知识库（`D:\obsidianStore\项目01-IntellDesk`），项目内 `docs/` 只保留业务文档
- 清理 Vite 模板残留：`HelloWorld.vue` / `assets/vite.svg` / `assets/vue.svg` / `public/icons.svg`
- 清理未使用遗留：`mcp_server/tools/`（server.py 实际用 app/tools）、`mcp_server/docs/`、`gen_vue.py`、`test_llm.py`
- 清理 `.pytest_cache/` 与 `__pycache__` 缓存
