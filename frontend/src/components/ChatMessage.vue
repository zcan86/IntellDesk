<script setup lang="ts">
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
    <div class="message" :class="[message.role, { clickable: message.role === 'system' }]">
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
</style>