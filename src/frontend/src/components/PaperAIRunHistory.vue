<template>
  <section class="run-history">
    <h3>{{ title }}</h3>
    <p v-if="!runs.length" class="empty-history">尚无统一审计运行。</p>
    <article v-for="run in runs" :key="run.id" class="run-card">
      <div class="run-head">
        <el-tag :type="statusTagType(run.status)" size="small">{{ statusLabel(run.status) }}</el-tag>
        <strong>运行 #{{ run.id }}</strong>
        <span>{{ formatTime(run.created_at) }}</span>
      </div>
      <p class="run-meta">
        范围：{{ scopeLabel(run.input_scope) }}
        · 论文 ID：{{ paperIds(run).join('、') || '—' }}
        · 提示词 {{ run.prompt_version || '—' }}
      </p>
      <p class="run-meta">
        配置：{{ run.provider || '—' }}/{{ run.model || '—' }}
        · 服务商返回：{{ run.provider_model || '—' }}
        · token {{ run.input_tokens ?? '—' }}/{{ run.output_tokens ?? '—' }}
        · 耗时 {{ run.duration_ms ?? '—' }} ms
      </p>
      <p v-if="run.request_id" class="run-meta request-id">请求 ID：{{ run.request_id }}</p>
      <p v-if="run.error_message" class="run-error">失败：{{ run.error_message }}</p>

      <div v-if="run.result && run.run_kind === 'paper_analysis'" class="ai-result">
        <strong>AI 建议（不会改写来源事实）</strong>
        <p>代码判断：{{ run.result.has_code ? '可能有代码' : '未发现代码' }}</p>
        <p v-if="run.result.code_url">
          建议代码链接：
          <a :href="run.result.code_url" target="_blank" rel="noopener noreferrer">{{ run.result.code_url }}</a>
        </p>
        <p v-if="run.result.innovation">创新建议：{{ run.result.innovation }}</p>
        <div v-if="parseTags(run.result.technologies).length" class="ai-mini-tags">
          技术建议：
          <el-tag
            v-for="technology in parseTags(run.result.technologies)"
            :key="technology"
            size="small"
            type="info"
          >{{ technology }}</el-tag>
        </div>
      </div>

      <div v-if="run.result && run.run_kind === 'workspace_review'" class="ai-result">
        <strong>结构化综述（不会改写论文事实）</strong>
        <p><b>热门方向：</b>{{ run.result.hot_topics }}</p>
        <p><b>技术趋势：</b>{{ run.result.tech_trends }}</p>
        <div v-if="run.result.recommendations?.length">
          <b>推荐关注：</b>
          <ul>
            <li v-for="entry in run.result.recommendations" :key="entry.paper_id">
              #{{ entry.paper_id }} {{ paperTitles[entry.paper_id] || '' }}：{{ entry.reason }}
            </li>
          </ul>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
defineProps({
  runs: { type: Array, default: () => [] },
  title: { type: String, default: '论文 AI 运行历史' },
  paperTitles: { type: Object, default: () => ({}) },
})

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

function paperIds(run) {
  return (run.paper_ids || [run.paper_id]).filter((id) => id != null)
}

function statusLabel(value) {
  return { running: '运行中', succeeded: '成功', failed: '失败' }[value] || value
}

function statusTagType(value) {
  return { running: 'warning', succeeded: 'success', failed: 'danger' }[value] || 'info'
}

function scopeLabel(fields = []) {
  const labels = {
    title: '标题',
    abstract: '摘要',
    'title:300': '标题（每篇最多 300 字符）',
    'abstract:2000': '摘要（每篇最多 2,000 字符）',
  }
  return fields.map((field) => labels[field] || field).join('、') || '—'
}

function formatTime(value) {
  return value ? String(value).slice(0, 19) : '—'
}
</script>

<style scoped>
.run-history { margin-top: var(--space-md); }
.run-history h3 { margin: 0 0 var(--space-xs); font-size: var(--font-size-sm); }
.empty-history { margin: 0; color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.run-card {
  margin-top: var(--space-xs);
  padding: var(--space-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}
.run-head { display: flex; align-items: center; gap: var(--space-xs); color: var(--color-text-secondary); }
.run-meta { margin: 5px 0 0; color: var(--color-text-secondary); line-height: 1.5; overflow-wrap: anywhere; }
.request-id { font-family: monospace; }
.run-error { color: var(--el-color-danger); white-space: pre-wrap; overflow-wrap: anywhere; }
.ai-result { margin-top: var(--space-sm); padding: var(--space-sm); background: var(--color-primary-bg); border-radius: var(--radius-sm); }
.ai-result p { margin: 5px 0; line-height: 1.5; }
.ai-result a { overflow-wrap: anywhere; }
.ai-result ul { margin: 5px 0 0; padding-left: 20px; }
.ai-mini-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 3px; margin-top: 5px; }
</style>
