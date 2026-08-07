<template>
  <div class="paper-card card">
    <!-- Top row: Star + Title + Cart -->
    <div class="paper-top">
      <el-button
        :type="paper.in_cart ? 'primary' : 'default'"
        circle
        size="small"
        @click="$emit('toggle-cart', paper)"
        title="加入购物车"
      >
        <el-icon><StarFilled v-if="paper.in_cart" /><Star v-else /></el-icon>
      </el-button>
      <h4 class="paper-title">{{ paper.title }}</h4>
      <el-button
        :type="paper.in_cart ? 'primary' : 'default'"
        size="small"
        plain
        @click="$emit('toggle-cart', paper)"
      >
        <el-icon><ShoppingCart /></el-icon>
        {{ paper.in_cart ? '已保存' : '保存' }}
      </el-button>
    </div>

    <!-- Meta row -->
    <div class="paper-meta">
      <span class="paper-authors">{{ formatAuthors(paper.authors) }}</span>
      <span class="meta-sep">·</span>
      <span class="paper-venue">{{ paper.journal_name }} {{ paper.publish_year }}</span>
      <span v-if="paper.arxiv_id" class="meta-sep">·</span>
      <span v-if="paper.arxiv_id" class="paper-arxiv">arXiv:{{ paper.arxiv_id }}</span>
    </div>

    <!-- AI Analysis block -->
    <div v-if="paper.ai_analyzed" class="ai-analysis" :class="{ expanded: aiExpanded }">
      <div class="ai-header" @click="aiExpanded = !aiExpanded">
        <span class="ai-label">🤖 AI 分析</span>
        <el-button text size="small">
          {{ aiExpanded ? '收起' : '展开' }}
        </el-button>
      </div>

      <div class="ai-body">
        <!-- Code -->
        <div class="ai-row">
          <span v-if="paper.has_code" class="tag-has-code">
            🔗 有开源代码
            <a :href="paper.code_url" target="_blank" class="code-link" @click.stop>
              {{ formatCodeUrl(paper.code_url) }}
            </a>
          </span>
          <span v-else class="tag-no-code">🔗 摘要未提及代码</span>
        </div>

        <!-- Innovation -->
        <div class="ai-row">
          <span class="ai-field">💡 创新点：</span>
          <span class="ai-text" :class="{ clamped: !aiExpanded }">
            {{ paper.ai_innovation }}
          </span>
        </div>

        <!-- Tech tags -->
        <div class="ai-row tech-row">
          <span class="ai-field">🛠 技术：</span>
          <template v-for="tag in displayedTags" :key="tag">
            <el-tag size="small" type="info">{{ tag }}</el-tag>
          </template>
          <span
            v-if="totalTagCount > maxTags && !aiExpanded"
            class="more-tags"
          >
            +{{ totalTagCount - maxTags }} 更多
          </span>
        </div>
      </div>
    </div>
    <div v-else class="ai-analysis">
      <span class="tag-no-code">尚未进行 AI 分析</span>
    </div>

    <!-- Actions -->
    <div class="paper-actions">
      <el-button text size="small" @click="$emit('view-detail', paper)">
        查看摘要
      </el-button>
      <a v-if="paper.paper_url" :href="paper.paper_url" target="_blank">
        <el-button text size="small" type="primary">
          访问原文 →
        </el-button>
      </a>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  paper: { type: Object, required: true },
})

defineEmits(['toggle-cart', 'view-detail'])

const aiExpanded = ref(false)
const maxTags = 3

function parseTags(val) {
  if (!val) return []
  if (Array.isArray(val)) return val
  try { return JSON.parse(val) } catch { return [] }
}

const totalTagCount = computed(() => parseTags(props.paper.ai_technologies).length)

const displayedTags = computed(() => {
  const tags = parseTags(props.paper.ai_technologies)
  return aiExpanded.value ? tags : tags.slice(0, maxTags)
})

function formatAuthors(authors) {
  const arr = parseTags(authors)  // same JSON-or-array logic
  if (!arr || arr.length === 0) return '未知作者'
  if (arr.length === 1) return arr[0]
  return arr[0] + ' et al.'
}

function formatCodeUrl(url) {
  if (!url) return ''
  return url.replace(/^https?:\/\//, '').replace(/\/$/, '').slice(0, 30) + '...'
}
</script>

<style scoped>
.paper-card {
  padding: var(--space-lg);
  margin-bottom: var(--space-md);
}

/* Top row */
.paper-top {
  display: flex;
  align-items: flex-start;
  gap: var(--space-sm);
  margin-bottom: var(--space-sm);
}

.paper-title {
  flex: 1;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-tight);
}

/* Meta row */
.paper-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-md);
  padding-left: 36px; /* align with title after star icon */
}

.paper-authors {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.meta-sep {
  color: var(--color-border-dark);
}

.paper-arxiv {
  font-family: monospace;
  font-size: var(--font-size-xs);
}

/* AI Analysis */
.ai-analysis {
  margin-left: 36px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: var(--space-sm);
}

.ai-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: var(--color-bg);
  cursor: pointer;
  user-select: none;
}

.ai-label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-secondary);
}

.ai-body {
  padding: 10px 12px;
}

.ai-row {
  margin-bottom: 6px;
}

.ai-row:last-child {
  margin-bottom: 0;
}

.ai-field {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}

.ai-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}

.ai-text.clamped {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tech-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.more-tags {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  cursor: pointer;
}

.code-link {
  font-size: var(--font-size-xs);
  color: var(--color-code);
  margin-left: 4px;
}

/* Actions */
.paper-actions {
  display: flex;
  gap: var(--space-sm);
  padding-left: 36px;
}
</style>
