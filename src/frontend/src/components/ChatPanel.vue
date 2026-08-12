<template>
  <div class="chat-panel card">
    <!-- Header -->
    <div class="chat-header">
      <span class="chat-title">🤖 AI 助手</span>
      <div class="chat-header-right">
        <el-select
          v-model="sessionId"
          placeholder="选择会话"
          size="small"
          style="width: 170px"
          @change="loadSession"
        >
          <el-option
            v-for="session in sessions"
            :key="session.id"
            :label="`${session.title} (${session.turn_count || 0})`"
            :value="session.id"
          />
        </el-select>
        <el-button size="small" text @click="startNewSession">新对话</el-button>
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
        选择历史会话，或附加论文后发送第一条消息。对话会保存在当前工作区。
      </div>
      <div v-for="(m, i) in messages" :key="i" class="chat-msg" :class="m.role">
        <div class="msg-content" v-text="m.content"></div>
        <div v-if="m.paperIds?.length" class="msg-audit">本轮附加论文 ID：{{ m.paperIds.join(', ') }}</div>
        <div v-if="m.audit" class="msg-audit">{{ m.audit }}</div>
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
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createChatSession, createChatTurn, fetchChatSession, fetchChatSessions, fetchPapers,
} from '@/api'
import { useWorkspaceStore } from '@/stores/workspace'
import { MAX_CHAT_ATTACHED_PAPERS } from '@/constants/aiLimits'

const props = defineProps({
  presets: { type: Array, default: () => [] },
  contextData: { type: Object, default: () => ({}) },
})

const input = ref('')
const selectedPreset = ref()
const sending = ref(false)
const msgList = ref(null)
const sessions = ref([])
const sessionId = ref(null)
const turns = ref([])
const workspaceStore = useWorkspaceStore()
let requestGeneration = 0
let latestSessionRequest = 0
let latestPapersRequest = 0
let latestSendRequest = 0

// Attachments
const showAttach = ref(false)
const attachedPapers = ref([])
const attachSearch = ref('')
const allPapers = ref([])

function invalidateWorkspaceData() {
  requestGeneration += 1
  latestSessionRequest += 1
  latestPapersRequest += 1
  latestSendRequest += 1
  sessionId.value = null
  sessions.value = []
  turns.value = []
  attachedPapers.value = []
  allPapers.value = []
  sending.value = false
}

async function loadAttachPapers(generation = requestGeneration) {
  const requestId = ++latestPapersRequest
  if (props.contextData.paper_count <= 0) {
    if (generation === requestGeneration && requestId === latestPapersRequest) {
      allPapers.value = []
    }
    return
  }
  try {
    const resp = await fetchPapers({ page_size: 100 })
    if (generation !== requestGeneration || requestId !== latestPapersRequest) return
    allPapers.value = resp?.items || resp?.data?.items || []
  } catch {
    if (generation === requestGeneration && requestId === latestPapersRequest) {
      allPapers.value = []
    }
  }
}

async function reloadWorkspaceData() {
  const generation = requestGeneration
  await Promise.all([loadAttachPapers(generation), loadSessions(generation)])
}

const unregisterWorkspaceConsumer = workspaceStore.registerConsumer('paper-chat', {
  invalidate: invalidateWorkspaceData,
  reload: reloadWorkspaceData,
})

watch(() => props.contextData.paper_count, () => loadAttachPapers(), { flush: 'post' })
onMounted(reloadWorkspaceData)
onUnmounted(unregisterWorkspaceConsumer)

const messages = computed(() => turns.value.flatMap((turn) => {
  const result = [{
    role: 'user', content: turn.user_message, time: turn.created_at || '',
    paperIds: turn.paper_ids || [],
  }]
  if (turn.status === 'succeeded') {
    const usage = turn.input_tokens != null || turn.output_tokens != null
      ? ` · ${turn.input_tokens ?? '?'}↑/${turn.output_tokens ?? '?'}↓ token`
      : ''
    result.push({
      role: 'ai', content: turn.assistant_message, time: turn.completed_at || '',
      audit: `${turn.provider || ''} · ${turn.provider_model || turn.model || ''}${usage}`,
    })
  } else if (turn.status === 'failed') {
    result.push({
      role: 'ai error', content: `失败：${turn.error_message}`, time: turn.completed_at || '',
      audit: `${turn.provider || ''} · ${turn.model || ''}`,
    })
  }
  return result
}))

