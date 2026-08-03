# 阶段 7：MCP 协议集成 + 工具服务独立化

> 目标：将 Agent 工具从硬编码解耦为标准 MCP 协议，并分离为可独立部署的 McpToolServer。

---

## 一、改动清单

### IntelliDesk（主项目）修改

| 文件 | 操作 | 说明 |
|---|---|---|
| `app/config.py` | 修改 | 新增 `USE_MCP`（开关）和 `MCP_SERVER_URL`（远程地址） |
| `app/mcp_client.py` | **新建** | 纯 HTTP MCP Client：`GET /mcp/tools` 发现工具，`POST /mcp/call` 执行工具，封装为 LangChain Tool |
| `app/routers/chat.py` | 修改 | `get_agent()` 支持 MCP 模式：`USE_MCP=true` 时从远程加载工具，`false` 时用本地 import |
| `requirements.txt` | 修改 | 新增 `mcp==2.0.0` |
| `mcp_servers/knowledge_server.py` | 新建 | stdio 版本知识库 MCP Server（备用，主方案用 HTTP） |
| `mcp_servers/utility_server.py` | 新建 | stdio 版本工具 MCP Server（备用） |

### McpToolServer（新独立项目）

| 文件 | 说明 |
|---|---|
| `server.py` | FastAPI 主程序，暴露 `GET /mcp/tools` + `POST /mcp/call` + `GET /health` |
| `tools/weather.py` | 天气工具（Open-Meteo API，零 IntelliDesk 依赖） |
| `tools/calculator.py` | 计算器工具（安全沙箱 eval） |
| `tools/time_tool.py` | 时间工具 |
| `tools/knowledge.py` | 知识库检索（独立 ChromaDB + BGE-m3） |
| `Dockerfile` | Docker 镜像 |
| `docker-compose.yaml` | 一键部署 |
| `deploy/阿里云部署指南.md` | 阿里云 ECS 部署步骤 |
| `deploy/systemd.service` | Systemd 服务文件 |

---

## 二、MCP 协议在本项目的实现

### 协议定义

| 端点 | 方法 | 作用 |
|---|---|---|
| `/mcp/tools` | GET | 返回工具列表（name + description + inputSchema） |
| `/mcp/call` | POST | 执行工具 `{"name": "...", "arguments": {...}}` |

### 工具定义格式（MCP 标准）

```json
{
  "name": "get_weather",
  "description": "查询指定城市的当前天气",
  "inputSchema": {
    "type": "object",
    "properties": {
      "city": {"type": "string", "description": "城市名称"}
    },
    "required": ["city"]
  }
}
```

### 调用流程

```
IntelliDesk Agent
  │  需要调用工具
  ▼
app/mcp_client.py
  │  GET /mcp/tools → 发现 4 个工具
  │  封装为 LangChain Tool（@tool 装饰器）
  ▼
Agent 触发工具调用
  │  POST /mcp/call {"name":"get_weather","arguments":{"city":"北京"}}
  ▼
McpToolServer (:8100)
  │  路由到 tools/weather.py → get_weather("北京")
  │  返回 {"content":[{"type":"text","text":"🌍 北京 当前天气：..."}]}
  ▼
Agent 收到结果 → 综合 → 回复用户
```

---

## 三、三种运行模式

| 模式 | `.env` 配置 | 工具来源 |
|---|---|---|
| **直接模式**（默认） | `USE_MCP=false` | `app/tools/` 本地 import |
| **本地 MCP** | `USE_MCP=true` + `MCP_SERVER_URL=http://127.0.0.1:8100` | 本地 McpToolServer 进程 |
| **远程 MCP** | `USE_MCP=true` + `MCP_SERVER_URL=http://公网IP:8100` | 云端 McpToolServer |

### 切换方式

改 `.env` 一行，重启服务即生效，无需改代码。

---

## 四、为什么这样做（架构价值）

### 没有 MCP 之前

```
Agent 进程
  ├── agent.py
  ├── tools/knowledge_search.py    ← 工具代码和 Agent 耦合
  └── tools/builtin_tools.py       ← 改工具 = 重启 Agent
```

### 有 MCP 之后

```
Agent 进程（IntelliDesk）          MCP Server 进程（McpToolServer）
  │                                    │
  │  HTTP: 发现工具有哪些               │  tools/weather.py
  │  ───────────────────────────────→  │  tools/calculator.py
  │                                    │  tools/time_tool.py
  │  HTTP: 执行这个工具                 │  tools/knowledge.py
  │  ───────────────────────────────→  │
  │                                    │  (独立部署、独立扩缩容、
  │  ← 返回结果                        │   跨语言复用、任何 Agent 可调)
```

### 简历能讲什么

- **MCP 协议理解**：不是只会调 API，而是理解 Agent-工具通信协议的标准化
- **工具解耦设计**：工具定义、参数 schema、执行逻辑全部由 Server 端提供
- **架构扩展性**：同一套工具可以被 Coze、Claude Desktop、IntelliDesk 等任意 Agent 复用
- **零侵入切换**：一个 `USE_MCP` 开关在三种模式间切换

---

## 五、踩坑记录

### 1. MCP 2.0 SDK 的 stdio transport 不稳定

`mcp` 库的 `stdio_client` + `Server.run()` 在 Windows 下出现 `ExceptionGroup` 错误，子进程通信频繁断开。

**解决**：放弃 stdio transport，改用 HTTP transport。创建 FastAPI 应用暴露 MCP 端点，MCP Client 通过 `httpx` 调 HTTP 接口。更稳定、更易调试、更贴近生产环境。

### 2. Server 构造函数 API 变更

MCP 2.0 的 `Server.on_list_tools` 不是装饰器，handler 需要在构造函数中传入：

```python
# 错误
@server.on_list_tools
async def list_tools(): ...

# 正确
server = Server("name", on_list_tools=list_tools_handler, on_call_tool=call_tool_handler)
```

### 3. Server.run() 需要 initialization_options

```python
init_opts = server.create_initialization_options()
await server.run(read_stream, write_stream, init_opts)
```

### 4. GitHub 502

推送时 GitHub 频繁返回 502，多次重试后成功。

---

## 六、测试结果

```bash
# McpToolServer 测试
curl http://127.0.0.1:8100/health
# → {"status":"ok","service":"McpToolServer","kb":"58 chunks"}

curl http://127.0.0.1:8100/mcp/tools
# → 返回 4 个工具定义

# IntelliDesk MCP Client 测试
python -c "from app.mcp_client import load_mcp_tools; print(len(load_mcp_tools()))"
# → 4 个工具全部加载 ✅
```
