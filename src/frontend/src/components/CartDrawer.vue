<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="购物车"
    direction="rtl"
    size="560px"
  >
    <el-alert
      v-if="cartStore.error"
      class="cart-error"
      type="error"
      title="购物车数据加载失败"
      :description="cartStore.error"
      show-icon
      :closable="false"
    >
      <template #default>
        <el-button size="small" :loading="cartStore.loading" @click="cartStore.refreshFromBackend()">
          重试
        </el-button>
      </template>
    </el-alert>

    <div v-if="cartStore.loading && cartStore.items.length === 0" class="cart-loading">
      正在加载当前工作区购物车…
    </div>
    <div v-else-if="cartStore.items.length === 0" class="cart-empty">
      <p>购物车为空</p>
      <p class="hint">浏览论文时点击 🛒 即可加入购物车</p>
    </div>
    <div v-else class="cart-list">
      <el-alert
        class="analysis-boundary"
        type="info"
        title="AI 分析边界"
        description="每次只发送所选论文的标题与摘要。新结果是可审计的 AI 建议，不会改写标题、摘要、作者、来源链接或来源代码事实。"
        show-icon
        :closable="false"
      />

      <div class="cart-toolbar">
        <el-button
          size="small"
          :loading="batchAnalyzing"
          :disabled="cartStore.items.length > MAX_CART_ANALYSIS_PAPERS || rowAnalyzingIds.size > 0"
          @click="analyzeAll"
        >
          🤖 批量 AI 分析（{{ cartStore.items.length }} 篇）
        </el-button>
        <span v-if="cartStore.items.length > MAX_CART_ANALYSIS_PAPERS" class="cart-limit">
          单次上限 {{ MAX_CART_ANALYSIS_PAPERS }} 篇，请先缩小清单
        </span>
        <span v-if="cartStore.loading" class="cart-refreshing">正在读取持久结果…</span>
      </div>

      <article v-for="item in cartStore.items" :key="item.id" class="cart-item">
        <div class="cart-item-head">
          <div class="cart-item-info">
            <div class="cart-item-title">{{ item.title }}</div>
            <div class="cart-item-source">{{ item.journal_name || '未知来源' }}</div>
            <div class="source-facts">
              来源代码事实：{{ item.has_code ? '有代码记录' : '无代码记录' }}
              <a v-if="item.code_url" :href="item.code_url" target="_blank" rel="noopener noreferrer">{{ item.code_url }}</a>
            </div>
          </div>
          <div class="cart-item-actions">
            <el-button
              size="small"
              text
              type="primary"
              :aria-label="`分析 ${item.title}`"
              :loading="isAnalyzing(item.id)"
              :disabled="batchAnalyzing"
              @click="analyzeOne(item)"
            >
              分析
            </el-button>
            <el-button
              size="small"
              text
              type="danger"
              :aria-label="`移除 ${item.title}`"
              :disabled="batchAnalyzing || isAnalyzing(item.id)"
              @click="removeOne(item.id)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>

        <PaperAIRunHistory
          title="论文分析运行历史"
          :runs="item.analysis_runs || []"
        />

        <section v-if="hasLegacyResult(item)" class="legacy-result">
          <strong>旧兼容结果（只读）</strong>
          <p>此区域仅展示迁移前的 papers.ai_* 数据，不代表统一审计运行，也不会改写来源事实。</p>
          <p v-if="item.ai_innovation">旧创新分析：{{ item.ai_innovation }}</p>
          <p v-if="item.ai_code_url">
            旧 AI 代码链接：
            <a :href="item.ai_code_url" target="_blank" rel="noopener noreferrer">{{ item.ai_code_url }}</a>
          </p>
          <div v-if="parseTags(item.ai_technologies).length" class="ai-mini-tags">
            旧技术标签：
            <el-tag
              v-for="technology in parseTags(item.ai_technologies)"
              :key="technology"
              size="small"
              type="info"
            >{{ technology }}</el-tag>
          </div>
        </section>
      </article>

      <div class="cart-actions">
        <el-button @click="copyTitles">复制标题列表</el-button>
        <el-button type="primary" @click="exportCSV">导出 CSV</el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useCartStore } from '@/stores/cart'
import { useWorkspaceStore } from '@/stores/workspace'
import PaperAIRunHistory from '@/components/PaperAIRunHistory.vue'
import { MAX_CART_ANALYSIS_PAPERS } from '@/constants/aiLimits'
import {
  analyzeAllCart,
  analyzeCartPapers,
  exportCart,
  getApiErrorMessage,
} from '@/api'

defineProps({ visible: Boolean })
defineEmits(['update:visible'])

const cartStore = useCartStore()
const workspaceStore = useWorkspaceStore()
const batchAnalyzing = ref(false)
const rowAnalyzingIds = ref(new Set())

watch(() => workspaceStore.generation, () => {
  batchAnalyzing.value = false
  rowAnalyzingIds.value = new Set()
}, { flush: 'sync' })

function parseTags(value) {
  if (!value) return []
  if (Array.isArray(value)) return value.filter(Boolean)
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed.filter(Boolean) : []
  } catch {
    return String(value).split(/[,，]/).map((entry) => entry.trim()).filter(Boolean)
  }
}

