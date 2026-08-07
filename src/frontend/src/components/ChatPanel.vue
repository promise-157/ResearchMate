<template>
  <div class="chat-panel card">
    <!-- Header -->
    <div class="chat-header">
      <span class="chat-title">🤖 AI 助手</span>
      <div class="chat-header-right">
        <span v-if="contextData.paper_count" class="chat-scope">{{ contextData.paper_count }} 篇可用</span>
        <el-badge :value="attachedPapers.length" :hidden="attachedPapers.length === 0">
          <el-button size="small" text @click="showAttach = true">📎 附件</el-button>
        </el-badge>
      </div>
    </div>

    <div class="chat-capability-note">
      使用设置中的模型服务；当前不实时联网，只读取你的问题和明确附加的论文摘要。
    </div>

    <!-- Attached papers bar -->
    <div v-if="attachedPapers.length > 0" class="attach-bar">
      <el-tag
        v-for="p in attachedPapers" :key="p.id"
        size="small" closable type="info"
        @close="detach(p.id)"
      >
        {{ p.title.slice(0, 30) }}...
      </el-tag>
    </div>

    <!-- Messages -->
    <div ref="msgList" class="chat-messages">
      <div v-if="messages.length === 0" class="chat-empty">
        选择模板、附加论文或直接输入指令与 AI 对话
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
      <el-input v-model="input" placeholder="输入指令..." size="small" @keyup.enter="send" />
      <el-button type="primary" size="small" :disabled="!input.trim() || sending" @click="send">发送</el-button>
    </div>

    <!-- Attachment selector dialog -->
    <el-dialog v-model="showAttach" title="选择附加论文" width="600px">
      <el-input v-model="attachSearch" placeholder="搜索论文..." size="small" style="margin-bottom:12px" clearable />
      <div class="attach-select-list">
        <div v-for="p in filteredAttachPapers" :key="p.id" class="attach-select-item"
             :class="{ selected: isAttached(p.id) }"
             @click="toggleAttach(p)">
          <el-checkbox :model-value="isAttached(p.id)" @click.stop="toggleAttach(p)" />
          <div class="attach-select-info">
            <div class="attach-select-title">{{ p.title }}</div>
            <div class="attach-select-meta">{{ p.journal_name }} · {{ p.publish_year }}</div>
          </div>
        </div>
      </div>
      <template #footer>
        <span style="color:var(--color-text-secondary);font-size:13px">已选 {{ attachedPapers.length }} 篇</span>
        <el-button @click="showAttach = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
  presets: { type: Array, default: () => [] },
  contextData: { type: Object, default: () => ({}) },
})

const messages = ref([])
const input = ref('')
const selectedPreset = ref()
const sending = ref(false)
const msgList = ref(null)

// Attachments
const showAttach = ref(false)
const attachedPapers = ref([])
const attachSearch = ref('')
const allPapers = ref([])

// Load papers for attachment selector
watch(() => props.contextData.paper_count, async (count) => {
  if (count > 0) {
    try {
      const resp = await axios.get('/api/papers', { params: { page_size: 100 } })
      allPapers.value = resp.data?.items || resp.data?.data?.items || []
    } catch { /* ignore */ }
  }
}, { immediate: true })

const filteredAttachPapers = computed(() => {
  if (!attachSearch.value) return allPapers.value
  const q = attachSearch.value.toLowerCase()
  return allPapers.value.filter(p => p.title.toLowerCase().includes(q))
})

function isAttached(id) { return attachedPapers.value.some(p => p.id === id) }
function toggleAttach(p) {
  if (isAttached(p.id)) attachedPapers.value = attachedPapers.value.filter(x => x.id !== p.id)
  else attachedPapers.value.push(p)
}
function detach(id) { attachedPapers.value = attachedPapers.value.filter(p => p.id !== id) }

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
      paper_ids: attachedPapers.value.map(p => p.id),
    })
    messages.value.push({
      role: 'ai',
      content: resp.data.reply || resp.data.error || '无响应',
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
.chat-panel { padding: 0; overflow: hidden; margin-bottom: var(--space-md); }
.chat-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 16px; background: var(--color-bg);
  border-bottom: 1px solid var(--color-border-light); font-size: var(--font-size-sm);
}
.chat-title { font-weight: var(--font-weight-medium); }
.chat-header-right { display: flex; align-items: center; gap: var(--space-sm); }
.chat-scope { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.chat-capability-note {
  padding: 6px 16px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.attach-bar {
  display: flex; flex-wrap: wrap; gap: 4px;
  padding: 6px 12px; border-bottom: 1px solid var(--color-border-light);
  background: var(--color-primary-bg);
}

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

.attach-select-list { max-height: 400px; overflow-y: auto; }
.attach-select-item {
  display: flex; align-items: flex-start; gap: 10px; padding: 8px 4px;
  border-bottom: 1px solid var(--color-border-light); cursor: pointer;
}
.attach-select-item:hover { background: var(--color-bg); }
.attach-select-item.selected { background: var(--color-primary-bg); }
.attach-select-title { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); }
.attach-select-meta { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin-top: 2px; }
</style>
