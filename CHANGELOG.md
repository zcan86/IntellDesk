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
- **修复 MCP 工具间歇性不被调用**：`**kwargs` 签名使 langchain 从函数签名推断出空壳参数 schema（`{kwargs: {type: object, additionalProperties: true}}`），DeepSeek 拿到模糊参数间歇性放弃调用工具，只输出"我来查询"类承诺句而卡住。现从 MCP `inputSchema` 动态生成 pydantic `args_schema`（`app/mcp_client.py`），工具调用恢复稳定
- **修正 System Prompt 工具名笔误**：`return_guide` → `process_return`（`app/agent.py`），避免退换货查询误导模型
- **前端侧栏"新对话"按钮**：缩小尺寸、改为 6px 圆角，`white-space: nowrap` 保证文字单行（`frontend/src/components/Sidebar.vue`）

### Changed
- 环境重建：原 venv 依赖的 miniconda 已移除，改用系统 Python 3.14 重建 venv 并重装依赖
- `langchain-core` 降至 **1.4.9**，匹配 `langchain 1.3.14` + `langchain-openai 1.4.0`（1.5.x 引入工具调用回归）
- README 同步：9 工具、多模态识别、设计系统、项目结构、环境搭建说明
- **Agent 状态显式建模**：新增 `AgentState`（`messages` + `order_context` + `intent`）传给 `create_agent`；请求层 `analyze_request` 提取订单号/意图播种状态，并以「【订单上下文】」SystemMessage 注入对话，LLM 不再从文本推断订单号；路由命中写记忆时同步播种显式字段（`app/agent.py` / `app/router.py` / `app/routers/chat.py`）
- 测试增至 32 例（新增 `tests/test_context.py` 守护订单上下文播种逻辑）
- 开发文档新增 `docs/dev/phase13-agent-state-architecture.md`；**约定：后续每次改动同步更新开发文档**

### Removed
- 删除 `docs/项目总结-简历版.md`
