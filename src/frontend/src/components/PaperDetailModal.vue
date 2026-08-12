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
        <p v-if="parseList(paper.authors).length" class="detail-authors">
          {{ parseList(paper.authors).join(', ') }}
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

      <!-- Read-only legacy AI block. New audited runs live in the cart drawer. -->
      <div v-if="paper.ai_analyzed" class="detail-section">
        <h4>🤖 旧兼容 AI 结果（只读）</h4>
        <p class="text-secondary">新分析不会更新这些旧字段；统一审计运行请在购物车中查看。</p>

        <div class="ai-detail-row">
          <span class="ai-detail-label">来源代码事实</span>
          <span v-if="paper.has_code" class="tag-has-code">
            🔗 <a :href="paper.code_url" target="_blank">{{ paper.code_url }}</a>
          </span>
          <span v-else class="tag-no-code">来源没有代码记录</span>
        </div>

        <div class="ai-detail-row">
          <span class="ai-detail-label">旧创新分析</span>
          <p class="ai-detail-text">{{ paper.ai_innovation }}</p>
        </div>

        <div class="ai-detail-row">
          <span class="ai-detail-label">旧技术标签</span>
          <div class="tech-tags-list">
            <el-tag v-for="tag in parseList(paper.ai_technologies)" :key="tag" size="small">
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </div>
      <div v-else class="detail-section text-secondary">统一审计分析请在购物车中运行和查看</div>
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

const props = defineProps({
  paper: { type: Object, default: null },
  visible: Boolean,
})

defineEmits(['update:visible', 'toggle-cart'])

function parseList(value) {
  if (Array.isArray(value)) return value
  if (!value) return []
  try { return JSON.parse(value) } catch { return [] }
}

async function copyCitation() {
  const paper = props.paper
  if (!paper) return
  const authors = parseList(paper.authors).join(', ')
  const year = paper.publish_year ? ` (${paper.publish_year})` : ''
  const source = paper.journal_name ? `. ${paper.journal_name}` : ''
  const url = paper.paper_url ? `. ${paper.paper_url}` : ''
  await navigator.clipboard.writeText(`${authors}${year}. ${paper.title}${source}${url}`)
  ElMessage.success('引用信息已复制')
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
