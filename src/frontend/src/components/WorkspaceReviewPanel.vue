<template>
  <section class="workspace-review card">
    <div class="panel-head">
      <div>
        <h2>工作区综述</h2>
        <p>从当前页面明确选择 2–20 篇论文，生成一条可刷新恢复的结构化综述。</p>
      </div>
      <el-button text @click="expanded = !expanded">{{ expanded ? '收起' : '展开' }}</el-button>
    </div>

    <div v-if="expanded">
      <el-alert
        type="info"
        title="发送边界"
        :description="boundaryText"
        show-icon
        :closable="false"
      />

      <div class="selection-list" aria-label="工作区综述论文选择">
        <p v-if="!papers.length" class="empty">当前页面没有可选论文。</p>
        <el-checkbox
          v-for="paper in papers"
          :key="paper.id"
          :model-value="selectedIds.includes(paper.id)"
          :disabled="!selectedIds.includes(paper.id) && selectedIds.length >= MAX_WORKSPACE_REVIEW_PAPERS"
          :aria-label="`选择论文 #${paper.id} ${paper.title}`"
          @change="togglePaper(paper.id, $event)"
        >
          <span class="paper-choice"><b>#{{ paper.id }}</b> {{ paper.title }}</span>
        </el-checkbox>
      </div>

      <div class="scope-preview" data-testid="workspace-review-scope">
        <strong>本次精确范围（{{ selectedIds.length }} 篇）</strong>
        <p>论文 ID（按发送顺序）：{{ selectedIds.join('、') || '尚未选择' }}</p>
        <p>字段：标题（每篇最多 300 字符）、摘要（每篇最多 2,000 字符）。不发送作者、来源链接、关键词或全文。</p>
      </div>

      <el-checkbox v-model="confirmed" :disabled="!selectionValid">
        我确认只把以上精确 ID 和字段边界发送给当前配置的 AI provider
      </el-checkbox>
      <div class="actions">
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!selectionValid || !confirmed || submitting"
          @click="submitReview"
        >
          生成工作区综述
        </el-button>
        <el-button :loading="loadingHistory" @click="loadHistory">刷新审计历史</el-button>
        <span v-if="selectionError" class="selection-error">{{ selectionError }}</span>
      </div>

      <el-alert
        v-if="historyError"
        type="error"
        title="综述历史加载失败"
        :description="historyError"
        show-icon
        :closable="false"
      />

      <PaperAIRunHistory
        title="工作区综述运行历史"
        :runs="displayRuns"
        :paper-titles="paperTitles"
      />

      <section v-if="legacyReviews.length" class="legacy-history">
        <h3>迁移前综述（只读兼容）</h3>
        <p>旧记录缺少确切论文范围、提示词版本与模型元数据，不视为统一审计运行。</p>
        <article v-for="review in legacyReviews" :key="review.id">
          <strong>旧记录 #{{ review.id }}</strong> · {{ formatTime(review.created_at) }}
          <p>{{ review.review?.hot_topics || review.review?.raw || '旧结果无可展示摘要' }}</p>
        </article>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import PaperAIRunHistory from '@/components/PaperAIRunHistory.vue'
import {
  createWorkspaceReview,
  fetchWorkspaceReviews,
  getApiErrorMessage,
} from '@/api'
import {
  MAX_WORKSPACE_REVIEW_PAPERS,
  MIN_WORKSPACE_REVIEW_PAPERS,
  WORKSPACE_REVIEW_FIELDS,
} from '@/constants/aiLimits'
import { useWorkspaceStore } from '@/stores/workspace'

const props = defineProps({
  papers: { type: Array, default: () => [] },
})

const workspaceStore = useWorkspaceStore()
const expanded = ref(true)
const selectedIds = ref([])
const confirmed = ref(false)
const runs = ref([])
const legacyReviews = ref([])
const loadingHistory = ref(false)
const historyError = ref('')
const submitting = ref(false)
const pendingRun = ref(null)
let unregisterConsumer

const selectionValid = computed(() => (
  selectedIds.value.length >= MIN_WORKSPACE_REVIEW_PAPERS
  && selectedIds.value.length <= MAX_WORKSPACE_REVIEW_PAPERS
))
const selectionError = computed(() => {
  if (!selectedIds.value.length) return `请选择 ${MIN_WORKSPACE_REVIEW_PAPERS}–${MAX_WORKSPACE_REVIEW_PAPERS} 篇论文`
  if (!selectionValid.value) return `还需至少选择 ${MIN_WORKSPACE_REVIEW_PAPERS - selectedIds.value.length} 篇`
  return ''
})
const boundaryText = WORKSPACE_REVIEW_FIELDS
  .map((field) => `${field.label}每篇最多 ${field.maxChars.toLocaleString()} 字符`)
  .join('；') + '。一次只发送明确选择的 2–20 篇论文，不发送全文，AI 结果不会修改 papers 或来源事实。'
