<template>
  <div class="theme-switch">
    <div class="theme-options">
      <div
        v-for="opt in options"
        :key="opt.value"
        class="theme-option"
        :class="{ active: settings.theme === opt.value }"
        @click="settings.theme = opt.value"
      >
        <el-icon :size="24">
          <component :is="opt.icon" />
        </el-icon>
        <span>{{ opt.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()

const options = [
  { value: 'light', label: '浅色', icon: 'Sunny' },
  { value: 'dark', label: '深色', icon: 'Moon' },
  { value: 'system', label: '跟随系统', icon: 'Monitor' },
]
</script>

<style scoped>
.theme-options {
  display: flex;
  gap: var(--space-md);
}

.theme-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-lg) var(--space-xl);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-fast);
  min-width: 120px;
  color: var(--color-text-secondary);
}

.theme-option:hover {
  border-color: var(--color-primary-light);
  color: var(--color-primary);
}

.theme-option.active {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.theme-option span {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}
</style>
