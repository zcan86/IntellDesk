/* ═══════════════════════════════════════════════════════════
   IntelliDesk Chat UI — JavaScript
   ═══════════════════════════════════════════════════════════ */

(function () {
    "use strict";

    // ── DOM 引用 ────────────────────────────────────────────
    const messagesEl   = document.getElementById("messages");
    const inputEl      = document.getElementById("input");
    const btnSend      = document.getElementById("btnSend");
    const btnNewChat   = document.getElementById("btnNewChat");
    const btnToggle    = document.getElementById("btnToggleSidebar");
    const sidebarEl    = document.getElementById("sidebar");
    const statusEl     = document.getElementById("statusIndicator");
    const historyEl    = document.getElementById("historyList");
    const welcomeEl    = document.getElementById("welcome");

    let sessionId       = null;
    let isStreaming     = false;
    let currentAgentBubble = null;

    // ── localStorage key ────────────────────────────────────
    const STORAGE_KEY = "intellidesk_sessions";  // { id, title, time, messages }

    // ── 初始化 ──────────────────────────────────────────────
    marked.setOptions({ breaks: true, gfm: true });

    /** 自动调整输入框高度 */
    function autoResize() {
        inputEl.style.height = "auto";
        inputEl.style.height = Math.min(inputEl.scrollHeight, 150) + "px";
    }

    function scrollBottom() {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function setStatus(text, streaming) {
        statusEl.textContent = text;
        statusEl.className = "topbar-status" + (streaming ? " streaming" : "");
    }

    // ── 会话持久化 ──────────────────────────────────────────

    function loadSessions() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
        } catch (_) { return []; }
    }

    function saveSessions(list) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    }

    /** 更新或新增一条会话记录 */
    function upsertSession(id, title) {
        const list = loadSessions().filter(s => s.id !== id);
        list.unshift({
            id: id,
            title: title || "新对话",
            time: Date.now(),
            messages: getCurrentMessages(),  // 保存当前消息 HTML
        });
        saveSessions(list);
        renderHistory();
    }

    /** 获取当前消息区的 HTML（用于存储） */
    function getCurrentMessages() {
        return messagesEl.innerHTML;
    }

    /** 删除会话 */
    function deleteSession(id) {
        let list = loadSessions().filter(s => s.id !== id);
        saveSessions(list);
        if (sessionId === id) {
            startNewChat();
        }
        renderHistory();
    }

    // ── 历史列表渲染 ────────────────────────────────────────

    function renderHistory() {
        const list = loadSessions();
        historyEl.innerHTML = list.map(s => {
            const active = s.id === sessionId ? " active" : "";
            const timeStr = formatTime(s.time);
            return `
                <div class="history-item${active}" data-id="${s.id}">
                    <div class="title" title="${escapeAttr(s.title)}">${escapeHtml(s.title)}</div>
                    <div class="time">${timeStr}</div>
                    <button class="btn-delete" data-action="delete" data-id="${s.id}">&times;</button>
                </div>`;
        }).join("");
    }

    function formatTime(ts) {
        const d = new Date(ts);
        const now = new Date();
        const diff = now - d;
        if (diff < 60_000) return "刚刚";
        if (diff < 3600_000) return Math.floor(diff / 60_000) + " 分钟前";
        if (d.toDateString() === now.toDateString()) {
            return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
        }
        return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
    }

    /** 点击历史列表 */
    historyEl.addEventListener("click", (e) => {
        // 删除按钮
        const delBtn = e.target.closest("[data-action='delete']");
        if (delBtn) {
            e.stopPropagation();
            deleteSession(delBtn.dataset.id);
            return;
        }
        // 切换会话
        const item = e.target.closest(".history-item");
        if (!item) return;
        const id = item.dataset.id;
        if (id === sessionId) return;

        // 保存当前会话
        if (sessionId) upsertSession(sessionId, getSessionTitle());

        // 加载目标会话
        const list = loadSessions();
        const target = list.find(s => s.id === id);
        if (target) {
            sessionId = id;
            currentAgentBubble = null;
            messagesEl.innerHTML = target.messages || "";
            hideWelcomeIfHasMessages();
            scrollBottom();
            renderHistory();
        }
    });

    function getSessionTitle() {
        const bubbles = messagesEl.querySelectorAll(".message.user .bubble");
        if (bubbles.length === 0) return "新对话";
        const text = bubbles[0].textContent.trim();
        return text.length > 30 ? text.slice(0, 30) + "..." : text;
    }

    function hideWelcomeIfHasMessages() {
        const hasMsgs = messagesEl.querySelector(".chat-group");
        if (hasMsgs && welcomeEl) welcomeEl.style.display = "none";
    }

    function startNewChat() {
        if (sessionId) upsertSession(sessionId, getSessionTitle());
        sessionId = null;
        currentAgentBubble = null;
        messagesEl.innerHTML = welcomeHTML();
        renderHistory();
    }

    // ── 消息渲染 ────────────────────────────────────────────

    function addUserMessage(text) {
        hideWelcome();
        const group = document.createElement("div");
        group.className = "chat-group";
        group.innerHTML = `
            <div class="message user">
                <div class="avatar">👤</div>
                <div class="bubble">${escapeHtml(text)}</div>
            </div>`;
        messagesEl.appendChild(group);
        scrollBottom();
    }

    function createAgentBubble() {
        hideWelcome();
        const group = document.createElement("div");
        group.className = "chat-group";

        const toolStatus = document.createElement("div");
        toolStatus.className = "tool-status";
        toolStatus.style.display = "none";
        toolStatus.innerHTML = `<span class="spinner"></span><span class="tool-label"></span>`;
        group.appendChild(toolStatus);

        const msgDiv = document.createElement("div");
        msgDiv.className = "message agent";
        msgDiv.innerHTML = `
            <div class="avatar">🤖</div>
            <div class="bubble cursor-blink"></div>`;
        group.appendChild(msgDiv);

        messagesEl.appendChild(group);
        currentAgentBubble = {
            group: group,
            bubble: msgDiv.querySelector(".bubble"),
            toolStatus: toolStatus,
            content: "",
        };
        scrollBottom();
    }

    function appendAgentToken(text) {
        if (!currentAgentBubble) createAgentBubble();
        currentAgentBubble.content += text;
        currentAgentBubble.bubble.innerHTML = marked.parse(currentAgentBubble.content);
        scrollBottom();
    }

    function finalizeAgentBubble() {
        if (!currentAgentBubble) return;
        currentAgentBubble.bubble.classList.remove("cursor-blink");
        currentAgentBubble.toolStatus.style.display = "none";
        currentAgentBubble.bubble.innerHTML = marked.parse(currentAgentBubble.content);
        currentAgentBubble = null;
        scrollBottom();
    }

    function showToolStatus(toolName) {
        if (!currentAgentBubble) createAgentBubble();
        const ts = currentAgentBubble.toolStatus;
        ts.style.display = "flex";
        ts.querySelector(".tool-label").textContent = toolLabel(toolName);
    }

    function hideToolStatus() {
        if (currentAgentBubble) {
            currentAgentBubble.toolStatus.style.display = "none";
        }
    }

    function toolLabel(name) {
        const map = {
            search_knowledge_base: "正在查询知识库...",
            get_weather: "正在查询天气...",
            calculator: "正在计算...",
            get_current_time: "正在获取时间...",
        };
        return map[name] || `正在调用 ${name}...`;
    }

    function hideWelcome() {
        if (welcomeEl) welcomeEl.style.display = "none";
    }

    // ── SSE 流式请求 ─────────────────────────────────────────

    async function sendMessage(message) {
        if (isStreaming) return;
        isStreaming = true;
        btnSend.disabled = true;
        inputEl.disabled = true;
        setStatus("● 思考中...", true);

        addUserMessage(message);
        createAgentBubble();

        try {
            const resp = await fetch("/api/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message, session_id: sessionId }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";
                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    try { handleSSEEvent(JSON.parse(line.slice(6))); }
                    catch (_) { /* ignore */ }
                }
            }
        } catch (err) {
            appendAgentToken(`\n\n❌ 请求失败：${escapeHtml(err.message)}`);
            finalizeAgentBubble();
            console.error(err);
        } finally {
            isStreaming = false;
            btnSend.disabled = false;
            inputEl.disabled = false;
            inputEl.focus();
            setStatus("● 就绪", false);
        }
    }

    function handleSSEEvent(evt) {
        switch (evt.type) {
        case "token":
            appendAgentToken(evt.content);
            break;
        case "tool_start":
            showToolStatus(evt.tool);
            break;
        case "tool_end":
            hideToolStatus();
            break;
        case "done":
            finalizeAgentBubble();
            if (evt.session_id && !sessionId) {
                sessionId = evt.session_id;
                // 保存到历史列表
                setTimeout(() => {
                    upsertSession(sessionId, getSessionTitle());
                }, 100);
            }
            break;
        case "error":
            appendAgentToken(`\n\n⚠️ ${escapeHtml(evt.message)}`);
            finalizeAgentBubble();
            break;
        }
    }

    // ── 事件绑定 ────────────────────────────────────────────

    function doSend() {
        const text = inputEl.value.trim();
        if (!text || isStreaming) return;
        inputEl.value = "";
        autoResize();
        sendMessage(text);
    }

    btnSend.addEventListener("click", doSend);
    inputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            doSend();
        }
    });
    inputEl.addEventListener("input", autoResize);

    btnNewChat.addEventListener("click", startNewChat);

    document.addEventListener("click", (e) => {
        const sug = e.target.closest(".suggestion");
        if (!sug || !sug.dataset.msg) return;
        inputEl.value = sug.dataset.msg;
        doSend();
    });

    btnToggle.addEventListener("click", () => {
        sidebarEl.classList.toggle("collapsed");
    });

    // ── 工具函数 ────────────────────────────────────────────

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function escapeAttr(str) {
        return str.replace(/"/g, "&quot;").replace(/</g, "&lt;");
    }

    function welcomeHTML() {
        return `
            <div class="welcome" id="welcome">
                <div class="welcome-icon">🤖</div>
                <h2>你好！我是小智</h2>
                <p>IntelliDesk 官方智能客服助手。你可以问我：</p>
                <div class="suggestions">
                    <button class="suggestion" data-msg="免费版能用 API 吗？">免费版能用 API 吗？</button>
                    <button class="suggestion" data-msg="Pro 版和免费版有什么区别？">Pro 版和免费版有什么区别？</button>
                    <button class="suggestion" data-msg="如何上传文档？">如何上传文档？</button>
                    <button class="suggestion" data-msg="北京今天天气怎么样？">北京今天天气怎么样？</button>
                </div>
            </div>`;
    }

    // ── 启动 ────────────────────────────────────────────────
    renderHistory();

})();
