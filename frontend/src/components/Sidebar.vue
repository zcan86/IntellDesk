<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'

const props = defineProps<{ sessionId: string | null; collapsed: boolean }>()
const emit = defineEmits<{ selectSession: [id: string | null] }>()

interface Session { id: string; title: string; time: number }
const sessions = ref<Session[]>([])

function loadSessions() {
  try { sessions.value = JSON.parse(localStorage.getItem('intellidesk_sessions') || '[]') }
  catch { sessions.value = [] }
}

function selectSession(s: Session) {
  emit('selectSession', s.id)
}

function newChat() {
  emit('selectSession', null)
}

function deleteSession(id: string, e: Event) {
  e.stopPropagation()
  sessions.value = sessions.value.filter(s => s.id !== id)
  localStorage.setItem('intellidesk_sessions', JSON.stringify(sessions.value))
  if (props.sessionId === id) emit('selectSession', null)
}

function formatTime(ts: number) {
  const d = new Date(ts), now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

onMounted(loadSessions)
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="sidebar-header"><span class="logo">🛒 速购电商</span></div>
    <el-button :icon="Plus" class="new-chat-btn" @click="newChat">新对话</el-button>
    <div class="history-list">
      <div
        v-for="s in sessions" :key="s.id"
        class="history-item"
        :class="{ active: s.id === sessionId }"
        @click="selectSession(s)"
      >
        <span class="title">{{ s.title }}</span>
        <span class="time">{{ formatTime(s.time) }}</span>
        <span class="delete-btn" @click="deleteSession(s.id, $event)">×</span>
      </div>
      <div v-if="!sessions.length" class="empty-hint">暂无历史对话</div>
    </div>
    <div class="sidebar-footer">v3.1.0</div>
  </aside>
</template>

<style scoped>
.sidebar { width: 260px; background: #202123; display: flex; flex-direction: column; padding: 12px; flex-shrink: 0; transition: margin-left 0.25s; }
.sidebar.collapsed { margin-left: -260px; }
.sidebar-header { padding: 8px 0 16px; }
.logo { font-size: 18px; font-weight: 700; color: #ececf1; }
.new-chat-btn { width: 100%; margin-bottom: 12px; }
.history-list { flex: 1; overflow-y: auto; }
.history-item { padding: 10px 12px; border-radius: 8px; cursor: pointer; color: #ececf1; font-size: 13px; margin-bottom: 4px; position: relative; }
.history-item:hover { background: rgba(255,255,255,0.1); }
.history-item.active { background: rgba(255,255,255,0.15); }
.title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; padding-right: 20px; }
.time { font-size: 11px; color: rgba(255,255,255,0.35); }
.delete-btn { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); color: rgba(255,255,255,0.3); opacity: 0; transition: opacity 0.15s; }
.history-item:hover .delete-btn { opacity: 1; }
.empty-hint { text-align: center; color: rgba(255,255,255,0.25); font-size: 12px; padding: 20px 0; }
.sidebar-footer { margin-top: auto; text-align: center; font-size: 11px; color: rgba(255,255,255,0.3); }
</style>
