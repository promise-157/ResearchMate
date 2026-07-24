<template>
  <div class="docs-page">
    <h1 class="page-title">文档</h1>

    <!-- Tab switcher -->
    <div class="docs-tabs">
      <el-radio-group v-model="activeTab" size="large">
        <el-radio-button value="QUICKSTART">快速上手</el-radio-button>
        <el-radio-button value="MANUAL">使用手册</el-radio-button>
      </el-radio-group>
    </div>

    <!-- Content -->
    <div v-if="loading" class="loading-state flex-center">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <div v-else-if="error" class="error-state">
      <el-alert :title="error" type="error" show-icon :closable="false" />
    </div>

    <div v-else class="docs-content card" v-html="renderedContent"></div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { marked } from 'marked'
import axios from 'axios'

const activeTab = ref('QUICKSTART')
const rawContent = ref('')
const loading = ref(false)
const error = ref('')

const renderedContent = computed(() => {
  if (!rawContent.value) return ''
  return marked(rawContent.value)
})

async function loadDoc(name) {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/docs/${name}`)
    rawContent.value = res.data.content || ''
  } catch {
    error.value = '加载文档失败，请确认后端已启动'
  } finally {
    loading.value = false
  }
}

// 初始化加载
loadDoc(activeTab.value)

// 切换 tab 时重新加载
watch(activeTab, (val) => loadDoc(val))
</script>

<style scoped>
.docs-page {
  max-width: 860px;
  margin: 0 auto;
  padding-top: var(--space-lg);
}

.docs-tabs {
  margin-bottom: var(--space-lg);
}

.docs-content {
  padding: var(--space-xl) var(--space-2xl);
  line-height: var(--line-height-relaxed);
  font-size: var(--font-size-base);
}

/* Override markdown-rendered styles to use theme variables */
.docs-content :deep(h1) {
  font-size: var(--font-size-2xl);
  margin: var(--space-lg) 0 var(--space-md);
  border-bottom: 1px solid var(--color-border);
  padding-bottom: var(--space-sm);
}

.docs-content :deep(h2) {
  font-size: var(--font-size-xl);
  margin: var(--space-lg) 0 var(--space-sm);
  border-bottom: 1px solid var(--color-border-light);
  padding-bottom: var(--space-xs);
}

.docs-content :deep(h3) {
  font-size: var(--font-size-lg);
  margin: var(--space-md) 0 var(--space-sm);
}

.docs-content :deep(p) {
  margin: var(--space-sm) 0;
  color: var(--color-text-secondary);
}

.docs-content :deep(ul), .docs-content :deep(ol) {
  padding-left: var(--space-lg);
  margin: var(--space-sm) 0;
}

.docs-content :deep(li) {
  margin: 4px 0;
}

.docs-content :deep(code) {
  background: var(--color-bg);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  font-family: monospace;
}

.docs-content :deep(pre) {
  background: var(--color-bg);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  overflow-x: auto;
  border: 1px solid var(--color-border-light);
  margin: var(--space-md) 0;
}

.docs-content :deep(pre code) {
  background: none;
  padding: 0;
}

.docs-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: var(--space-md) 0;
}

.docs-content :deep(th), .docs-content :deep(td) {
  border: 1px solid var(--color-border);
  padding: 8px 12px;
  text-align: left;
  font-size: var(--font-size-sm);
}

.docs-content :deep(th) {
  background: var(--color-bg);
  font-weight: var(--font-weight-semibold);
}

.docs-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border-light);
  margin: var(--space-lg) 0;
}

.docs-content :deep(blockquote) {
  border-left: 3px solid var(--color-primary);
  padding-left: var(--space-md);
  color: var(--color-text-secondary);
  margin: var(--space-md) 0;
}

.docs-content :deep(a) {
  color: var(--color-primary);
}

.loading-state, .error-state {
  padding: var(--space-2xl);
}
</style>
