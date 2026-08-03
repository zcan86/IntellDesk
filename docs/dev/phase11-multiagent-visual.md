# 阶段 11：多 Agent 调度可视化

> 目标：将多 Agent 编排过程从隐式（代码内部）变为显式（SSE 事件 + 前端展示）。

---

## 一、新增

| 文件 | 说明 |
|---|---|
| `app/agents/orchestrator.py` | 多 Agent 编排器：规划任务 → 分派 Agent → 记录轨迹 |

## 二、修改

| 文件 | 改动 |
|---|---|
| `app/routers/chat.py` | SSE 新增 `agent_start`/`agent_end` 事件 + `done` 含调度轨迹 |
| `frontend/src/composables/useChat.ts` | 处理 agent_start/agent_end 事件 + 展示 Agent 名称 |

---

## 三、多 Agent 架构

```
用户查询
  │
  ▼
Orchestrator.plan_task()
  │  classify_intent(query) → LLM 意图识别
  │  主意图 + 关键词分析
  │  判断是否需要多个 Agent（规则引擎）
  │
  ▼ 调度计划
  SSE: agent_start → "订单Agent"
  │
  ▼
Agent.invoke() 执行
  │  tool_start / tool_end
  │  token 流式输出
  │
  ▼
  SSE: agent_end ← "订单Agent"
  SSE: done ← 含完整调度轨迹
```

## 四、7 个专业 Agent

| Agent | 意图 | 推荐工具 |
|---|---|---|
| 订单Agent | order | query_order, track_delivery |
| 售后Agent | return | return_guide, search_knowledge_base |
| 商品Agent | product | product_search, search_knowledge_base |
| 物流Agent | shipping | track_delivery, search_knowledge_base |
| 支付Agent | payment | search_knowledge_base |
| 账号Agent | account | search_knowledge_base |
| 综合Agent | general | 通用工具兜底 |

## 五、测试

```
"帮我查订单 DD20240001 和退货流程"
  → Orchestrator: 主意图 order, 置信度 60%
  → 调度: 订单Agent
  → SSE: agent_start → agent_end → done (含轨迹)
```
