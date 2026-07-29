<script setup lang="ts">
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
</style>