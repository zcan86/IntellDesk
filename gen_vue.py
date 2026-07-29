#!/usr/bin/env python
"""Generate all Vue 3 frontend files"""

import os

BASE = r"D:/IntellDesk/frontend/src"

# ═══ useChat.ts ═══
with open(f"{BASE}/composables/useChat.ts", "w", encoding="utf-8") as f:
    f.write("""import { ref } from 'vue'
import { marked } from 'marked'
marked.setOptions({ breaks: true, gfm: true })

export interface ChatMessage { role: 'user' | 'agent'; content: string; toolStatus?: string }

export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const sessionId = ref<string | null>(null)

  function addUserMessage(text: string) { messages.value.push({ role: 'user', content: text }) }
  function addAgentPlaceholder() { messages.value.push({ role: 'agent', content: '', toolStatus: '' }) }
  function appendToken(text: string) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'agent') last.content += text
  }
  function finalizeAgent() {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'agent') last.toolStatus = undefined
  }
  function showTool(tool: string) {
    const label: Record<string, string> = {
      search_knowledge_base: '查询知识库...', get_weather: '查询天气...',
      calculator: '计算中...', query_order: '查询订单...',
      track_delivery: '查询物流...', return_guide: '退换货指引...',
      product_search: '搜索商品...',
    }
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'agent') last.toolStatus = label[tool] || tool
  }
  function hideTool() {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'agent') last.toolStatus = ''
  }

  async function sendMessage(text: string) {
    if (isStreaming.value) return
    isStreaming.value = true; addUserMessage(text); addAgentPlaceholder()
    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId.value }),
      })
      if (!resp.ok) throw new Error((await resp.json()).detail || 'Error')
      const reader = resp.body!.getReader(); const decoder = new TextDecoder(); let buf = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buf += decoder.decode(value, { stream: true }); const lines = buf.split('\\n'); buf = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            if (evt.type === 'token') appendToken(evt.content)
            else if (evt.type === 'tool_start') showTool(evt.tool)
            else if (evt.type === 'tool_end') hideTool()
            else if (evt.type === 'done') { finalizeAgent(); if (evt.session_id && !sessionId.value) sessionId.value = evt.session_id }
          } catch { /* skip */ }
        }
      }
    } catch (err: any) { appendToken('\\n\\n' + err.message); finalizeAgent() }
    finally { isStreaming.value = false }
  }

  function clearMessages() { messages.value = []; sessionId.value = null }
  function renderMarkdown(text: string) { return marked.parse(text) }
  return { messages, isStreaming, sessionId, sendMessage, clearMessages, renderMarkdown }
}
""")
print("useChat.ts done")

# ═══ WelcomeScreen.vue ═══
with open(f"{BASE}/components/WelcomeScreen.vue", "w", encoding="utf-8") as f:
    f.write("""<script setup lang="ts">
const emit = defineEmits<{ suggestion: [msg: string] }>()
const suggestions = [
  '帮我查一下订单 DD20240001',
  '退货流程是怎样的？',
  '有没有蓝牙耳机推荐？',
  '满多少包邮？',
]
</script>

<template>
  <div class="welcome">
    <div class="icon">shopping_cart</div>
    <h2>你好！我是小速</h2>
    <p>速购电商智能客服。你可以问我：</p>
    <div class="suggestions">
      <el-button v-for="s in suggestions" :key="s" class="suggestion" round @click="emit('suggestion', s)">{{ s }}</el-button>
    </div>
  </div>
</template>

<style scoped>
.welcome { text-align: center; padding: 60px 20px 30px; }
.icon { font-size: 56px; margin-bottom: 12px; }
h2 { font-size: 22px; margin-bottom: 8px; }
p { color: #6e6e80; font-size: 14px; margin-bottom: 20px; }
.suggestions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; max-width: 520px; margin: 0 auto; }
</style>""")
print("WelcomeScreen.vue done")

