<template>
  <div class="home">
    <!-- Hero -->
    <div class="hero">
      <h1 class="hero-title">ResearchMate</h1>
      <p class="hero-subtitle">AI 辅助论文筛选工具 — 爬摘要、AI 分析、快速筛选</p>
    </div>

    <!-- Nav Cards -->
    <div class="nav-grid">
      <NavCard
        icon="Document"
        title="论文中心"
        description="管理期刊源，爬取论文摘要，AI 智能分析，快速筛选值得精读的论文"
        to="/papers"
      />
      <NavCard
        icon="Setting"
        title="全局设置"
        description="配置 AI 接口、爬取参数、主题外观，打造适合你的使用体验"
        to="/settings"
      />
      <NavCard
        icon="InfoFilled"
        title="关于"
        description="了解 ResearchMate 的设计理念、技术栈和使用方法"
        to="/about"
      />
    </div>

    <!-- Stats Bar -->
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-value">{{ stats.paperCount }}</span>
        <span class="stat-label">已收录论文</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-value">{{ stats.cartCount }}</span>
        <span class="stat-label">购物车</span>
      </div>
      <div class="stat-divider" />
      <div class="stat-item">
        <span class="stat-value">{{ stats.lastUpdate }}</span>
        <span class="stat-label">上次更新</span>
      </div>
    </div>

    <!-- Quick links -->
    <div class="quick-links">
      <a href="https://github.com/promise-157/ResearchMate/blob/main/docs/QUICKSTART.md" target="_blank">
        <el-button type="primary" link size="small">
          <el-icon><Lightning /></el-icon> 快速上手
        </el-button>
      </a>
      <a href="https://github.com/promise-157/ResearchMate/blob/main/docs/MANUAL.md" target="_blank">
        <el-button type="primary" link size="small">
          <el-icon><Document /></el-icon> 使用手册
        </el-button>
      </a>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import NavCard from '@/components/NavCard.vue'
import { useCartStore } from '@/stores/cart'
import { fetchStats } from '@/api'

const cartStore = useCartStore()

const stats = ref({
  paperCount: '--',
  cartCount: 0,
  lastUpdate: '暂无',
})

onMounted(async () => {
  try {
    const res = await fetchStats()
    const data = res.data || res
    stats.value = {
      paperCount: data.paper_count ?? '--',
      cartCount: data.cart_count ?? cartStore.count,
      lastUpdate: data.last_update || '暂无',
    }
  } catch {
    stats.value.cartCount = cartStore.count
  }
})
</script>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: var(--space-2xl);
}

/* Hero */
.hero {
  text-align: center;
  margin-bottom: var(--space-2xl);
}

.hero-title {
  font-size: 36px;
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-sm);
  letter-spacing: -0.5px;
}

.hero-subtitle {
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}

/* Nav Grid */
.nav-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-lg);
  width: 100%;
  max-width: 900px;
  margin-bottom: var(--space-2xl);
}

@media (max-width: 700px) {
  .nav-grid {
    grid-template-columns: 1fr;
    max-width: 360px;
  }
}

/* Stats Bar */
.stats-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-xl);
  padding: var(--space-lg) var(--space-2xl);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 900px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
}

.stat-value {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-primary);
}

.stat-label {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.stat-divider {
  width: 1px;
  height: 36px;
  background: var(--color-border);
}

.quick-links {
  display: flex;
  gap: var(--space-md);
  margin-top: var(--space-lg);
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border-light);
}
</style>
