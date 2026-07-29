# 阶段 10：前端重构 — Vanilla JS → Vue 3 + Element Plus

> 目标：将纯原生前端重构为 Vue 3 组件化架构，提升可维护性和开发体验。

---

## 一、改动清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `frontend/` | **新建** | Vue 3 + Vite + Element Plus 项目 |
| `frontend/src/App.vue` | 新建 | 根布局：侧边栏 + 聊天视图 |
| `frontend/src/components/Sidebar.vue` | 新建 | 侧边栏组件：logo + 新对话 + 历史列表 + 删除 |
| `frontend/src/components/ChatView.vue` | 新建 | 主聊天视图：顶栏 + 消息列表 + 输入区 |
| `frontend/src/components/ChatMessage.vue` | 新建 | 消息气泡：SSE 流式渲染 + Markdown + 工具状态 |
| `frontend/src/components/WelcomeScreen.vue` | 新建 | 欢迎页：4 个建议问题按钮 |
| `frontend/src/composables/useChat.ts` | 新建 | 核心逻辑：SSE 流式 + 工具状态 + session 管理 |
| `frontend/vite.config.ts` | 新建 | 开发代理到 :8000 + 构建输出到 ../static |
| `main.py` | 修改 | 静态资源挂载 `/assets` + 版本号 v3.1.0 |
| `static/css/style.css` | 删除 | 旧 CSS（被 Element Plus 替代） |
| `static/js/chat.js` | 删除 | 旧 JS（被 useChat composable 替代） |
| `static/index.html` | 覆盖 | Vite 构建产物 |

---

## 二、组件树

```
App.vue
├── Sidebar.vue
│   └── localStorage 会话持久化
└── ChatView.vue
    ├── WelcomeScreen.vue  (无消息时显示)
    └── ChatMessage.vue × N  (消息列表)
        └── useChat.ts  (SSE 流式 + 工具状态)
```

---

## 三、技术对比

| | Vanilla JS | Vue 3 |
|---|---|---|
| 组件化 | 无（单文件 400 行） | 5 个 SFC 组件 |
| 状态管理 | 全局变量 + DOM | `ref` + `reactive` |
| 样式 | 手写 CSS | Element Plus + scoped |
| 开发 | 改完手动刷新 | Vite HMR 热更新 |
| 构建 | 无 | `npm run build` → `static/` |
| 类型检查 | 无 | TypeScript |
| SSE | `fetch + ReadableStream` | 同（逻辑移入 composable） |

---

## 四、测试结果

21 个测试全部通过。前端功能完整保留：SSE 打字机、Markdown 渲染、工具状态提示、历史会话管理。

---

## 五、版本

| 版本 | 里程碑 |
|---|---|
| v3.0.0 | 多智能体电商客服 |
| **v3.1.0** | **前端重构为 Vue 3 + Element Plus** |
