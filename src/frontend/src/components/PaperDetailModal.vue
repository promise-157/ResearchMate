<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="paper?.title || '论文详情'"
    width="680px"
    top="5vh"
  >
    <template v-if="paper">
      <!-- Meta -->
      <div class="detail-meta">
        <p v-if="paper.authors?.length" class="detail-authors">
          {{ paper.authors.join(', ') }}
        </p>
        <p class="detail-venue">
          {{ paper.journal_name }} · {{ paper.publish_year }}
          <span v-if="paper.arxiv_id" class="detail-arxiv">
            · arXiv:{{ paper.arxiv_id }}
          </span>
        </p>
      </div>

      <!-- Abstract -->
      <div class="detail-section">
        <h4>原始摘要</h4>
        <p class="detail-abstract">{{ paper.abstract || '暂无摘要' }}</p>
      </div>

      <el-divider />

      <!-- AI Analysis -->
      <div class="detail-section">
        <h4>🤖 AI 分析</h4>

        <div class="ai-detail-row">
          <span class="ai-detail-label">开源代码</span>
          <span v-if="paper.has_code" class="tag-has-code">
            🔗 <a :href="paper.code_url" target="_blank">{{ paper.code_url }}</a>
          </span>
          <span v-else class="tag-no-code">摘要未提及代码</span>
        </div>

        <div class="ai-detail-row">
          <span class="ai-detail-label">创新点</span>
          <p class="ai-detail-text">{{ paper.ai_innovation }}</p>
        </div>

        <div class="ai-detail-row">
          <span class="ai-detail-label">技术栈</span>
          <div class="tech-tags-list">
            <el-tag v-for="tag in paper.ai_technologies" :key="tag" size="small">
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="detail-footer">
        <el-button @click="copyCitation">复制引用</el-button>
        <el-button
          :type="paper?.in_cart ? 'primary' : 'default'"
          @click="$emit('toggle-cart', paper)"
        >
          {{ paper?.in_cart ? '已保存到购物车' : '加入购物车' }}
        </el-button>
        <a v-if="paper?.paper_url" :href="paper.paper_url" target="_blank">
          <el-button type="primary">访问原文</el-button>
        </a>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ElMessage } from 'element-plus'

defineProps({
  paper: { type: Object, default: null },
  visible: Boolean,
})

defineEmits(['update:visible', 'toggle-cart'])

function copyCitation() {
  ElMessage.info('复制引用功能将在后端实现后接入')
}
</script>

<style scoped>
.detail-meta {
  margin-bottom: var(--space-lg);
}

.detail-authors {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.detail-venue {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.detail-arxiv {
  font-family: monospace;
}

.detail-section {
  margin-bottom: var(--space-md);
}

.detail-section h4 {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-sm);
}

.detail-abstract {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  white-space: pre-wrap;
}

.ai-detail-row {
  margin-bottom: var(--space-md);
}

.ai-detail-label {
  display: block;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: 4px;
}

.ai-detail-text {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  margin: 0;
}

.tech-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-footer {
  display: flex;
  gap: var(--space-sm);
  justify-content: flex-end;
}
</style>
