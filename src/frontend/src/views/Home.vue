<template>
  <div class="home">
    <!-- Hero -->
    <div class="hero">
      <h1 class="hero-title">ResearchMate</h1>
      <p class="hero-subtitle">本地资料工作台 — 导入、理解、整理、关联与按需 AI 分析</p>
    </div>

    <!-- Nav Cards -->
    <div class="nav-grid">
      <NavCard
        icon="Files"
        title="资料中心"
        description="导入文字资料，自动去重和类型建议，并在工作区内检索整理"
        to="/materials"
      />
      <NavCard
        icon="Document"
        title="论文中心"
        description="同步公开论文元数据，在本地筛选并保存值得精读的论文"
        to="/papers"
      />
      <NavCard
        icon="Aim"
        title="行动专题"
        description="把明确选择的资料组织为证据清单，维护自己的结论和下一步"
        to="/actions"
      />
      <NavCard
        icon="Notebook"
        title="使用文档"
        description="快速上手指南 + 完整使用手册，从安装到高级配置覆盖所有功能"
        to="/docs"
      />
      <NavCard
        icon="Setting"
        title="全局设置"
        description="配置 AI 接口、同步参数与主题；外部调用始终由你主动发起"
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
        <span class="stat-value">{{ stats.materialCount }}</span>
        <span class="stat-label">通用资料</span>
      </div>
      <div class="stat-divider" />
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
  materialCount: '--',
  cartCount: 0,
  lastUpdate: '暂无',
})

onMounted(async () => {
  try {
    const res = await fetchStats()
    const data = res.data || res
    stats.value = {
      paperCount: data.paper_count ?? '--',
      materialCount: data.material_count ?? '--',
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
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-lg);
  width: 100%;
  max-width: 700px;
  margin-bottom: var(--space-2xl);
}

@media (max-width: 520px) {
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
  max-width: 700px;
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
</style>
