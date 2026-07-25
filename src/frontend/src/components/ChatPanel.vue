<template>
  <div class="chat-panel card">
    <!-- Header -->
    <div class="chat-header">
      <span class="chat-title">🤖 AI 助手</span>
      <span class="chat-scope">📂 {{ scope }}</span>
    </div>

    <!-- Messages -->
    <div ref="msgList" class="chat-messages">
      <div v-if="messages.length === 0" class="chat-empty">
        选择模板或直接输入指令与 AI 对话
      </div>
      <div v-for="(m, i) in messages" :key="i" class="chat-msg" :class="m.role">
        <div class="msg-content" v-text="m.content"></div>
        <div class="msg-time">{{ m.time }}</div>
      </div>
      <div v-if="sending" class="chat-msg ai">
        <div class="msg-content typing">...</div>
      </div>
    </div>

    <!-- Input -->
    <div class="chat-input-row">
      <el-select v-model="selectedPreset" placeholder="模板" size="small" style="width:100px" @change="onPreset" clearable>
        <el-option v-for="(p, i) in presets" :key="i" :label="p.label" :value="i" />
      </el-select>
      <el-input
        v-model="input"
        placeholder="输入指令..."
        size="small"
        @keyup.enter="send"
      />
      <el-button type="primary" size="small" :disabled="!input.trim() || sending" @click="send">
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import axios from 'axios'

const props = defineProps({
  scope: { type: String, default: '工作区' },
  presets: { type: Array, default: () => [] },
  contextData: { type: Object, default: () => ({}) },
})

const messages = ref([])
const input = ref('')
const selectedPreset = ref()
const sending = ref(false)
const msgList = ref(null)

function onPreset(idx) {
  if (idx !== undefined && idx !== null && props.presets[idx]) {
    input.value = props.presets[idx].template
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return

  const now = new Date().toLocaleTimeString()
  messages.value.push({ role: 'user', content: text, time: now })
  input.value = ''
  sending.value = true

  await nextTick()
  if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight

  try {
    const resp = await axios.post('/api/chat', {
      message: text,
      scope: props.scope,
      context: props.contextData,
    })
    const data = resp.data
    messages.value.push({
      role: 'ai',
      content: data.reply || data.error || '无响应',
      time: new Date().toLocaleTimeString(),
    })
  } catch (e) {
    messages.value.push({
      role: 'ai',
      content: '错误: ' + (e.response?.data?.detail || e.message),
      time: new Date().toLocaleTimeString(),
    })
  } finally {
    sending.value = false
    await nextTick()
    if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-panel {
  padding: 0;
  overflow: hidden;
  margin-bottom: var(--space-md);
}
.chat-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 16px; background: var(--color-bg);
  border-bottom: 1px solid var(--color-border-light);
  font-size: var(--font-size-sm);
}
.chat-title { font-weight: var(--font-weight-medium); }
.chat-scope { font-size: var(--font-size-xs); color: var(--color-text-secondary); }

.chat-messages {
  max-height: 400px; overflow-y: auto; padding: 12px 16px;
  display: flex; flex-direction: column; gap: 10px;
}
.chat-empty { text-align: center; color: var(--color-text-disabled); padding: 40px 0; font-size: var(--font-size-sm); }

.chat-msg { max-width: 85%; }
.chat-msg.user { align-self: flex-end; }
.chat-msg.ai { align-self: flex-start; }

.msg-content {
  padding: 8px 12px; border-radius: var(--radius-md);
  font-size: var(--font-size-sm); line-height: 1.6; white-space: pre-wrap;
}
.chat-msg.user .msg-content { background: var(--color-primary); color: #fff; }
.chat-msg.ai .msg-content { background: var(--color-bg); color: var(--color-text-primary); }
.msg-content.typing { color: var(--color-text-disabled); }
.msg-time { font-size: 10px; color: var(--color-text-disabled); margin-top: 2px; padding: 0 4px; }

.chat-input-row {
  display: flex; gap: var(--space-xs); padding: 8px 12px;
  border-top: 1px solid var(--color-border-light);
}
</style>
