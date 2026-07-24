<template>
  <div class="about">
    <h1 class="page-title">关于 ResearchMate</h1>

    <div class="about-card card">
      <p class="version">v0.1.0</p>
      <p class="desc">
        ResearchMate 是一个 AI 辅助论文筛选工具。导入你感兴趣的期刊网址，
        自动爬取论文摘要，通过 AI 分析每篇论文的创新点和技术栈，
        帮你快速找到值得精读的论文。
      </p>

      <div class="tech-section">
        <h3>技术栈</h3>
        <div class="tech-tags">
          <el-tag type="primary">Python 3.11</el-tag>
          <el-tag type="primary">FastAPI</el-tag>
          <el-tag type="primary">Vue 3</el-tag>
          <el-tag type="primary">Vite</el-tag>
          <el-tag type="success">Element Plus</el-tag>
          <el-tag type="warning">SQLite</el-tag>
          <el-tag>ECharts</el-tag>
          <el-tag type="danger">AI / LLM</el-tag>
        </div>
      </div>

      <div class="links">
        <a href="https://github.com/promise-157/ResearchMate" target="_blank">
          <el-button type="primary" link>
            <el-icon><Link /></el-icon> GitHub
          </el-button>
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>

<style scoped>
.about {
  max-width: 640px;
  margin: 0 auto;
  padding-top: var(--space-xl);
}

.about-card {
  padding: var(--space-2xl);
}

.version {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-md);
}

.desc {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  line-height: var(--line-height-relaxed);
  margin-bottom: var(--space-xl);
}

.tech-section h3 {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--space-md);
}

.tech-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  margin-bottom: var(--space-xl);
}

.links {
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border);
}
</style>
