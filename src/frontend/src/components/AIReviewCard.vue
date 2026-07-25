<template>
  <div v-if="review" class="ai-review card">
    <div class="review-header flex-between" @click="expanded = !expanded" style="cursor:pointer">
      <div class="review-title">
        <el-icon color="var(--color-primary)"><DataAnalysis /></el-icon>
        <span>AI 本批点评</span>
      </div>
      <el-button text size="small">
        {{ expanded ? '收起' : '展开' }}
        <el-icon><component :is="expanded ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
      </el-button>
    </div>

    <div v-if="expanded" class="review-body">
      <!-- stats row -->
      <div class="review-stats">
        <span>共 <strong>{{ review.total_papers || '?' }}</strong> 篇论文</span>
        <span v-if="review.generated_at" class="review-time">生成于 {{ review.generated_at }}</span>
      </div>

      <!-- hot topics -->
      <div class="review-section">
        <div class="review-label">🔥 热门方向</div>
        <p>{{ review.hot_topics }}</p>
      </div>

      <!-- recommendations -->
      <div class="review-section">
        <div class="review-label">⭐ 推荐关注</div>
        <ul class="rec-list">
          <li v-for="(rec, i) in review.recommendations" :key="i">
            <span class="rec-title">{{ rec.title }}</span>
            <span class="rec-reason">— {{ rec.reason }}</span>
          </li>
        </ul>
      </div>

      <!-- tech trends -->
      <div class="review-section">
        <div class="review-label">💡 技术趋势</div>
        <p>{{ review.tech_trends }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  review: { type: Object, default: null },
})

const expanded = ref(true)
</script>

<style scoped>
.ai-review {
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
  border-left: 4px solid var(--color-primary);
}

.review-title {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
}

.review-body {
  margin-top: var(--space-md);
}

.review-stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-sm);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-md);
  border-bottom: 1px solid var(--color-border-light);
}

.has-code-count { color: var(--color-code); }
.review-time { color: var(--color-text-disabled); font-size: var(--font-size-xs); }

.review-section {
  margin-bottom: var(--space-md);
}

.review-section:last-child {
  margin-bottom: 0;
}

.review-label {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-xs);
}

.review-section p {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  margin: 0;
}

.rec-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.rec-list li {
  font-size: var(--font-size-sm);
  padding: 4px 0;
}

.rec-title {
  font-weight: var(--font-weight-medium);
}

.rec-reason {
  color: var(--color-text-secondary);
}
</style>
