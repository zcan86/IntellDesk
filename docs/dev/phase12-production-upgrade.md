# 阶段 12：生产级升级汇总（v3.6 → v3.10）

> 2026-07-31 更新：订单数据库、退款退货、请求路由、网关鉴权、Token统计、语义路由、用户画像、评价系统

---

## 版本迭代

| 版本 | 内容 |
|---|---|
| v3.6.0 | SQLite 订单数据库（3用户/7订单，4种状态） |
| v3.7.0 | 退款退货功能（三重校验：签收状态+时效+类型区分） |
| v3.7.1 | 移除天气工具 |
| v3.7.2 | 物流跟踪使用真实数据（发货地+目的地+快递单号） |
| v3.8.0 | 请求分级路由（14条精确+12条关键词+语义+订单号正则） |
| v3.8.1 | Memory 5轮滑动窗口 |
| v3.8.2 | 会话 TTL 过期（60分钟）+ 手动清除 |
| v3.9.0 | 网关鉴权+限流+Token统计+语义路由+用户画像 |
| v3.10.0 | 服务评价系统（1-5星+评论+统计） |

## 新增文件

| 文件 | 职责 |
|---|---|
| `app/database.py` | SQLite（users/orders/return_requests/feedback） |
| `app/gateway.py` | API Key鉴权 + IP滑动窗口限流 |
| `app/stats.py` | Token用量 + 请求耗时统计 |
| `app/router.py` | 4层请求路由（精确→关键词→正则→语义） |

## 新增 API

| 端点 | 说明 |
|---|---|
| `GET /api/orders/{user_id}` | 用户订单列表 |
| `GET /api/order/{id}` | 订单详情 |
| `GET /api/profile/{user_id}` | 用户画像（消费/偏好/等级/可退订单） |
| `GET /api/stats` | Token统计 |
| `POST /api/feedback` | 提交评价 |
| `GET /api/feedback/stats` | 评价统计 |
| `DELETE /api/session/{id}` | 清除会话 |

## 完整架构

```
用户输入
  → 网关(鉴权+限流)
  → 记忆(5轮窗口+60分TTL)
  → 路由(精确14→关键词12→正则→语义10→Agent)
  → 执行(ReAct+工具限制+MCP)
  → 输出(SSE+Token统计)
  → 反馈(打星+评论)
```
