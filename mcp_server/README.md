# McpToolServer — 独立 MCP 工具服务器

通用 Agent 工具服务器，通过 MCP 协议（HTTP transport）暴露工具。

**任何实现了 MCP Client 的 Agent 都可以调用本服务。**

---

## 提供的工具

| 工具 | 功能 |
|---|---|
| `search_knowledge_base` | ChromaDB + BGE-m3 语义检索 |
| `get_weather` | Open-Meteo 全球天气查询 |
| `calculator` | 安全沙箱数学计算 |
| `get_current_time` | 当前日期时间 |

---

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入 EMBEDDING_API_KEY
python server.py        # → http://127.0.0.1:8100
```

## MCP 接口

```bash
# 列出工具
curl http://127.0.0.1:8100/mcp/tools

# 调用工具
curl -X POST http://127.0.0.1:8100/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"name":"get_weather","arguments":{"city":"北京"}}'
```
