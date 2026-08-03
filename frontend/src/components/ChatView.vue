<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Fold, Expand, Picture, Microphone, StarFilled, List } from '@element-plus/icons-vue'
import SwooshMark from './SwooshMark.vue'
import ChatMessage from './ChatMessage.vue'
import WelcomeScreen from './WelcomeScreen.vue'
import { useChat } from '../composables/useChat'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps<{ sessionId: string | null; resetKey: number; sidebarCollapsed: boolean }>()
const emit = defineEmits<{ toggleSidebar: []; sessionCreated: [id: string, title: string] }>()

const { messages, isStreaming, sessionId, sendMessage, sendMultimodal, clearMessages } = useChat()
const inputText = ref('')
const sessionTitle = ref('')
const msgContainer = ref<HTMLElement>()
const fileInput = ref<HTMLInputElement>()
const rating = ref(0)
const ratingComment = ref('')
const ratingSubmitted = ref(false)
const ordersPanel = ref(false)
const ordersData = ref<any[]>([])

async function loadOrders() {
  ordersPanel.value = !ordersPanel.value
  if (!ordersPanel.value) return
  const { value: uid } = await ElMessageBox.prompt('请输入用户ID', '查询订单', {
    confirmButtonText: '查询', cancelButtonText: '取消',
    inputPattern: /^u00[1-3]$/, inputErrorMessage: 'u001/u002/u003',
  }).catch(() => ({ value: '' }))
  if (!uid) { ordersPanel.value = false; return }
  try {
    const base = import.meta.env.VITE_API_BASE || ''
    const key = import.meta.env.VITE_API_KEY || 'sk-intellidesk-demo'
    const resp = await fetch(`${base}/api/orders/${uid}`, { headers: { 'X-API-Key': key } })
    const data = await resp.json()
    ordersData.value = data.orders || []
  } catch { ordersData.value = [] }
}
function sendOrderMsg(oid: string) {
  inputText.value = `帮我查一下订单 ${oid}`
  doSend()
  ordersPanel.value = false
}

// 「新对话」/删除当前会话 → App 递增 resetKey，这里强制清空
// 用计数而非 sessionId 值变化判断，避免 sessionId 原本就是 null 时不触发
watch(() => props.resetKey, () => {
  clearMessages()
  rating.value = 0
  ratingComment.value = ''
  ratingSubmitted.value = false
})
watch(() => messages.value.length, async () => {
  await nextTick()
  msgContainer.value?.scrollTo({ top: msgContainer.value.scrollHeight, behavior: 'smooth' })
})
// 会话创建后同步给 App（侧栏高亮 + 历史保存 + 「新对话」清空消息依赖此状态）
watch(sessionId, (val) => { if (val) emit('sessionCreated', val, sessionTitle.value) })

function doSend() {
  const text = inputText.value.trim()
  if (!text || isStreaming.value) return
  // 新会话的首条消息作为历史标题
  if (!sessionId.value && !messages.value.length) {
    sessionTitle.value = text.slice(0, 30)
  }
  inputText.value = ''
  sendMessage(text)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend() }
}

function triggerUpload() { fileInput.value?.click() }

