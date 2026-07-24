<template>
  <div class="crawl-control card">
    <div class="control-header flex-between">
      <h3 class="section-title" style="margin-bottom:0">爬取控制</h3>
      <el-button size="small" type="primary" plain @click="$emit('add-source')">
        + 添加期刊源
      </el-button>
    </div>

    <!-- source list -->
    <div v-if="sources.length === 0" class="empty-state" style="padding:var(--space-lg) 0">
      <p style="color:var(--color-text-secondary)">还没有添加期刊源</p>
    </div>
    <div v-else class="source-list">
      <div
        v-for="src in sources"
        :key="src.id"
        class="source-row"
        :class="{ selected: selectedIds.includes(src.id) }"
        @click="toggleSource(src.id)"
      >
        <el-checkbox
          :model-value="selectedIds.includes(src.id)"
          @click.stop="toggleSource(src.id)"
        />
        <div class="source-info">
          <div class="source-label">{{ src.label || src.url }}</div>
          <div class="source-meta">
            <span v-if="src.last_crawled_at">上次: {{ src.last_crawled_at }}</span>
            <span v-else class="never-crawled">从未爬取</span>
            <span v-if="src.last_paper_count !== null" class="source-count">
              · 上次 {{ src.last_paper_count }} 篇
            </span>
          </div>
        </div>
        <el-button
          text
          circle
          size="small"
          type="danger"
          @click.stop="$emit('delete-source', src.id)"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- mode + trigger -->
    <div class="control-footer">
      <el-radio-group v-model="mode" size="small">
        <el-radio-button value="new">仅新论文</el-radio-button>
        <el-radio-button value="all">全部重新爬取</el-radio-button>
      </el-radio-group>
      <el-button
        type="primary"
        :disabled="selectedIds.length === 0"
        @click="$emit('crawl-start', selectedIds, mode)"
      >
        开始爬取已选的 {{ selectedIds.length }} 个源
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  sources: { type: Array, default: () => [] },
})

defineEmits(['add-source', 'delete-source', 'crawl-start'])

const selectedIds = ref(props.sources.map((s) => s.id))
const mode = ref('new')

function toggleSource(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}
</script>

<style scoped>
.crawl-control {
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
}

.control-header {
  margin-bottom: var(--space-md);
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.source-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 8px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.source-row:hover {
  background: var(--color-primary-bg);
}

.source-row.selected {
  background: var(--color-primary-bg);
}

.source-info {
  flex: 1;
  min-width: 0;
}

.source-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-meta {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.never-crawled {
  color: var(--color-warning);
}

.source-count {
  color: var(--color-text-secondary);
}

.control-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--space-md);
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border-light);
}
</style>
