<template>
  <router-link :to="to" class="nav-card card card-clickable">
    <div class="nav-card-icon">
      <el-icon :size="40">
        <component :is="icon" />
      </el-icon>
    </div>
    <div class="nav-card-body">
      <h3 class="nav-card-title">{{ title }}</h3>
      <p class="nav-card-desc">{{ description }}</p>
    </div>
  </router-link>
</template>

<script setup>
defineProps({
  icon: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  to: { type: String, required: true },
})
</script>

<style scoped>
.nav-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: var(--space-2xl) var(--space-lg);
  min-height: 200px;
  text-decoration: none;
}

.nav-card-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-xl);
  background: var(--color-primary-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-md);
  color: var(--color-primary);
  transition:
    background var(--transition-normal),
    transform var(--transition-normal);
}

.nav-card:hover .nav-card-icon {
  background: var(--color-primary);
  color: #fff;
  transform: scale(1.05);
}

.nav-card-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-sm);
}

.nav-card-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
  max-width: 240px;
}
</style>