async function submitFeedback() {
  if (rating.value === 0 || !sessionId.value) return
  try {
    await fetch(`${import.meta.env.VITE_API_BASE || ''}/api/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': import.meta.env.VITE_API_KEY || 'sk-intellidesk-demo' },
      body: JSON.stringify({ session_id: sessionId.value, rating: rating.value, comment: ratingComment.value }),
    })
    ratingSubmitted.value = true
    ElMessage.success('感谢你的评价！')
  } catch { ElMessage.error('提交失败') }
}

async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const ext = file.name.split('.').pop()?.toLowerCase()
  const imgExts = ['jpg','jpeg','png','gif','webp']
  const audioExts = ['mp3','wav','m4a','ogg','webm']

  if (![...imgExts, ...audioExts].includes(ext || '')) {
    ElMessage.warning('仅支持图片(JPG/PNG/GIF)和音频(MP3/WAV)')
    return
  }
  ElMessage.info(`${imgExts.includes(ext||'') ? '图片' : '音频'}识别中...`)
  await sendMultimodal(file, inputText.value)
  inputText.value = ''
  if (fileInput.value) fileInput.value.value = ''
}
</script>

<template>
  <div class="chat-view">
    <header class="topbar">
      <button class="icon-btn" @click="emit('toggleSidebar')" :aria-label="sidebarCollapsed ? '展开侧栏' : '收起侧栏'">
        <el-icon><Expand v-if="sidebarCollapsed" /><Fold v-else /></el-icon>
      </button>
      <div class="brand-line">
        <span class="brand-dot" :class="{ streaming: isStreaming }" />
        <span class="brand-name">小速</span>
        <span class="brand-sub">{{ isStreaming ? '正在思考…' : '在线 · 有问必答' }}</span>
      </div>
    </header>

    <div class="messages" ref="msgContainer">
      <div class="messages-inner">
        <WelcomeScreen v-if="!messages.length" @suggestion="(m: string) => { inputText = m; doSend() }" />
        <ChatMessage
          v-for="(msg, i) in messages"
          :key="i"
          :message="msg"
          :is-last="i === messages.length - 1"
          :is-streaming="isStreaming && i === messages.length - 1"
        />
      </div>
    </div>

    <!-- 订单面板 -->
    <div class="orders-panel">
      <button class="orders-toggle" @click="loadOrders">
        <el-icon :size="14"><List /></el-icon> {{ ordersPanel ? '收起订单' : '我的订单' }}
      </button>
      <div v-if="ordersPanel && ordersData.length" class="orders-list">
        <div v-for="o in ordersData" :key="o.order_id" class="order-row" @click="sendOrderMsg(o.order_id)">
          <span class="order-id">{{ o.order_id }}</span>
          <span class="order-item">{{ o.product_name }}</span>
          <span class="order-status" :class="'st-' + o.status">{{ o.status }}</span>
          <span class="order-send">去问 <span class="send-arrow">→</span></span>
        </div>
      </div>
      <span v-if="ordersPanel && !ordersData.length" class="orders-empty">暂无订单</span>
    </div>

    <!-- 评价栏 -->
    <div v-if="messages.length > 0 && !isStreaming" class="rating-bar">
      <template v-if="!ratingSubmitted">
        <span class="rating-label">这次服务怎么样？</span>
        <span v-for="s in 5" :key="s" class="star" :class="{ active: s <= rating }" @click="rating = s">
          <el-icon :size="18"><StarFilled /></el-icon>
        </span>
        <input v-if="rating > 0" v-model="ratingComment" class="rating-comment" placeholder="补充一句（可选）" />
        <button v-if="rating > 0" class="rating-submit" @click="submitFeedback">提交</button>
      </template>
      <span v-else class="rating-thanks">已收到你的评价，谢谢 ⭐</span>
    </div>

    <!-- 输入条 -->
    <div class="composer">
      <input ref="fileInput" type="file" accept="image/*,audio/*" style="display:none" @change="onFileChange" />
      <div class="composer-box">
        <button class="composer-btn" :disabled="isStreaming" @click="triggerUpload" title="上传图片">
          <el-icon :size="17"><Picture /></el-icon>
        </button>
        <button class="composer-btn" disabled title="语音（开发中）">
          <el-icon :size="17"><Microphone /></el-icon>
        </button>
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="1"
          placeholder="问小速：查订单、退换货、选鞋…"
          :disabled="isStreaming"
          resize="none"
          class="composer-input"
          @keydown="onKeydown"
        />
        <button class="send-btn" :disabled="isStreaming || !inputText.trim()" @click="doSend" title="发送">
          <SwooshMark :size="15" :weight="3.4" />
        </button>
      </div>
      <p class="composer-hint">小速会调用工具实时查询 · 支持图片识别与语音</p>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex; flex-direction: column;
  height: 100vh;
  background: var(--canvas);
}

/* —— 顶栏 —— */
.topbar {
  height: 60px; flex-shrink: 0;
  display: flex; align-items: center; gap: 14px;
  padding: 0 20px;
  border-bottom: 1px solid var(--line);
  background: var(--canvas);
}
.icon-btn {
  width: 34px; height: 34px;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--line);
  border-radius: var(--r-s);
  background: var(--surface);
  color: var(--ink-soft);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.icon-btn:hover { border-color: var(--signal-line); color: var(--signal); }
.brand-line { display: flex; align-items: center; gap: 9px; }
.brand-name { font-weight: 700; font-size: 15px; letter-spacing: 0.2px; }
.brand-sub { font-size: 12.5px; color: var(--ink-mute); }
.brand-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--ok);
  box-shadow: 0 0 0 3px var(--ok-soft);
}
.brand-dot.streaming {
  background: var(--signal);
  box-shadow: 0 0 0 3px var(--signal-soft);
  animation: pulse 1.1s var(--ease) infinite;
}
@keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.4); } }

/* —— 消息区 —— */
.messages { flex: 1; overflow-y: auto; }
.messages-inner {
  max-width: 740px;
  margin: 0 auto;
  padding: 28px 24px 20px;
  display: flex; flex-direction: column; gap: 8px;
}

/* —— 订单面板 —— */
.orders-panel { max-width: 740px; margin: 0 auto; width: 100%; padding: 0 24px; font-size: 13px; }
.orders-toggle {
  display: inline-flex; align-items: center; gap: 5px;
  border: 1px solid var(--line);
  background: var(--surface);
  border-radius: var(--r-full);
  padding: 4px 12px;
  font: 13px var(--font-body);
  color: var(--ink-soft);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.orders-toggle:hover { border-color: var(--signal-line); color: var(--signal); }
.orders-list {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r-m);
  margin-top: 8px;
  padding: 6px;
  box-shadow: var(--shadow-card);
}
.order-row {
  display: flex; align-items: center; gap: 12px;
  padding: 9px 10px;
  cursor: pointer;
  border-radius: var(--r-s);
  transition: background 0.12s;
}
.order-row:hover { background: var(--signal-soft); }
.order-id { font-family: var(--font-mono); font-size: 12px; color: var(--ink-mute); min-width: 132px; }
.order-item { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.order-status { font-size: 11.5px; font-weight: 600; min-width: 58px; text-align: center; padding: 2px 8px; border-radius: var(--r-full); }
.st-已签收 { color: var(--ok); background: var(--ok-soft); }
.st-运输中 { color: #2f6fd0; background: rgba(47, 111, 208, 0.1); }
.st-待发货 { color: #c07a1d; background: rgba(192, 122, 29, 0.1); }
.st-待付款 { color: #c0402a; background: rgba(192, 64, 42, 0.1); }
.order-send { color: var(--signal); font-size: 12px; }
.send-arrow { display: inline-block; transition: transform 0.12s var(--ease); }
.order-row:hover .send-arrow { transform: translateX(3px); }
.orders-empty { color: var(--ink-faint); font-size: 12px; }

/* —— 评价栏 —— */
.rating-bar {
  max-width: 740px; margin: 0 auto; width: 100%;
  padding: 2px 24px 6px;
  display: flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: var(--ink-mute);
}
.star { color: var(--line-strong); cursor: pointer; transition: color 0.12s; }
.star.active, .star:hover { color: var(--signal); }
.rating-comment {
  flex: 0 0 180px;
  border: 1px solid var(--line);
  border-radius: var(--r-s);
  padding: 4px 9px;
  font: 12.5px var(--font-body);
  color: var(--ink);
  background: var(--surface);
}
.rating-submit {
  border: 1px solid var(--signal-line);
  background: var(--signal-soft);
  color: var(--signal-deep);
  border-radius: var(--r-full);
  padding: 3px 13px;
  font: 12.5px/1.6 var(--font-body);
  cursor: pointer;
}
.rating-submit:hover { background: var(--signal); color: #fff; }
.rating-thanks { color: var(--ok); }

/* —— 输入条 —— */
.composer { max-width: 740px; margin: 0 auto; width: 100%; padding: 0 24px 14px; flex-shrink: 0; }
.composer-box {
  display: flex; align-items: flex-end; gap: 6px;
  background: var(--surface);
  border: 1.5px solid var(--line-strong);
  border-radius: 16px;
  padding: 8px 10px;
  box-shadow: var(--shadow-card);
  transition: border-color 0.15s;
}
.composer-box:focus-within { border-color: var(--signal-line); }
.composer-btn {
  width: 38px; height: 38px; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border: none;
  background: transparent;
  color: var(--ink-mute);
  border-radius: 50%;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
}
.composer-btn:hover:not(:disabled) { color: var(--signal); background: var(--signal-soft); }
.composer-btn:disabled { cursor: not-allowed; opacity: 0.45; }
.composer-input { flex: 1; }
.composer-input :deep(.el-textarea__inner) {
  border: none; box-shadow: none; background: transparent;
  font: 14.5px/1.6 var(--font-body);
  color: var(--ink);
  padding: 7px 4px;
}
.send-btn {
  width: 38px; height: 38px; flex-shrink: 0;
  border-radius: 50%;
  border: none;
  background: var(--signal);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}
.send-btn:not(:disabled):hover { background: var(--signal-deep); }
.send-btn:not(:disabled):active { transform: translateY(1px); }
.send-btn:disabled { background: var(--line-strong); cursor: not-allowed; }
.composer-hint { margin: 7px 2px 0; font-size: 11.5px; color: var(--ink-faint); text-align: center; }
</style>