async function loadSessions(generation = requestGeneration) {
  const requestId = ++latestSessionRequest
  try {
    const loadedSessions = await fetchChatSessions()
    if (generation !== requestGeneration || requestId !== latestSessionRequest) return
    sessions.value = loadedSessions
    if (sessions.value.length > 0) {
      sessionId.value = sessions.value[0].id
      await loadSession(sessionId.value, generation)
    } else {
      sessionId.value = null
      turns.value = []
    }
  } catch {
    if (generation === requestGeneration && requestId === latestSessionRequest) {
      sessions.value = []
      sessionId.value = null
      turns.value = []
      ElMessage.error('聊天会话加载失败')
    }
  }
}

async function loadSession(id, generation = requestGeneration) {
  if (!id) {
    turns.value = []
    return
  }
  const requestId = ++latestSessionRequest
  try {
    const session = await fetchChatSession(id)
    if (generation !== requestGeneration || requestId !== latestSessionRequest) return
    turns.value = session.turns || []
    await scrollToBottom()
  } catch {
    if (generation === requestGeneration && requestId === latestSessionRequest) {
      turns.value = []
      ElMessage.error('聊天记录加载失败')
    }
  }
}

async function startNewSession() {
  const generation = requestGeneration
  const requestId = ++latestSessionRequest
  try {
    const session = await createChatSession()
    if (generation !== requestGeneration || requestId !== latestSessionRequest) return
    sessions.value.unshift({ ...session, turn_count: 0 })
    sessionId.value = session.id
    turns.value = []
  } catch {
    if (generation === requestGeneration && requestId === latestSessionRequest) {
      ElMessage.error('新建聊天会话失败')
    }
  }
}

const filteredAttachPapers = computed(() => {
  if (!attachSearch.value) return allPapers.value
  const q = attachSearch.value.toLowerCase()
  return allPapers.value.filter(p => p.title.toLowerCase().includes(q))
})

function isAttached(id) { return attachedPapers.value.some(p => p.id === id) }
function toggleAttach(p) {
  if (isAttached(p.id)) attachedPapers.value = attachedPapers.value.filter(x => x.id !== p.id)
  else if (attachedPapers.value.length >= MAX_CHAT_ATTACHED_PAPERS) {
    ElMessage.warning(`单轮最多附加 ${MAX_CHAT_ATTACHED_PAPERS} 篇论文`)
  }
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

  input.value = ''
  sending.value = true

  const generation = requestGeneration
  const sendRequest = ++latestSendRequest
  try {
    if (!sessionId.value) await startNewSession()
    if (!sessionId.value) throw new Error('无法创建聊天会话')
    const turn = await createChatTurn(sessionId.value, {
      message: text,
      paper_ids: attachedPapers.value.map(p => p.id),
    })
    if (generation !== requestGeneration) return
    turns.value.push(turn)
    await loadSessions(generation)
    if (turn.status === 'failed') ElMessage.error(turn.error_message || 'AI 对话失败')
  } catch (e) {
    if (generation === requestGeneration) {
      ElMessage.error(e.response?.data?.detail || e.message || 'AI 对话失败')
    }
  } finally {
    if (generation === requestGeneration && sendRequest === latestSendRequest) {
      sending.value = false
      await nextTick()
      if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
    }
  }
}

async function scrollToBottom() {
  await nextTick()
  if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
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
.chat-msg.ai.error .msg-content { background: var(--color-danger-light-9); }
.msg-content {
  padding: 8px 12px; border-radius: var(--radius-md);
  font-size: var(--font-size-sm); line-height: 1.6; white-space: pre-wrap;
}
.chat-msg.user .msg-content { background: var(--color-primary); color: #fff; }
.chat-msg.ai .msg-content { background: var(--color-bg); color: var(--color-text-primary); }
.msg-content.typing { color: var(--color-text-disabled); }
.msg-time { font-size: 10px; color: var(--color-text-disabled); margin-top: 2px; padding: 0 4px; }
.msg-audit { font-size: 10px; color: var(--color-text-secondary); margin-top: 2px; padding: 0 4px; }

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
