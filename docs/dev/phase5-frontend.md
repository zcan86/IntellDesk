# 阶段 5：前端聊天界面

> 目标：用纯 HTML/CSS/JS 做一个可直接演示的聊天界面，支持流式输出、Markdown 渲染、建议问题、多轮会话。

---

## 1. 阶段 5 改了什么

| 文件 | 操作 | 说明 |
|---|---|---|
| `static/index.html` | **重写** | 完整聊天 UI 布局（侧边栏 + 消息区 + 输入区） |
| `static/css/style.css` | **新建** | 全部样式（CSS 变量系统、气泡、Markdown、响应式） |
| `static/js/chat.js` | **新建** | 聊天逻辑（SSE 流式消费、消息渲染、session 管理） |
| `main.py` | **修改** | 新增 `StaticFiles` 挂载 `/static` 目录 |

---

## 2. 页面布局

```
┌──────────┬─────────────────────────────────────┐
│  侧边栏   │  顶栏：标题 + 状态指示器              │
│          ├─────────────────────────────────────┤
│  🤖 Logo  │                                     │
│          │  消息区（可滚动）                      │
│ + 新对话  │  ┌ 🤖 您好！我是小智...            │
│          │  │    欢迎界面 + 建议问题             │
│          │  └──────────────────────────────    │
│          │                                     │
│  v0.4.0  ├─────────────────────────────────────┤
│          │  [输入框........................] [➤]│
└──────────┴─────────────────────────────────────┘
```

### 组件关系

| 组件 | 作用 |
|---|---|
| 侧边栏 | Logo + 新对话按钮 + 版本号 |
| 欢迎界面 | 首次加载时展示，含 4 个建议问题 |
| 消息区 | 对话历史 + 流式输出中的消息 |
| 工具状态条 | 显示 `正在查询知识库...` + spinner 动画 |
| 气泡 | Agent（白色左侧）和用户（绿色右侧） |
| 输入区 | textarea 自动伸缩 + 发送按钮 |

---

## 3. 流式消费（SSE via fetch）

### 3.1 为什么用 fetch + ReadableStream 而不是 EventSource？

`EventSource` 只能发 GET 请求，不能带 Body。聊天需要 POST 传 `message` 和 `session_id`，所以用 `fetch` + `ReadableStream` 手动解析 SSE。

```javascript
const resp = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
});

const reader = resp.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";  // 保留不完整的最后一行

    for (const line of lines) {
        if (line.startsWith("data: ")) {
            const evt = JSON.parse(line.slice(6));
            handleSSEEvent(evt);
        }
    }
}
```

### 3.2 buffer 的作用

SSE 数据是流式到达的，一次 `read()` 拿到的数据可能被**截断**：

```
第一次 read: "data: {\"type\":\"to"     ← 被中间截断了
第二次 read: "ken\",\"content\":\"你好\"}\n\n"
```

`buffer` 保存每次读完后不完整的最后一行，拼接后下次继续处理，保证 JSON 解析不失败。

---

## 4. SSE 事件处理

```javascript
function handleSSEEvent(evt) {
    switch (evt.type) {
    case "token":
        appendAgentToken(evt.content);   // 往气泡追加文字
        break;
    case "tool_start":
        showToolStatus(evt.tool);        // 显示 "正在查询..."
        break;
    case "tool_end":
        hideToolStatus();                // 隐藏加载提示
        break;
    case "done":
        finalizeAgentBubble();           // 去掉光标，最终渲染
        sessionId = evt.session_id;      // 保存 session_id
        break;
    case "error":
        appendAgentToken("\n\n⚠️ " + evt.message);
        break;
    }
}
```

---

## 5. 打字机效果的实现

```javascript
function appendAgentToken(text) {
    if (!currentAgentBubble) createAgentBubble();
    currentAgentBubble.content += text;                              // 累积文本
    currentAgentBubble.bubble.innerHTML = marked.parse(content);     // 实时 Markdown → HTML
    scrollBottom();
}
```

`cursor-blink` CSS 类让气泡末尾有一个闪烁的光标：

```css
.cursor-blink::after {
    content: " ▌";
    animation: blink 1s step-end infinite;
}
```

`done` 事件到达后移除 `cursor-blink` 类，光标消失。

---

## 6. Markdown 渲染

使用 `marked.js` CDN。每次追加 token 后**全量重新渲染**——因为 Markdown 语法需要完整上下文：

```
"| 功能 | 免"     → marked 解析不完整表格
"| 功能 | 免费版 |" → marked 正常渲染表格
```

小文本量（< 2000 字符）下全量重渲染性能无影响。

---

## 7. Session 管理

```javascript
let sessionId = null;    // 新会话为 null

// 发送时：如果有 sessionId 就带上
body: JSON.stringify({ message, session_id: sessionId })

// 收到 done 事件时：保存服务器返回的 sessionId
if (!sessionId) sessionId = evt.session_id;

// 新对话按钮：清空 sessionId + 重置界面
btnNewChat.onclick = () => location.reload();
```

---

## 8. 前端检查清单

- [x] `http://localhost:8000` 可访问聊天界面
- [x] 欢迎界面 + 建议问题可点击
- [x] 输入框 Enter 发送 / Shift+Enter 换行
- [x] SSE 流式打字机效果
- [x] 工具调用时显示 spinner + 状态文字
- [x] Markdown 正确渲染（表格、列表、粗体）
- [x] 新对话按钮重置会话
- [x] 响应式（移动端可用）
