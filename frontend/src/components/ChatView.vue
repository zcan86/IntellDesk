<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Fold, Promotion, Picture, Microphone, StarFilled } from '@element-plus/icons-vue'
import ChatMessage from './ChatMessage.vue'
import WelcomeScreen from './WelcomeScreen.vue'
import { useChat } from '../composables/useChat'
import { ElMessage } from 'element-plus'

const props = defineProps<{ sessionId: string | null; sidebarCollapsed: boolean }>()
const emit = defineEmits<{ toggleSidebar: []; sessionCreated: [id: string] }>()

const { messages, isStreaming, sessionId, sendMessage, sendMultimodal, clearMessages } = useChat()
const inputText = ref('')
const msgContainer = ref<HTMLElement>()
const fileInput = ref<HTMLInputElement>()
const rating = ref(0)
const ratingComment = ref('')
const ratingSubmitted = ref(false)

watch(() => props.sessionId, (val) => { if (val === null) { clearMessages(); rating.value = 0; ratingComment.value = ''; ratingSubmitted.value = false } })
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
      <el-button :icon="Fold" text @click="emit('toggleSidebar')" />
      <h1>IntelliDesk 智能客服</h1>
      <span class="status" :class="{ streaming: isStreaming }">{{ isStreaming ? '...' : 'ready' }}</span>
    </header>

    <div class="messages" ref="msgContainer">
      <WelcomeScreen v-if="!messages.length" @suggestion="(m: string) => { inputText = m; doSend() }" />
      <ChatMessage v-for="(msg, i) in messages" :key="i" :message="msg" :is-last="i === messages.length - 1" :is-streaming="isStreaming && i === messages.length - 1" />
    </div>

    <!-- 评价栏（有对话 + 非流式时显示） -->
    <div v-if="messages.length > 0 && !isStreaming" class="rating-bar">
      <template v-if="!ratingSubmitted">
        <span class="rating-label">服务评价：</span>
        <span v-for="s in 5" :key="s" class="star" :class="{ active: s <= rating }" @click="rating = s">
          <el-icon :size="20"><StarFilled /></el-icon>
        </span>
        <el-input v-if="rating > 0" v-model="ratingComment" size="small" placeholder="补充评价(可选)" style="width:200px;margin-left:8px" />
        <el-button v-if="rating > 0" size="small" type="success" @click="submitFeedback" style="margin-left:8px">提交</el-button>
      </template>
      <span v-else class="rating-thanks">感谢你的评价！⭐</span>
    </div>

    <div class="input-area">
      <input ref="fileInput" type="file" accept="image/*,audio/*" style="display:none" @change="onFileChange" />
      <el-button :icon="Picture" :disabled="isStreaming" circle @click="triggerUpload" title="上传图片" />
      <el-button :icon="Microphone" :disabled="true" circle title="语音(开发中)" />
      <el-input v-model="inputText" type="textarea" :rows="1" placeholder="输入文字，或上传图片/语音..." :disabled="isStreaming" @keydown="onKeydown" resize="none" />
      <el-button type="success" :icon="Promotion" :disabled="isStreaming || (!inputText.trim())" @click="doSend" circle />
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
.rating-bar { max-width: 800px; margin: 0 auto; width: 100%; padding: 8px 20px; display: flex; align-items: center; gap: 4px; font-size: 13px; color: #6e6e80; }
.star { cursor: pointer; color: #ddd; transition: color 0.15s; }
.star.active { color: #f5a623; }
.star:hover { color: #f5a623; }
.rating-label { margin-right: 4px; }
.rating-thanks { color: #10a37f; font-weight: 500; }
</style>
