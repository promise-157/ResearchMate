<template>
  <div class="papers-page">
    <h1 class="page-title">论文中心</h1>

    <!-- API status indicator -->
    <div v-if="apiStatus" class="api-status" :class="apiStatus">
      {{ apiStatus === 'ok' ? '✓ 后端已连接' : '✗ 后端未连接 — 请确认 python run.py 已启动' }}
    </div>

    <!-- DEBUG: data flow trace -->
    <div v-if="debugInfo" class="debug-panel">
      <div v-for="(line, i) in debugInfo" :key="i" class="debug-line">{{ line }}</div>
    </div>

    <!-- Loading -->
    <div v-if="loading.journals" class="loading-state flex-center">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <template v-else>
      <!-- Progress -->
      <CrawlProgress
        :status="crawlStatus"
        :percentage="crawlPercentage"
        :message="crawlMessage"
      />

      <!-- Area 1: Crawl Control -->
      <CrawlControl
        :sources="journalSources"
        @add-source="showAddDialog = true"
        @delete-source="handleDeleteSource"
        @crawl-start="handleCrawlStart"
      />

      <!-- Area 2: AI Review -->
      <AIReviewCard :review="aiReview" />

      <!-- Area 3: Filter + Paper List -->
      <PaperFilterBar @filter-change="handleFilter" />

      <div v-if="loading.papers" class="loading-state flex-center">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载论文...</span>
      </div>

      <div v-else-if="papers.length === 0" class="empty-state">
        <div class="empty-state-icon">📄</div>
        <p>暂无论文数据</p>
        <p class="text-small text-secondary">添加期刊源后点击爬取按钮</p>
      </div>

      <TransitionGroup v-else name="fade" tag="div">
        <PaperCard
          v-for="paper in papers"
          :key="paper.id"
          :paper="paper"
          @toggle-cart="handleToggleCart(paper)"
          @view-detail="openDetail(paper)"
        />
      </TransitionGroup>

      <!-- Pagination -->
      <div v-if="totalPapers > pageSize" class="pagination-row flex-center">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="totalPapers"
          layout="prev, pager, next"
          small
          @current-change="loadPapers"
        />
      </div>

      <!-- Crawl error -->
      <div v-if="error" class="error-state">
        <el-alert :title="error" type="error" show-icon :closable="false" />
      </div>
    </template>

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
import { ElMessage } from 'element-plus'
import axios from 'axios'
import CrawlControl from '@/components/CrawlControl.vue'
import CrawlProgress from '@/components/CrawlProgress.vue'
import AIReviewCard from '@/components/AIReviewCard.vue'
import PaperFilterBar from '@/components/PaperFilterBar.vue'
import PaperCard from '@/components/PaperCard.vue'
import PaperDetailModal from '@/components/PaperDetailModal.vue'
import AddSourceDialog from '@/components/AddSourceDialog.vue'
import { useCartStore } from '@/stores/cart'
import {
  fetchJournals, addJournal, deleteJournal,
  startCrawl, getCrawlStatus,
  fetchPapers, updatePaper,
  fetchLatestSession, fetchStats,
} from '@/api'

const cartStore = useCartStore()

// ---- State ----
const apiStatus = ref(null) // null=checking, 'ok', 'offline'
const debugInfo = ref([])   // TEMP: trace data flow
const journalSources = ref([])
const papers = ref([])
const totalPapers = ref(0)
const aiReview = ref(null)
const showAddDialog = ref(false)
const showDetail = ref(false)
const selectedPaper = ref(null)
const page = ref(1)
const pageSize = 20
const error = ref('')
const crawlStatus = ref('idle')
const crawlPercentage = ref(0)
const crawlMessage = ref('')
const filters = ref({ search: '', hasCode: false, inCart: false, sort: 'newest' })
const loading = reactive({ journals: true, papers: false })
let crawlPollTimer = null

// ---- Lifecycle ----
onMounted(async () => {
  try {
    await axios.get('/api/health')
    apiStatus.value = 'ok'
  } catch {
    apiStatus.value = 'offline'
  }
  loadJournals()
  loadPapers()
  loadLatestReview()
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
  const log = []
  try {
    log.push(`1. 发起请求 GET /api/papers?page=1&page_size=20`)
    const res = await fetchPapers({
      q: filters.value.search || undefined,
      has_code: filters.value.hasCode || undefined,
      in_cart: filters.value.inCart || undefined,
      sort: filters.value.sort,
      page: page.value,
      page_size: pageSize,
    })
    log.push(`2. 收到响应 typeof=${typeof res} keys=${Object.keys(res || {}).join(',')}`)
    const data = res.data || res
    log.push(`3. data typeof=${typeof data} keys=${Object.keys(data || {}).join(',')}`)
    log.push(`4. data.total=${data.total} data.items?.length=${data.items?.length}`)
    papers.value = data.items || []
    totalPapers.value = data.total || 0
    log.push(`5. papers.value.length=${papers.value.length} totalPapers=${totalPapers.value}`)
  } catch (e) {
    log.push(`ERR: ${e.message || e}`)
    error.value = '加载论文失败'
  } finally {
    loading.papers = false
    debugInfo.value = log
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

async function handleCrawlStart(sourceIds, mode) {
  crawlStatus.value = 'crawling'
  crawlPercentage.value = 0
  crawlMessage.value = ''
  error.value = ''

  try {
    const res = await startCrawl(sourceIds, mode)
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
        // Refresh data
        await loadJournals()
        await loadPapers()
        await loadLatestReview()
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
</style>
