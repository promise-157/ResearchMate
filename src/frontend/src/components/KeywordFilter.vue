<template>
  <div v-if="keywords.length > 0" class="keyword-filter card">
    <div class="kf-header">
      <span class="kf-title">关键词筛选</span>
      <div class="kf-controls">
        <el-radio-group v-model="mode" size="small" @change="$emit('mode-change', mode)">
          <el-radio-button value="or">OR (任一)</el-radio-button>
          <el-radio-button value="and">AND (全部)</el-radio-button>
        </el-radio-group>
        <el-button v-if="selected.size > 0" size="small" text type="danger" @click="clearAll">
          清除 ({{ selected.size }})
        </el-button>
      </div>
    </div>

    <div class="kf-tags">
      <span
        v-for="kw in keywords"
        :key="kw.keyword"
        class="kf-tag"
        :class="{ active: selected.has(kw.keyword) }"
        @click="toggle(kw.keyword)"
      >
        {{ kw.keyword }}
        <span class="kf-count">{{ kw.count }}</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  keywords: { type: Array, default: () => [] },
})

const emit = defineEmits(['filter-change', 'mode-change'])

const selected = ref(new Set())
const mode = ref('or')

function toggle(kw) {
  if (selected.value.has(kw)) {
    selected.value.delete(kw)
  } else {
    selected.value.add(kw)
  }
  selected.value = new Set(selected.value) // trigger reactivity
  emitFilter()
}

function clearAll() {
  selected.value = new Set()
  emitFilter()
}

function emitFilter() {
  emit('filter-change', {
    keywords: [...selected.value],
    mode: mode.value,
  })
}
</script>

<style scoped>
.keyword-filter {
  padding: var(--space-md) var(--space-lg);
  margin-bottom: var(--space-md);
}

.kf-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-sm);
}

.kf-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}

.kf-controls {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.kf-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.kf-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  font-size: var(--font-size-xs);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  cursor: pointer;
  user-select: none;
  transition: all var(--transition-fast);
  color: var(--color-text-secondary);
}

.kf-tag:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
}

.kf-tag.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.kf-tag.active .kf-count {
  color: rgba(255, 255, 255, 0.7);
}

.kf-count {
  font-size: 10px;
  color: var(--color-text-disabled);
}
</style>
