<template>
  <div class="papers-page">
    <h1 class="page-title">论文中心</h1>

    <WorkspaceManager
      ref="wsManager"
      :paper-count="totalPapers"
      @workspace-changed="onWorkspaceChanged"
      @clear="handleClearWorkspace"
    />

    <!-- Content -->
    <CrawlProgress
      :status="crawlStatus"
      :percentage="crawlPercentage"
      :message="crawlMessage"
    />

    <CrawlControl
      :sources="journalSources"
      @add-source="showAddDialog = true"
      @delete-source="handleDeleteSource"
      @crawl-start="handleCrawlStart"
    />

    <div class="review-trigger">
      <el-button type="primary" plain size="small" :loading="reviewLoading" @click="handleWorkspaceReview">
        🤖 生成工作区报告
      </el-button>
      <span v-if="reviewStatus" class="review-status" :class="{ 'review-error': reviewStatus.includes('失败') }">{{ reviewStatus }}</span>
      <span v-else-if="aiSettingsHint" class="review-status">{{ aiSettingsHint }}</span>
    </div>
    <AIReviewCard :review="aiReview" />

    <PaperFilterBar @filter-change="handleFilter" />

    <KeywordFilter
      :keywords="workspaceKeywords"
      @filter-change="handleKeywordFilter"
    />

    <!-- Paper list: show empty only when done loading and truly empty -->
    <div v-if="!loading.papers && papers.length === 0" class="empty-state">
      <div class="empty-state-icon">📄</div>
      <p>暂无论文数据</p>
      <p class="text-small text-secondary">添加期刊源后点击爬取按钮</p>
    </div>

    <div v-if="papers.length > 0" class="paper-list">
      <PaperCard
        v-for="paper in papers"
        :key="paper.id"
        :paper="paper"
        @toggle-cart="handleToggleCart(paper)"
        @view-detail="openDetail(paper)"
      />
    </div>

    <!-- Pagination -->
    <div v-if="totalPapers > pageSize" class="pagination-row flex-center">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="totalPapers"
        layout="prev, pager, next"
        size="small"
        @current-change="loadPapers"
      />
    </div>

    <!-- Crawl error -->
    <div v-if="error" class="error-state">
      <el-alert :title="error" type="error" show-icon :closable="false" />
    </div>

    <!-- Dialogs -->
    <AddSourceDialog
      v-model:visible="showAddDialog"
      @add="handleAddSource"
    />

    <PaperDetailModal
      v-model:visible="showDetail"
      :paper="selectedPaper"
      @toggle-cart="handleToggleCart"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import CrawlControl from '@/components/CrawlControl.vue'
import CrawlProgress from '@/components/CrawlProgress.vue'
import AIReviewCard from '@/components/AIReviewCard.vue'
import WorkspaceManager from '@/components/WorkspaceManager.vue'
import PaperFilterBar from '@/components/PaperFilterBar.vue'
import KeywordFilter from '@/components/KeywordFilter.vue'
import PaperCard from '@/components/PaperCard.vue'
import PaperDetailModal from '@/components/PaperDetailModal.vue'
import AddSourceDialog from '@/components/AddSourceDialog.vue'
import { useCartStore } from '@/stores/cart'
import { useSettingsStore } from '@/stores/settings'
import {
  fetchJournals, addJournal, deleteJournal,
  startCrawl, getCrawlStatus,
  fetchPapers, updatePaper,
  fetchLatestSession,
  fetchKeywords, triggerWorkspaceReview, clearWorkspace,
} from '@/api'

const cartStore = useCartStore()
const wsManager = ref(null)

async function handleWorkspaceReview() {
  reviewLoading.value = true
  reviewStatus.value = 'AI 分析中，请稍候...'
  try {
    const res = await triggerWorkspaceReview()
    const data = res.data || res
    if (!data.ok) {
      reviewStatus.value = `失败: ${data.error}`
      if (data.hint) ElMessage.warning(data.hint)
      reviewLoading.value = false
      return
    }
    // 直接显示结果
    if (data.review) {
      aiReview.value = data.review
      aiReview.value.total_papers = data.meta?.paper_count
    }
    // 从 DB 重新加载确保数据一致
    await loadLatestReview()
    reviewStatus.value = `✓ 点评完成 (${data.meta?.api_type} / ${data.meta?.model})`
    reviewLoading.value = false
  } catch (e) {
    const msg = e.response?.data?.error || e.message || '网络错误'
    reviewStatus.value = `失败: ${msg}`
    reviewLoading.value = false
  }
}

function onWorkspaceChanged() {
  papers.value = []
  totalPapers.value = 0
  loadPapers()
  loadJournals()
  loadKeywords()
}

async function handleClearWorkspace() {
  try {
    await ElMessageBox.confirm('确定清空当前工作区所有论文？此操作不可恢复。', '确认清空', {
      confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning',
    })
    await clearWorkspace()
    papers.value = []
    totalPapers.value = 0
    workspaceKeywords.value = []
    keywordFilter.value = { keywords: [], mode: 'or' }
    aiReview.value = null
    ElMessage.success('已清空')
  } catch { /* cancelled */ }
}

// ---- State ----
const journalSources = ref([])
const papers = ref([])
const totalPapers = ref(0)
const aiReview = ref(null)
const showAddDialog = ref(false)
const showDetail = ref(false)
const selectedPaper = ref(null)
const reviewLoading = ref(false)
const reviewStatus = ref('')
const aiSettingsHint = computed(() => {
  const s = useSettingsStore()
  if (!s.aiConfig.apiKey) return '提示：前往全局设置配置 AI Key'
  return `AI: ${s.aiConfig.apiType} / ${s.aiConfig.model}`
})
const page = ref(1)
const pageSize = 20
const error = ref('')
const crawlStatus = ref('idle')
const crawlPercentage = ref(0)
const crawlMessage = ref('')
const workspaceKeywords = ref([])
const keywordFilter = ref({ keywords: [], mode: 'or' })
const filters = ref({ search: '', hasCode: false, inCart: false, sort: 'newest' })
const loading = reactive({ journals: true, papers: false })
let crawlPollTimer = null

