# 阶段 9：专精为多智能体电商客服

> 目标：从 SaaS 产品客服转型为速购电商多智能体客服系统。

---

## 一、转型动因

### 之前

```
IntelliDesk — SaaS 产品客服
  ├── 知识库: 产品手册 + 计费规则 + API文档
  ├── 工具: 知识库检索 + 天气 + 计算 + 时间
  └── 场景: 回答 IntelliDesk 产品功能/价格/API 问题
```

### 之后

```
速购电商 — 多智能体客服
  ├── 知识库: 退换货政策 + 配送规则 + 商品分类 + FAQ
  ├── 工具: 知识库 + 订单查询 + 物流跟踪 + 退换货指引 + 商品搜索 + 天气 + 计算 + 时间
  ├── 意图路由: 7 类自动分类（订单/退换货/商品/物流/支付/账号/通用）
  └── 子 Agent: 7 个专业 Prompt 模板
```

---

## 二、新增文件

| 文件 | 职责 |
|---|---|
| `app/agents/router.py` | 意图识别节点 + 7 类子 Agent Prompt |
| `app/tools/ecommerce.py` | 4 个电商工具（订单/物流/退换货/商品搜索） |
| `docs/products/returns.md` | 退换货政策（7天无理由/15天换货/特殊场景） |
| `docs/products/shipping.md` | 配送说明（快递/包邮/时效/物流查询） |
| `docs/products/products.md` | 商品分类 + 热销 TOP5 + 会员权益 + 促销活动 |
| `docs/products/faq.md` | 常见问题（订单/支付/售后/账号/优惠券） |

## 三、修改文件

| 文件 | 改动 |
|---|---|
| `app/agent.py` | System Prompt 重写为速购电商「小速」+ 8 工具 |
| `app/routers/chat.py` | 注入 4 个电商工具，MCP 降级列表同步更新 |
| `static/index.html` | 品牌名、logo、欢迎语、建议问题全部更新 |
| `main.py` | App 标题更新 |

## 四、多智能体架构

```
用户输入
  │
  ▼
router.py: classify_intent()
  │  LLM 意图识别 → {"intent": "order", "confidence": 0.95}
  │
  ├── order    → OrderAgent     (订单查询/修改/取消)
  ├── return   → ReturnAgent    (退换货/退款/售后)
  ├── product  → ProductAgent   (商品推荐/对比)
  ├── shipping → ShippingAgent  (物流/配送/运费)
  ├── payment  → PaymentAgent   (支付/发票)
  ├── account  → AccountAgent   (账号/会员/优惠券)
  └── general  → GeneralAgent   (问候/闲聊/兜底)

每个子 Agent 有独立的 System Prompt，定义了该领域的：
  - 职责边界
  - 应调用的工具
  - 回复风格和规则
```

## 五、8 工具矩阵

| 工具 | 来源 | 触发场景 |
|---|---|---|
| search_knowledge_base | Adaptive-RAG | 退换货政策/配送规则/FAQ |
| query_order | `app/tools/ecommerce.py` | 用户提供订单号查状态 |
| track_delivery | `app/tools/ecommerce.py` | 用户问物流到哪了 |
| return_guide | `app/tools/ecommerce.py` | 用户问怎么退换货 |
| product_search | `app/tools/ecommerce.py` | 用户找商品/推荐 |
| get_weather | Open-Meteo | 天气 |
| calculator | Python eval | 计算 |
| get_current_time | datetime | 时间 |

## 六、测试结果

```
21 passed

"我想退货怎么操作？"    → Agent 调 return_guide + 知识库 → 4步流程 ✅
"查订单 DD20240001"     → Agent 调 query_order → 商品/金额/状态 ✅
"有没有蓝牙耳机推荐？"   → Agent 调 product_search → TOP2 ✅
"满多少包邮？"          → Agent 调知识库 → ¥99全国 ✅
```

## 七、版本

| 版本 | 里程碑 |
|---|---|
| v0.1.0 | 单 Agent 对话 |
| v0.2.0 | RAG 知识库（TF-IDF） |
| v0.3.0 | 多工具调用 |
| v0.4.0 | SSE + Memory |
| v0.5.0 | ChromaDB + BGE-m3 |
| v2.0.0 | Adaptive-RAG |
| **v3.0.0** | **多智能体电商客服** |