# ═══ ChatView.vue ═══
with open(f"{BASE}/components/ChatView.vue", "w", encoding="utf-8") as f:
    f.write("""<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Fold, Promotion } from '@element-plus/icons-vue'
import ChatMessage from './ChatMessage.vue'
import WelcomeScreen from './WelcomeScreen.vue'
import { useChat } from '../composables/useChat'

const props = defineProps<{ sessionId: string | null; sidebarCollapsed: boolean }>()
const emit = defineEmits<{ toggleSidebar: []; sessionCreated: [id: string] }>()

const { messages, isStreaming, sendMessage, clearMessages } = useChat()
const inputText = ref('')
const msgContainer = ref<HTMLElement>()

watch(() => props.sessionId, (val) => { if (val === null) clearMessages() })
watch(() => messages.value.length, async () => {
  await nextTick()
  msgContainer.value?.scrollTo({ top: msgContainer.value.scrollHeight, behavior: 'smooth' })
})

function doSend() {
  const text = inputText.value.trim()
  if (!text || isStreaming.value) return
  inputText.value = ''
  sendMessage(text)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend() }
}
</script>

<template>
  <div class="chat-view">
    <header class="topbar">
      <el-button :icon="Fold" text @click="emit('toggleSidebar')" />
      <h1>速购电商 智能客服</h1>
      <span class="status" :class="{ streaming: isStreaming }">{{ isStreaming ? 'thinking...' : 'ready' }}</span>
    </header>
    <div class="messages" ref="msgContainer">
      <WelcomeScreen v-if="!messages.length" @suggestion="(m: string) => { inputText = m; doSend() }" />
      <ChatMessage v-for="(msg, i) in messages" :key="i" :message="msg" :is-last="i === messages.length - 1" :is-streaming="isStreaming && i === messages.length - 1" />
    </div>
    <div class="input-area">
      <el-input v-model="inputText" type="textarea" :rows="1" placeholder="Enter..." :disabled="isStreaming" @keydown="onKeydown" resize="none" />
      <el-button type="success" :icon="Promotion" :disabled="isStreaming || !inputText.trim()" @click="doSend" circle />
    </div>
  </div>
</template>

<style scoped>
.chat-view { display: flex; flex-direction: column; height: 100vh; }
.topbar { height: 52px; display: flex; align-items: center; gap: 12px; padding: 0 20px; border-bottom: 1px solid #e5e5e8; background: #fff; flex-shrink: 0; }
.topbar h1 { font-size: 16px; font-weight: 600; flex: 1; }
.status { font-size: 12px; color: #6e6e80; }
.status.streaming { color: #10a37f; }
.messages { flex: 1; overflow-y: auto; padding: 20px 0; }
.input-area { max-width: 800px; margin: 0 auto; width: 100%; padding: 12px 20px 16px; display: flex; gap: 8px; align-items: flex-end; flex-shrink: 0; }
</style>""")
print("ChatView.vue done")

with open(f"{BASE}/components/ChatMessage.vue", "w", encoding="utf-8") as f:
    f.write("""<script setup lang="ts">
import { computed } from 'vue'
import { useChat } from '../composables/useChat'
import type { ChatMessage as Msg } from '../composables/useChat'

const props = defineProps<{ message: Msg; isLast: boolean; isStreaming: boolean }>()
const { renderMarkdown } = useChat()
const htmlContent = computed(() => renderMarkdown(props.message.content))
</script>

<template>
  <div class="msg-wrapper">
    <div v-if="message.role === 'agent' && message.toolStatus" class="tool-status">
      <span class="spinner" /> {{ message.toolStatus }}
    </div>
    <div class="message" :class="message.role">
      <div class="avatar">{{ message.role === 'user' ? 'U' : 'AI' }}</div>
      <div class="bubble" v-html="htmlContent" :class="{ 'cursor-blink': isLast && isStreaming && !message.content }" />
    </div>
  </div>
</template>

<style scoped>
.msg-wrapper { max-width: 800px; margin: 0 auto; padding: 0 20px; }
.tool-status { font-size: 12px; color: #6e6e80; padding: 0 0 8px 56px; display: flex; align-items: center; gap: 6px; }
.spinner { width: 14px; height: 14px; border: 2px solid #ddd; border-top-color: #10a37f; border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.message { display: flex; gap: 12px; padding: 12px 0; align-items: flex-start; }
.message.user { flex-direction: row-reverse; }
.avatar { width: 32px; height: 32px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; font-weight: 700; }
.message.agent .avatar { background: #10a37f; color: #fff; }
.message.user .avatar { background: #5436da; color: #fff; }
.bubble { padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.65; max-width: 85%; word-break: break-word; }
.message.agent .bubble { background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.message.user .bubble { background: #10a37f; color: #fff; }
.cursor-blink::after { content: ' |'; animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>""")
print("ChatMessage.vue done")

print("All Vue files generated!")