function hasLegacyResult(item) {
  return Boolean(
    item.ai_analyzed
    || item.cart_ai_analyzed
    || item.ai_innovation
    || item.ai_technologies
    || item.ai_code_url,
  )
}

function isAnalyzing(paperId) {
  return rowAnalyzingIds.value.has(paperId)
}

function setRowAnalyzing(paperId, value) {
  const next = new Set(rowAnalyzingIds.value)
  if (value) next.add(paperId)
  else next.delete(paperId)
  rowAnalyzingIds.value = next
}

function failedRunDetails(result) {
  return (result?.runs || [])
    .filter((run) => run?.status === 'failed')
    .map((run) => `#${run.paper_id ?? run.paper_ids?.[0] ?? '—'} ${run.error_message || '分析失败'}`)
    .join('；')
}

function reportAnalysisResult(result, batch) {
  const requested = Number(result?.requested) || (batch ? cartStore.items.length : 1)
  const succeeded = Number(result?.succeeded) || 0
  const failed = Number(result?.failed) || Math.max(0, requested - succeeded)
  if (result?.overall_status === 'succeeded') {
    ElMessage.success(batch ? `${succeeded}/${requested} 篇论文分析成功` : '单篇分析成功，AI 建议已记录')
    return
  }
  const details = failedRunDetails(result)
  if (result?.overall_status === 'partial') {
    ElMessage.warning(`${succeeded}/${requested} 篇成功，${failed} 篇失败；请查看逐篇失败记录${details ? `：${details}` : ''}`)
    return
  }
  if (result?.overall_status === 'failed') {
    ElMessage.error(`分析失败：${succeeded}/${requested} 篇成功，${failed} 篇失败${details ? `；${details}` : ''}`)
    return
  }
  ElMessage.error(result?.message || '分析响应缺少有效的整体状态')
}

async function analyzeOne(paper) {
  const generation = workspaceStore.generation
  setRowAnalyzing(paper.id, true)
  let result
  let requestError
  try {
    result = await analyzeCartPapers([paper.id])
  } catch (error) {
    requestError = error
  } finally {
    if (generation === workspaceStore.generation) await cartStore.refreshFromBackend()
    setRowAnalyzing(paper.id, false)
  }
  if (generation !== workspaceStore.generation) return
  if (requestError) {
    ElMessage.error(getApiErrorMessage(requestError, '单篇分析请求失败'))
    return
  }
  reportAnalysisResult(result, false)
}

async function analyzeAll() {
  const generation = workspaceStore.generation
  batchAnalyzing.value = true
  let result
  let requestError
  try {
    result = await analyzeAllCart(cartStore.items.length)
  } catch (error) {
    requestError = error
  } finally {
    if (generation === workspaceStore.generation) await cartStore.refreshFromBackend()
    batchAnalyzing.value = false
  }
  if (generation !== workspaceStore.generation) return
  if (requestError) {
    ElMessage.error(getApiErrorMessage(requestError, '批量分析请求失败'))
    return
  }
  reportAnalysisResult(result, true)
}

async function copyTitles() {
  try {
    const titles = cartStore.items.map((paper) => paper.title).join('\n')
    await navigator.clipboard.writeText(titles)
    ElMessage.success('已复制到剪贴板')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '复制失败'))
  }
}

async function removeOne(id) {
  const generation = workspaceStore.generation
  try {
    await cartStore.removeFromCart(id)
  } catch (error) {
    if (generation === workspaceStore.generation) {
      ElMessage.error(getApiErrorMessage(error, '移除失败'))
    }
  }
}

async function exportCSV() {
  try {
    const result = await exportCart('csv')
    const blob = new Blob([result.data], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'researchmate-shortlist.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '导出失败'))
  }
}
</script>

<style scoped>
.cart-loading, .cart-empty {
  text-align: center;
  padding: 40px 0;
  color: var(--color-text-secondary);
}
.cart-empty .hint { font-size: 13px; margin-top: 8px; }
.cart-error, .analysis-boundary { margin-bottom: var(--space-md); }
.cart-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  flex-wrap: wrap;
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--color-border);
}
.cart-limit { color: var(--color-warning); font-size: var(--font-size-xs); }
.cart-refreshing { color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.cart-item {
  padding: var(--space-md) 0;
  border-bottom: 1px solid var(--color-border);
}
.cart-item-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-sm); }
.cart-item-info { flex: 1; min-width: 0; }
.cart-item-title { font-size: 14px; font-weight: 600; }
.cart-item-source, .source-facts { font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; }
.source-facts a, .ai-suggestion a, .legacy-result a { overflow-wrap: anywhere; }
.cart-item-actions { display: flex; align-items: center; flex-shrink: 0; }
.legacy-result {
  margin-top: var(--space-xs);
  padding: var(--space-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}
.legacy-result p { margin: 5px 0; line-height: 1.5; }
.ai-mini-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 3px; margin-top: 5px; }
.legacy-result { background: var(--color-bg-secondary); color: var(--color-text-secondary); }
.cart-actions { margin-top: 20px; display: flex; gap: 8px; }
</style>