const paperTitles = computed(() => Object.fromEntries(
  props.papers.map((paper) => [paper.id, paper.title]),
))
const displayRuns = computed(() => pendingRun.value
  ? [pendingRun.value, ...runs.value]
  : runs.value)

watch(selectedIds, () => { confirmed.value = false }, { deep: true })

function togglePaper(paperId, checked) {
  if (checked) selectedIds.value = [...selectedIds.value, paperId]
  else selectedIds.value = selectedIds.value.filter((id) => id !== paperId)
}

function invalidate() {
  selectedIds.value = []
  confirmed.value = false
  runs.value = []
  legacyReviews.value = []
  pendingRun.value = null
  historyError.value = ''
  submitting.value = false
}

async function loadHistory() {
  const generation = workspaceStore.generation
  loadingHistory.value = true
  historyError.value = ''
  try {
    const data = await fetchWorkspaceReviews()
    if (generation !== workspaceStore.generation) return
    runs.value = data.runs || []
    legacyReviews.value = data.legacy_reviews || []
  } catch (error) {
    if (generation === workspaceStore.generation) {
      historyError.value = getApiErrorMessage(error, '无法读取工作区综述历史')
    }
  } finally {
    if (generation === workspaceStore.generation) loadingHistory.value = false
  }
}

async function submitReview() {
  if (!selectionValid.value || !confirmed.value) return
  const generation = workspaceStore.generation
  const paperIds = [...selectedIds.value]
  submitting.value = true
  pendingRun.value = {
    id: '等待服务端响应',
    run_kind: 'workspace_review',
    status: 'running',
    paper_ids: paperIds,
    input_scope: ['title:300', 'abstract:2000'],
    prompt_version: 'workspace-review-v1',
    created_at: new Date().toISOString(),
  }
  let response
  let requestError
  try {
    response = await createWorkspaceReview(paperIds)
  } catch (error) {
    requestError = error
  } finally {
    if (generation === workspaceStore.generation) {
      pendingRun.value = null
      await loadHistory()
      submitting.value = false
    }
  }
  if (generation !== workspaceStore.generation) return
  if (requestError) {
    ElMessage.error(getApiErrorMessage(requestError, '工作区综述请求失败'))
    return
  }
  if (response?.run?.status === 'succeeded') {
    ElMessage.success('工作区综述成功，审计记录已保存')
  } else {
    ElMessage.error(`工作区综述失败：${response?.run?.error_message || '请查看审计历史'}`)
  }
}

function formatTime(value) {
  return value ? String(value).slice(0, 19) : '—'
}

onMounted(() => {
  unregisterConsumer = workspaceStore.registerConsumer('workspace-review', {
    invalidate,
    reload: loadHistory,
  })
  loadHistory()
})

onUnmounted(() => unregisterConsumer?.())
</script>

<style scoped>
.workspace-review { padding: var(--space-lg); margin-bottom: var(--space-lg); }
.panel-head { display: flex; justify-content: space-between; gap: var(--space-md); }
.panel-head h2 { margin: 0; font-size: var(--font-size-lg); }
.panel-head p { margin: 5px 0 var(--space-md); color: var(--color-text-secondary); }
.selection-list { display: grid; gap: 6px; margin: var(--space-md) 0; max-height: 280px; overflow: auto; }
.paper-choice { white-space: normal; }
.scope-preview { padding: var(--space-sm); margin-bottom: var(--space-sm); background: var(--color-bg-secondary); border-radius: var(--radius-sm); }
.scope-preview p { margin: 5px 0 0; line-height: 1.5; }
.actions { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; margin: var(--space-sm) 0; }
.selection-error { color: var(--color-warning); font-size: var(--font-size-xs); }
.legacy-history { margin-top: var(--space-lg); padding-top: var(--space-md); border-top: 1px solid var(--color-border); color: var(--color-text-secondary); }
.legacy-history h3 { margin: 0; color: var(--color-text-primary); font-size: var(--font-size-sm); }
.legacy-history article { margin-top: var(--space-sm); padding: var(--space-sm); background: var(--color-bg-secondary); border-radius: var(--radius-sm); }
.legacy-history p { margin: 5px 0 0; }
.empty { color: var(--color-text-secondary); }
</style>
