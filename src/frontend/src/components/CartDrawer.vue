<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="购物车"
    direction="rtl"
    size="420px"
  >
    <div v-if="cartStore.items.length === 0" class="cart-empty">
      <p>购物车为空</p>
      <p class="hint">浏览论文时点击 🛒 即可加入购物车</p>
    </div>
    <div v-else class="cart-list">
      <!-- Batch actions -->
      <div class="cart-toolbar">
        <el-button size="small" :loading="analyzing" :disabled="cartStore.items.length > 20" @click="analyzeAll">
          🤖 批量AI分析 ({{ cartStore.items.length }}篇)
        </el-button>
        <span v-if="cartStore.items.length > 20" class="cart-limit">单次上限 20 篇，请先缩小清单</span>
      </div>

      <div v-for="item in cartStore.items" :key="item.id" class="cart-item">
        <div class="cart-item-info">
          <div class="cart-item-title">{{ item.title }}</div>
          <div class="cart-item-source">{{ item.journal_name }}</div>
          <!-- Inline AI result -->
          <div v-if="item.cart_ai_analyzed || item.ai_analyzed" class="cart-ai-result">
            <div v-if="item.ai_innovation" class="ai-mini">💡 {{ item.ai_innovation?.slice(0, 80) }}...</div>
            <div v-if="parseTags(item.ai_technologies).length" class="ai-mini-tags">
              <el-tag v-for="t in parseTags(item.ai_technologies).slice(0, 3)" :key="t" size="small" type="info">{{ t }}</el-tag>
            </div>
          </div>
        </div>
        <div class="cart-item-actions">
          <el-button size="small" text type="primary" :loading="analyzing" @click="analyzeOne(item)">
            分析
          </el-button>
          <el-button size="small" text type="danger" @click="removeOne(item.id)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>

      <div class="cart-actions">
        <el-button @click="copyTitles">复制标题列表</el-button>
        <el-button type="primary" @click="exportCSV">导出 CSV</el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useCartStore } from '@/stores/cart'
import { analyzeCartPapers, analyzeAllCart, exportCart } from '@/api'

defineProps({ visible: Boolean })
defineEmits(['update:visible'])

const cartStore = useCartStore()
const analyzing = ref(false)
function parseTags(val) {
  if (!val) return []
  if (Array.isArray(val)) return val
  try { return JSON.parse(val) } catch { return [] }
}

async function analyzeOne(paper) {
  analyzing.value = true
  try {
    const result = await analyzeCartPapers([paper.id])
    if (!result.ok) throw new Error(result.message || 'AI 未返回有效分析')
    await cartStore.refreshFromBackend()
    ElMessage.success('分析完成')
  } catch (error) { ElMessage.error(error.message || '分析失败') }
  finally { analyzing.value = false }
}

async function analyzeAll() {
  analyzing.value = true
  try {
    const result = await analyzeAllCart()
    if (!result.ok) throw new Error(result.message || 'AI 未返回有效分析')
    await cartStore.refreshFromBackend()
    ElMessage.success('批量分析完成')
  } catch (error) { ElMessage.error(error.message || '分析失败') }
  finally { analyzing.value = false }
}

function copyTitles() {
  const titles = cartStore.items.map((p) => p.title).join('\n')
  navigator.clipboard.writeText(titles)
  ElMessage.success('已复制到剪贴板')
}

async function removeOne(id) {
  try {
    await cartStore.removeFromCart(id)
  } catch { ElMessage.error('移除失败') }
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
  } catch { ElMessage.error('导出失败') }
}
</script>

<style scoped>
.cart-empty {
  text-align: center;
  padding: 40px 0;
  color: #999;
}
.cart-empty .hint { font-size: 13px; margin-top: 8px; }

.cart-toolbar {
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--color-border);
}
.cart-limit { margin-left: 8px; color: var(--color-warning); font-size: var(--font-size-xs); }

.cart-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border-light);
  gap: var(--space-sm);
}
.cart-item-info { flex: 1; min-width: 0; }
.cart-item-title { font-size: 14px; font-weight: 500; }
.cart-item-source { font-size: 12px; color: #999; margin-top: 4px; }
.cart-item-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; }

.cart-ai-result {
  margin-top: 8px;
  padding: 6px 8px;
  background: var(--color-primary-bg);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}
.ai-mini { color: var(--color-text-secondary); line-height: 1.5; }
.ai-mini-tags { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px; }

.cart-actions {
  margin-top: 20px;
  display: flex;
  gap: 8px;
}
</style>
