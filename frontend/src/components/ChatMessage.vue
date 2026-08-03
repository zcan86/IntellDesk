<script setup lang="ts">
import { computed } from 'vue'
import SwooshMark from './SwooshMark.vue'
import { useChat } from '../composables/useChat'
import type { ChatMessage as Msg } from '../composables/useChat'

const props = defineProps<{ message: Msg; isLast: boolean; isStreaming: boolean }>()
const { renderMarkdown } = useChat()
const htmlContent = computed(() => renderMarkdown(props.message.content))
</script>

<template>
  <div class="msg-row" :class="message.role">
    <div class="avatar" :class="message.role" aria-hidden="true">
      <SwooshMark v-if="message.role === 'agent'" :size="15" :weight="3.4" />
      <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
        <path d="M5 20a7 7 0 0 1 14 0" />
      </svg>
    </div>
    <div class="content">
      <div v-if="message.role === 'agent' && message.toolStatus" class="tool-status">
        <span class="tool-sweep" /><span>{{ message.toolStatus }}</span>
      </div>
      <div
        class="bubble md"
        :class="{ 'cursor-blink': isLast && isStreaming && !message.content }"
        v-html="htmlContent"
      />
    </div>
  </div>
</template>

<style scoped>
.msg-row { display: flex; gap: 12px; align-items: flex-start; }
.msg-row.user { flex-direction: row-reverse; }

.avatar {
  width: 34px; height: 34px;
  border-radius: 11px;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  margin-top: 4px;
}
.avatar.agent {
  background: var(--signal);
  color: #fff;
  box-shadow: 0 8px 20px -10px var(--signal);
}
.avatar.user { background: var(--ink); color: var(--canvas); }

.content { max-width: 86%; display: flex; flex-direction: column; gap: 5px; }
.bubble {
  padding: 10px 14px;
  border-radius: var(--r-m);
  font-size: 14.5px;
  line-height: 1.72;
}
.msg-row.agent .bubble {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink);
  box-shadow: var(--shadow-card);
  border-top-left-radius: 5px;
}
.msg-row.user .bubble {
  background: var(--ink);
  color: var(--canvas);
  border-top-right-radius: 5px;
}

/* 流式输入光标 */
.cursor-blink::after { content: ' ▍'; color: var(--signal); animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* 工具调用状态行：橙色勾扫过 */
.tool-status {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--ink-mute);
  padding-left: 2px;
}
.tool-sweep {
  width: 22px; height: 10px;
  position: relative; overflow: hidden;
  border-radius: 99px;
  background: var(--signal-soft);
}
.tool-sweep::after {
  content: '';
  position: absolute; top: 0; left: -40%; width: 40%; height: 100%;
  border-radius: 99px;
  background: var(--signal);
  animation: sweep 1.2s ease-in-out infinite;
}
@keyframes sweep {
  0% { left: -40%; }
  60%, 100% { left: 100%; }
}
</style>