// ---- Lifecycle ----
async function loadKeywords() {
  try {
    const res = await fetchKeywords()
    workspaceKeywords.value = (res.data || res) || []
  } catch { /* ignore */ }
}

function handleKeywordFilter(kf) {
  keywordFilter.value = kf
  page.value = 1
  loadPapers()
}

onMounted(() => {
  loadJournals()
  loadPapers()
  loadLatestReview()
  loadKeywords()
})

// ---- Data loading ----
async function loadJournals() {
  loading.journals = true
  try {
    const res = await fetchJournals()
    journalSources.value = Array.isArray(res) ? res : res.data || []
  } catch (e) {
    error.value = '加载期刊源失败'
  } finally {
    loading.journals = false
  }
}

async function loadPapers() {
  loading.papers = true
  try {
    const res = await fetchPapers({
      q: filters.value.search || undefined,
      has_code: filters.value.hasCode || undefined,
      in_cart: filters.value.inCart || undefined,
      keywords: keywordFilter.value.keywords.length > 0 ? keywordFilter.value.keywords.join(',') : undefined,
      kw_mode: keywordFilter.value.keywords.length > 0 ? keywordFilter.value.mode : undefined,
      sort: filters.value.sort,
      page: page.value,
      page_size: pageSize,
    })
    const data = res.data || res
    papers.value = data.items || []
    totalPapers.value = data.total || 0
  } catch (e) {
    error.value = '加载论文失败'
  } finally {
    loading.papers = false
  }
}

async function loadLatestReview() {
  try {
    const res = await fetchLatestSession()
    const session = res.data || res
    if (session && session.ai_review) {
      aiReview.value = typeof session.ai_review === 'string'
        ? JSON.parse(session.ai_review)
        : session.ai_review
      // Add stats from session
      if (!aiReview.value.total_papers) {
        aiReview.value.total_papers = session.paper_count || 0
      }
    }
  } catch (e) { /* no review yet */ }
}

// ---- Actions ----
function openDetail(paper) {
  selectedPaper.value = paper
  showDetail.value = true
}

async function handleToggleCart(paper) {
  const newCartState = !paper.in_cart
  // Optimistic update
  paper.in_cart = newCartState
  if (newCartState) {
    cartStore.addItem({ ...paper, in_cart: true })
  } else {
    cartStore.removeItem(paper.id)
  }
  // Persist to backend
  try {
    await updatePaper(paper.id, { in_cart: newCartState })
  } catch (e) {
    // Rollback on failure
    paper.in_cart = !newCartState
    if (newCartState) cartStore.removeItem(paper.id)
    else cartStore.addItem({ ...paper, in_cart: true })
    ElMessage.error('保存失败')
  }
}

function handleFilter(f) {
  filters.value = f
  page.value = 1
  loadPapers()
}

async function handleAddSource(url, label) {
  try {
    const res = await addJournal(url, label)
    const data = res.data || res
    journalSources.value.unshift(data)
    ElMessage.success('期刊源已添加')
  } catch (e) {
    ElMessage.error('添加失败')
  }
}

async function handleDeleteSource(id) {
  try {
    await deleteJournal(id)
    journalSources.value = journalSources.value.filter((s) => s.id !== id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function handleCrawlStart(sourceIds, mode, keywords, sortMode) {
  crawlStatus.value = 'crawling'
  crawlPercentage.value = 0
  crawlMessage.value = ''
  error.value = ''

  try {
    const res = await startCrawl(sourceIds, mode, keywords, sortMode)
    const data = res.data || res
    if (!data.ok) {
      ElMessage.warning(data.message || '爬取启动失败')
      crawlStatus.value = 'error'
      return
    }
    // Start polling
    crawlPollTimer = setInterval(pollCrawlStatus, 1500)
  } catch (e) {
    crawlStatus.value = 'error'
    crawlMessage.value = '启动爬取失败'
  }
}

async function pollCrawlStatus() {
  try {
    const res = await getCrawlStatus()
    const data = res.data || res
    crawlStatus.value = data.status
    crawlPercentage.value = data.percentage
    crawlMessage.value = data.message

    if (data.status === 'done' || data.status === 'error') {
      clearInterval(crawlPollTimer)
      crawlPollTimer = null
      if (data.status === 'done') {
        await loadJournals()
        await loadPapers()
        await loadLatestReview()
        await loadKeywords()
        // Update home stats via store
        const statsRes = await fetchStats()
        const stats = statsRes.data || statsRes
        if (stats) {
          window.__rmStats = stats
        }
      }
    }
  } catch (e) {
    clearInterval(crawlPollTimer)
    crawlPollTimer = null
    crawlStatus.value = 'error'
  }
}
</script>

<style scoped>
.papers-page {
  padding-top: var(--space-lg);
}

.pagination-row {
  padding: var(--space-lg) 0;
}

.loading-state {
  padding: var(--space-2xl);
  color: var(--color-text-secondary);
  gap: var(--space-sm);
}

.error-state {
  margin-top: var(--space-md);
}

.api-status {
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-md);
}

.api-status.ok {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.api-status.offline {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.debug-panel {
  background: #1e293b;
  color: #4ade80;
  font-family: monospace;
  font-size: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-md);
  line-height: 1.8;
}

.review-trigger { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-md); }
.review-status { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.review-error { color: var(--color-danger); font-weight: var(--font-weight-medium); }
</style>
