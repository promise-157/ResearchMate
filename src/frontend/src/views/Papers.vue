<template>
  <div class="papers-page">
    <h1 class="page-title">论文中心</h1>

    <!-- Workspace selector -->
    <div class="workspace-bar">
      <div class="ws-info">
        <el-icon><FolderOpened /></el-icon>
        <span class="ws-label">工作区: {{ wsName }}</span>
        <span class="ws-count">({{ totalPapers }} 篇)</span>
      </div>
      <div class="ws-actions">
        <el-button size="small" @click="showWsDialog = true">切换</el-button>
        <el-button size="small" @click="handleNewWorkspace">新建</el-button>
        <el-button size="small" type="danger" plain @click="handleClearWorkspace">清空</el-button>
      </div>
    </div>

    <!-- Workspace dialog -->
    <el-dialog v-model="showWsDialog" title="切换工作区" width="480px">
      <div v-if="wsList.length === 0" style="color:#999;text-align:center;padding:20px">暂无工作区</div>
      <div v-for="ws in wsList" :key="ws.id" class="ws-item"
           :class="{ active: ws.db_path === currentWsPath }"
           @click="handleSwitchWs(ws)">
        <div>
          <div class="ws-item-name">{{ ws.name }}</div>
          <div class="ws-item-meta">{{ ws.paper_count || 0 }} 篇 · {{ ws.opened_at || '' }}</div>
        </div>
        <el-button v-if="ws.db_path !== currentWsPath" size="small" type="primary" plain>加载</el-button>
        <el-tag v-else size="small" type="success">当前</el-tag>
      </div>
    </el-dialog>

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
      <span v-if="reviewStatus" class="review-status">{{ reviewStatus }}</span>
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import CrawlControl from '@/components/CrawlControl.vue'
import CrawlProgress from '@/components/CrawlProgress.vue'
import AIReviewCard from '@/components/AIReviewCard.vue'
import PaperFilterBar from '@/components/PaperFilterBar.vue'
import KeywordFilter from '@/components/KeywordFilter.vue'
import PaperCard from '@/components/PaperCard.vue'
import PaperDetailModal from '@/components/PaperDetailModal.vue'
import AddSourceDialog from '@/components/AddSourceDialog.vue'
import { useCartStore } from '@/stores/cart'
import {
  fetchJournals, addJournal, deleteJournal,
  startCrawl, getCrawlStatus,
  fetchPapers, updatePaper,
  fetchLatestSession, fetchStats,
  fetchWorkspaces, createWorkspace, loadWorkspace, clearWorkspace,
  fetchKeywords, triggerWorkspaceReview,
} from '@/api'

const cartStore = useCartStore()

// ---- Workspace ----
const showWsDialog = ref(false)
const wsName = ref('default')
const currentWsPath = ref('')
const wsList = ref([])

async function loadWorkspaces() {
  try {
    const res = await fetchWorkspaces()
    const data = res.data || res
    wsList.value = data.items || []
    currentWsPath.value = data.active_path
    wsName.value = data.active_name || 'default'
  } catch { /* ignore */ }
}

async function handleSwitchWs(ws) {
  try {
    await loadWorkspace(ws.db_path)
    currentWsPath.value = ws.db_path
    wsName.value = ws.name
    showWsDialog.value = false
    papers.value = []
    totalPapers.value = 0
    loadPapers()
    loadJournals()
    ElMessage.success(`已切换到: ${ws.name}`)
  } catch { ElMessage.error('切换失败') }
}

async function handleNewWorkspace() {
  try {
    const name = prompt('工作区名称:')
    if (!name) return
    const res = await createWorkspace(name)
    const data = res.data || res
    currentWsPath.value = data.db_path
    wsName.value = data.name
    papers.value = []
    totalPapers.value = 0
    loadPapers()
    loadJournals()
    loadWorkspaces()
    ElMessage.success(`已创建: ${data.name}`)
  } catch { ElMessage.error('创建失败') }
}

async function handleWorkspaceReview() {
  reviewLoading.value = true
  reviewStatus.value = '正在生成...'
  try {
    await triggerWorkspaceReview()
    reviewStatus.value = '点评完成，刷新中...'
    setTimeout(async () => {
      await loadLatestReview()
      reviewStatus.value = ''
      reviewLoading.value = false
    }, 3000)
  } catch {
    reviewStatus.value = '生成失败（请确认已配置 AI Key）'
    reviewLoading.value = false
  }
}

async function handleClearWorkspace() {
  try {
    await ElMessageBox.confirm('确定清空当前工作区所有论文？此操作不可恢复。', '确认清空', {
      confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning',
    })
    await clearWorkspace()
    papers.value = []
    totalPapers.value = 0
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
  loadWorkspaces()
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

.workspace-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-md);
}
.ws-info { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-size-sm); }
.ws-label { font-weight: var(--font-weight-medium); }
.ws-count { color: var(--color-text-secondary); }
.ws-actions { display: flex; gap: var(--space-xs); }
.ws-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px; border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm); margin-bottom: 8px; cursor: pointer;
}
.ws-item:hover { border-color: var(--color-primary); }
.ws-item.active { border-color: var(--color-primary); background: var(--color-primary-bg); }
.ws-item-name { font-size: var(--font-size-base); font-weight: var(--font-weight-medium); }
.ws-item-meta { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin-top: 2px; }

.review-trigger { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-md); }
.review-status { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
</style>
