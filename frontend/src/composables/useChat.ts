import { ref } from 'vue'
import { marked } from 'marked'
marked.setOptions({ breaks: true, gfm: true })

export interface ChatMessage { role: 'user' | 'agent' | 'system'; content: string; toolStatus?: string; agentName?: string }

export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const sessionId = ref<string | null>(null)
  const currentAgent = ref('')

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
    isStreaming.value = true
    addUserMessage(text)
    addAgentPlaceholder()
    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId.value }),
      })
      if (!resp.ok) throw new Error((await resp.json()).detail || 'Error')
      const reader = resp.body!.getReader(); const decoder = new TextDecoder(); let buf = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buf += decoder.decode(value, { stream: true }); const lines = buf.split('\n'); buf = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            if (evt.type === 'agent_start') { const last = messages.value[messages.value.length - 1]; if (last && last.role === 'agent') last.toolStatus = evt.agent; currentAgent.value = evt.agent }
            else if (evt.type === 'agent_end') { if (currentAgent.value) { const last = messages.value[messages.value.length - 1]; if (last && last.role === 'agent') last.toolStatus = ''; } currentAgent.value = '' }
            else if (evt.type === 'token') appendToken(evt.content)
            else if (evt.type === 'tool_start') showTool(evt.tool)
            else if (evt.type === 'tool_end') hideTool()
            else if (evt.type === 'done') { finalizeAgent(); if (evt.session_id && !sessionId.value) sessionId.value = evt.session_id }
          } catch { /* skip */ }
        }
      }
    } catch (err: any) { appendToken('\n\n' + err.message); finalizeAgent() }
    finally { isStreaming.value = false }
  }

  async function sendMultimodal(file: File, text: string) {
    if (isStreaming.value) return
    isStreaming.value = true
    const form = new FormData()
    form.append('file', file)
    form.append('message', text || '')
    if (sessionId.value) form.append('session_id', sessionId.value)

    addUserMessage(text || `[上传了 ${file.name}]`)
    addAgentPlaceholder()

    try {
      const resp = await fetch('/api/chat/upload', { method: 'POST', body: form })
      if (!resp.ok) throw new Error((await resp.json()).detail || 'Error')
      const reader = resp.body!.getReader(); const decoder = new TextDecoder(); let buf = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buf += decoder.decode(value, { stream: true }); const lines = buf.split('\n'); buf = lines.pop() || ''
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
    } catch (err: any) { appendToken('\n\n' + err.message); finalizeAgent() }
    finally { isStreaming.value = false }
  }

  function clearMessages() { messages.value = []; sessionId.value = null }
  function renderMarkdown(text: string) { return marked.parse(text) }
  return { messages, isStreaming, sessionId, currentAgent, sendMessage, sendMultimodal, clearMessages, renderMarkdown }
}
