<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ChatView from './components/ChatView.vue'

const sessionId = ref<string | null>(null)
const sidebarCollapsed = ref(false)

function onSelectSession(id: string | null) {
  sessionId.value = id
}
</script>

<template>
  <div class="app">
    <Sidebar
      :session-id="sessionId"
      :collapsed="sidebarCollapsed"
      @select-session="onSelectSession"
    />
    <main class="main">
      <ChatView
        :session-id="sessionId"
        :sidebar-collapsed="sidebarCollapsed"
        @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
        @session-created="onSelectSession"
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
