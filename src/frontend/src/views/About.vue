<template>
  <div class="about">
    <h1 class="page-title">关于 ResearchMate</h1>

    <div class="about-card card">
      <p class="version">v0.1.0</p>
      <p class="desc">
        ResearchMate 是一个本地优先的论文收件箱。它从明确支持的公开元数据来源
        同步论文，先在本地完成筛选和收藏，再按你的明确选择调用 AI 分析。
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
          <el-tag type="danger">AI / LLM</el-tag>
        </div>
      </div>

      <div class="links">
        <a href="https://github.com/promise-157/ResearchMate" target="_blank">
          <el-button type="primary" link>
            <el-icon><Link /></el-icon> GitHub
          </el-button>
        </a>
        <router-link to="/docs">
          <el-button type="primary" link>
            <el-icon><Document /></el-icon> 使用文档
          </el-button>
        </router-link>
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
