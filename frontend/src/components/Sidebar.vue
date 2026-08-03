<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import SwooshMark from './SwooshMark.vue'

interface Session { id: string; title: string; time: number }

const props = defineProps<{ sessionId: string | null; collapsed: boolean; sessions: Session[] }>()
const emit = defineEmits<{ selectSession: [id: string | null]; deleteSession: [id: string] }>()

function selectSession(s: Session) {
  emit('selectSession', s.id)
}

function newChat() {
  emit('selectSession', null)
}

function deleteSession(id: string, e: Event) {
  e.stopPropagation()
  emit('deleteSession', id)
}

function formatTime(ts: number) {
  const d = new Date(ts), now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="brand">
      <span class="brand-mark"><SwooshMark :size="17" :weight="3.4" /></span>
      <div class="brand-text">
        <strong>小速</strong>
        <span>耐克旗舰店 · 智能客服</span>
      </div>
    </div>

    <button class="new-chat" @click="newChat">
      <Plus :size="12" /><span class="new-chat-label">新对话</span>
    </button>

    <div class="history">
      <div class="history-head">历史对话</div>
      <div v-if="sessions.length" class="history-list">
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
      </div>
      <div v-else class="empty">还没有对话<br />点上方「新对话」开始</div>
    </div>

    <div class="foot">
      <span class="foot-dot" /> 在线 · v3.2.0
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 264px;
  background: var(--ink);
  color: #f2f2ee;
  display: flex;
  flex-direction: column;
  padding: 18px 14px 14px;
  flex-shrink: 0;
  transition: margin-left 0.25s var(--ease);
}
.sidebar.collapsed { margin-left: -264px; }

.brand { display: flex; align-items: center; gap: 11px; padding: 2px 4px 16px; }
.brand-mark {
  width: 38px; height: 38px;
  border-radius: 12px;
  background: var(--signal);
  color: #fff;
  display: inline-flex; align-items: center; justify-content: center;
  transform: rotate(-3deg);
}
.brand-text { display: flex; flex-direction: column; line-height: 1.35; }
.brand-text strong {
  font-family: var(--font-display);
  font-weight: 400;
  font-size: 19px;
  letter-spacing: 1px;
}
.brand-text span { font-size: 11px; color: rgba(242, 242, 238, 0.5); }

.new-chat {
  display: flex; align-items: center; justify-content: center; gap: 5px;
  width: 100%; padding: 3px 8px;
  border: 1px solid rgba(242, 242, 238, 0.16);
  border-radius: 6px;
  background: rgba(242, 242, 238, 0.06);
  color: #f2f2ee;
  font: 12px var(--font-body);
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.new-chat-label { line-height: 1; }
.new-chat:hover { background: rgba(242, 242, 238, 0.12); border-color: rgba(242, 242, 238, 0.28); }

.history { flex: 1; overflow-y: auto; margin-top: 16px; }
.history-head { font-size: 11px; color: rgba(242, 242, 238, 0.38); letter-spacing: 2px; padding: 0 6px 8px; }
.history-item {
  position: relative;
  padding: 9px 10px 9px 12px;
  border-radius: var(--r-s);
  cursor: pointer;
  font-size: 13px;
  margin-bottom: 2px;
  color: #d6d7d1;
  transition: background 0.13s;
}
.history-item:hover { background: rgba(242, 242, 238, 0.07); }
.history-item.active { background: rgba(239, 77, 33, 0.16); color: #fff; }
.history-item.active::before {
  content: '';
  position: absolute;
  left: 0; top: 50%;
  transform: translateY(-50%);
  width: 3px; height: 16px;
  border-radius: 3px;
  background: var(--signal);
}
.title { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 18px; }
.time { font-size: 10.5px; color: rgba(242, 242, 238, 0.35); }
.delete-btn {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  color: rgba(242, 242, 238, 0.35);
  opacity: 0; transition: opacity 0.13s;
  font-size: 15px; line-height: 1; cursor: pointer;
}
.history-item:hover .delete-btn { opacity: 1; }
.delete-btn:hover { color: #fff; }
.empty { text-align: center; color: rgba(242, 242, 238, 0.3); font-size: 12px; line-height: 1.7; padding: 22px 0; }

.foot { margin-top: auto; display: flex; align-items: center; justify-content: center; gap: 6px; font-size: 11px; color: rgba(242, 242, 238, 0.4); }
.foot-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); }
</style>
