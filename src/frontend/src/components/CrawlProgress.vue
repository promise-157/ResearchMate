<template>
  <div v-if="status !== 'idle'" class="crawl-progress" :class="`status-${status}`">
    <div class="progress-content">
      <el-icon v-if="status === 'crawling' || status === 'analyzing'" class="is-loading">
        <Loading />
      </el-icon>
      <el-icon v-else-if="status === 'done'"><CircleCheckFilled /></el-icon>
      <el-icon v-else-if="status === 'error'"><CircleCloseFilled /></el-icon>
      <span class="progress-text">{{ statusText }}</span>
      <el-progress
        v-if="status === 'crawling' || status === 'analyzing'"
        :percentage="percentage"
        :stroke-width="4"
        :show-text="false"
        style="width: 200px; margin-left: 12px;"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'idle', // idle | crawling | analyzing | done | error
    validator: (v) => ['idle', 'crawling', 'analyzing', 'done', 'error'].includes(v),
  },
  percentage: { type: Number, default: 0 },
  message: { type: String, default: '' },
})

const statusText = computed(() => {
  const map = {
    crawling: '正在爬取论文摘要...',
    analyzing: 'AI 正在分析...',
    done: props.message || '爬取分析完成',
    error: props.message || '爬取出错',
  }
  return map[props.status] || ''
})
</script>

<style scoped>
.crawl-progress {
  padding: 10px 16px;
  border-radius: var(--radius-md);
  margin-bottom: var(--space-md);
  font-size: var(--font-size-sm);
}

.status-crawling,
.status-analyzing {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.status-done {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.status-error {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.progress-content {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
