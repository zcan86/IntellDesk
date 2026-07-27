# IntelliDesk 产品手册 v2.1

> 最后更新：2025-07-20
> 适用版本：IntelliDesk Cloud v2.x

---

## 1. 产品概述

IntelliDesk 是一个基于大语言模型（LLM）的智能客服 SaaS 平台。你可以上传产品文档、API 手册和 FAQ，IntelliDesk 会自动构建知识库，让你的客户通过自然语言对话获取答案，无需人工客服介入。

### 核心能力

| 能力 | 说明 |
|---|---|
| **知识库问答** | 上传 Markdown / PDF / Word 文档，自动构建向量索引，支持自然语言检索 |
| **多工具调用** | Agent 可调用天气查询、订单查询、数学计算等外部工具 |
| **多轮对话** | 自动维护对话上下文，支持追问、澄清和补全 |
| **流式响应** | 基于 SSE 协议逐字输出，首 Token 延迟 <1.5 秒 |
| **报告导出** | 支持将对话记录导出为 Markdown / PDF |

### 系统架构

```
用户浏览器
    │  HTTP / SSE
    ▼
FastAPI 服务层（路由、认证、限流）
    │
    ▼
LangChain Agent 引擎（ReAct 模式）
    ├── RAG 检索器（ChromaDB 向量库）
    ├── 工具执行器（天气、订单、计算器...）
    └── Memory 管理器（多轮对话上下文）
```

---

## 2. 快速开始

### 2.1 注册账号

访问 [https://intellidesk.com/signup](https://intellidesk.com/signup)，使用邮箱注册。注册完成后会自动创建一个**免费版**工作区，支持 1 个知识库、100 次对话/月。

### 2.2 创建知识库

1. 登录控制台 → 点击左侧菜单「知识库」
2. 点击「新建知识库」，输入名称（如"产品帮助中心"）
3. 上传文档：支持 Markdown（`.md`）、PDF（`.pdf`）、Word（`.docx`）、纯文本（`.txt`）
4. 等待索引完成（通常 <30 秒，取决于文档大小）
5. 索引完成后，点击「测试」验证检索效果

### 2.3 嵌入到你的网站

在控制台 → 「部署」页面，复制以下代码到你网站的 `<head>` 标签中：

```html
<script src="https://cdn.intellidesk.com/widget/v2.js"></script>
<script>
  IntelliDesk.init({
    workspaceId: "ws_xxxxxxxx",
    theme: "light",           // light | dark | auto
    position: "bottom-right", // bottom-right | bottom-left
    title: "智能客服",
    placeholder: "输入你的问题...",
  });
</script>
```

刷新你的网站页面，右下角会出现 IntelliDesk 聊天窗口。

### 2.4 通过 API 集成

如果你需要更灵活的控制，可以使用 REST API：

```bash
# 创建会话
curl -X POST https://api.intellidesk.com/v2/sessions \
  -H "Authorization: Bearer sk-xxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"workspace_id": "ws_xxxxxxxx"}'
# 返回: {"session_id": "sess_abc123"}

# 发送消息
curl -X POST https://api.intellidesk.com/v2/chat \
  -H "Authorization: Bearer sk-xxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sess_abc123", "message": "如何退货？"}'
# 返回: {"reply": "您好，退货流程如下...", "sources": [...]}
```

---

## 3. 知识库管理

### 3.1 文档格式要求

| 格式 | 最大文件大小 | 说明 |
|---|---|---|
| Markdown (`.md`) | 10 MB | **推荐格式**，支持标题层级、表格、代码块 |
| PDF (`.pdf`) | 20 MB | 支持文本型 PDF，扫描版需 OCR（Pro 及以上） |
| Word (`.docx`) | 15 MB | 支持标准 .docx 格式 |
| 纯文本 (`.txt`) | 5 MB | 无格式纯文本 |

### 3.2 文档切分策略

IntelliDesk 使用以下策略处理上传的文档：

1. **智能分段**：按 Markdown 标题层级（`#` → `##` → `###`）优先切分，保持语义完整性
2. **块大小**：500 字符/块，重叠 50 字符（可在「高级设置」中调整）
3. **元数据保留**：每块保留来源文档名、标题路径、页码
4. **增量更新**：新增文档不重建整个索引，只索引新增部分

### 3.3 检索精度优化

在知识库「设置」页面可以调整：

| 参数 | 默认值 | 说明 |
|---|---|---|
| 检索 Top-K | 3 | 每次检索返回的相关片段数量 |
| 相似度阈值 | 0.70 | 低于此值的结果会被丢弃 |
| Rerank | 关闭 | 开启后使用重排序模型提升精度（Pro+） |

---

## 4. Agent 行为配置

### 4.1 System Prompt 自定义

在控制台 → 「Agent」→ 「System Prompt」，可以自定义 Agent 的行为：

```markdown
你可以修改以下内容：
- 角色名称和个性
- 回答风格（简洁/详细）
- 知识库外的行为（拒绝回答 / 尝试通用建议）
- 特定场景的处理逻辑
```

### 4.2 工具开关

在「Agent」→ 「工具」页面，可以开启/关闭内置工具：

| 工具 | 说明 | 免费版 | Pro | Enterprise |
|---|---|---|---|---|
| 知识库检索 | 检索已上传文档 | ✅ | ✅ | ✅ |
| 天气查询 | 调用公开天气 API | ❌ | ✅ | ✅ |
| 数学计算 | 安全四则运算 | ✅ | ✅ | ✅ |
| 自定义工具 | 用户自定义 API 工具 | ❌ | ❌ | ✅ |

---

## 5. 数据安全

- **数据加密**：传输层 TLS 1.3，存储层 AES-256
- **向量库隔离**：每个工作区使用独立的 ChromaDB Collection
- **API Key 管理**：支持创建、轮换、删除 API Key，可设置过期时间
- **审计日志**：Enterprise 版支持完整的操作审计日志
- **合规**：已通过 SOC 2 Type II 认证

---

## 6. 故障排查

### 6.1 知识库检索不到内容

1. 检查文档是否成功上传（控制台 → 知识库 → 文档列表）
2. 尝试在「测试」面板用文档中的原句搜索
3. 降低相似度阈值（默认 0.70 → 0.50）
4. 增大 Top-K 值（默认 3 → 5）
5. 检查文档是否为扫描版 PDF（扫描版需要 OCR，Pro 版以上支持）

### 6.2 Agent 回复不准确

1. 检查知识库中是否包含相关答案
2. 在 System Prompt 中加入："如果不确定，请诚实告知，不要编造"
3. 开启 Rerank 功能（Pro 版以上）
4. 调整 Temperature 参数（降低到 0.3 可以让回答更确定）

### 6.3 API 返回 429（请求过多）

免费版限制 30 次请求/分钟。如果业务量较大，请升级到 Pro 版（300 次/分钟）或 Enterprise 版（无限制）。
