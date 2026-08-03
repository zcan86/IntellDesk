<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatView from './components/ChatView.vue'

interface Session { id: string; title: string; time: number }
const STORAGE_KEY = 'intellidesk_sessions'

const sessionId = ref<string | null>(null)
const resetKey = ref(0)
const sidebarCollapsed = ref(false)
const sessions = ref<Session[]>([])

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value))
}
function loadSessions() {
  try { sessions.value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') }
  catch { sessions.value = [] }
}
loadSessions()

function clearActiveSession() {
  sessionId.value = null
  // 即使 sessionId 原本就是 null，也强制触发 ChatView 清空（修复 null→null 不触发 watch）
  resetKey.value++
}

function onSelectSession(id: string | null) {
  if (id === null) clearActiveSession()
  else sessionId.value = id
}

/** 新会话创建后写入历史（侧栏显示 + localStorage 持久化） */
function onSessionCreated(id: string, title: string) {
  if (sessions.value.some(s => s.id === id)) return
  sessions.value.unshift({ id, title: title || '新对话', time: Date.now() })
  persist()
}

function onDeleteSession(id: string) {
  sessions.value = sessions.value.filter(s => s.id !== id)
  persist()
  if (sessionId.value === id) clearActiveSession()
}
</script>

<template>
  <div class="app">
    <Sidebar
      :session-id="sessionId"
      :collapsed="sidebarCollapsed"
      :sessions="sessions"
      @select-session="onSelectSession"
      @delete-session="onDeleteSession"
    />
    <main class="main">
      <ChatView
        :session-id="sessionId"
        :reset-key="resetKey"
        :sidebar-collapsed="sidebarCollapsed"
        @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
        @session-created="onSessionCreated"
      />
    </main>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  height: 100vh;
  background: var(--canvas);
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>
