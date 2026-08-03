# 阶段 8：Adaptive-RAG 检索升级

> 目标：将单一语义检索升级为 Adaptive-RAG（混合检索 + RRF 融合 + LLM Rerank + Self-RAG 反思）。

---

## 一、为什么升级

### 之前的问题

```
单一 ChromaDB 语义检索：
  用户: "免费版能用 API 吗？"  →  BGE-m3 向量匹配  →  返回 3 条结果

问题:
  1. 纯语义检索对精确关键词（API/Pro/Free）不够敏感
  2. 没有质量校验——返回了不相关的文档块也没人检查
  3. 同义改写"不花钱的版本能调用接口吗"偶尔命中偏低
```

### 升级后

```
Adaptive-RAG 管线:
  用户问题
    → 查询分析（LLM 判断复杂度）
    → 混合检索（BM25 + BGE-m3 + RRF 融合）
    → LLM Rerank（DeepSeek 1-5 分重排序）
    → Self-RAG 反思（不够则改写查询重试）
    → 最终 Top-K
```

---

## 二、新增文件

| 文件 | 职责 | 核心技术 |
|---|---|---|
| `app/rag/hybrid_retriever.py` | BM25 关键词 + BGE-m3 语义 + RRF 融合 | RRF (Reciprocal Rank Fusion, k=60) |
| `app/rag/reranker.py` | LLM 重排序 | DeepSeek 评分 1-5，过滤 <阈值 文档 |
| `app/rag/adaptive_rag.py` | 查询分析 → 策略路由 → 反思循环 | Self-RAG: 不满足则改写查询重试 |

## 三、修改文件

| 文件 | 改动 |
|---|---|
| `app/tools/knowledge_search.py` | 从 `search_knowledge()` 改为 `adaptive_search()` |
| `app/rag/loader.py` | 构建 ChromaDB 索引后同步初始化 BM25 |
| `app/routers/chat.py` | MCP 模式失败时自动降级为直接模式 |
| `app/mcp_client.py` | 新增 `load_mcp_tools_sync()` 避免 asyncio 嵌套 |

---

## 四、核心技术详解

### 4.1 混合检索 + RRF 融合

```
语义检索（BGE-m3）：
  Rank 1: doc_A (语义最接近)
  Rank 2: doc_B
  Rank 3: doc_C

关键词检索（BM25）：
  Rank 1: doc_D (API 精确匹配)
  Rank 2: doc_A
  Rank 3: doc_E

RRF 融合: score(doc) = 1/(60+rank_semantic) + 1/(60+rank_keyword)

  最终排序:
  doc_A: 1/61 + 1/62 = 0.0164 + 0.0161 = 0.0325  ← 两个榜单都靠前
  doc_D: 0/61 + 1/61 = 0.0164                    ← 仅关键词榜第一
  doc_B: 1/62 + 0/61 = 0.0161                    ← 仅语义榜第二
```

### 4.2 LLM Rerank

不是 Cohere Rerank API 的付费方案，而是用 DeepSeek 自己做评分：

```
Prompt: "对以下 5 个文档片段对用户问题'免费版能用 API 吗？'的相关度打分（1-5）"

LLM 返回: [{"id":1,"score":5}, {"id":2,"score":3}, {"id":3,"score":1}]

过滤 score < 3 的，剩余的按 综合分 = 原始分*0.4 + LLM分/5*0.6 重排
```

### 4.3 Self-RAG 反思

```
检索 → 判断是否充分 → Yes → 返回
                    → No  → 改写查询 → 重新检索（最多 2 次）
```

改写示例：
```
原查询: "不花钱的版本可以调用接口吗？"
→ 反思: insufficient, 问题使用了口语化表达
→ 改写: "免费版 API 访问 限制"
→ 重新检索 → sufficient ✓
```

### 4.4 MCP 降级机制

```
启动 Agent
  → 尝试 MCP 连接
  → 成功 → MCP 模式（4 个远程工具）
  → 失败 → 降级为直接模式（4 个本地工具）
  → 日志: "MCP 连接失败，降级为直接模式"
```

---

## 五、版本迭代

| 版本 | 内容 |
|---|---|
| v0.5.0 | ChromaDB + BGE-m3 语义检索 |
| **v2.0.0** | **Adaptive-RAG: 混合检索 + RRF + LLM Rerank + Self-RAG** |

---

## 六、测试结果

```
21 passed in 23.61s

检索验证:
  "免费版能用 API 吗？"
    → [0.6066] 关键词匹配 | API集成章节 ✅
    → [0.4927] faq.md | 费用与计费 ✅

  "不花钱的版本可以调用接口吗？"
    → [0.6127] faq.md | API集成章节 ✅（语义理解成功）
    → [0.3664] pricing.md | 免费版限制详解 ✅
```
