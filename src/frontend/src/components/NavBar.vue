<template>
  <header class="navbar">
    <div class="navbar-left">
      <router-link to="/" class="logo">ResearchMate</router-link>
      <nav class="nav-links">
        <router-link to="/materials">资料中心</router-link>
        <router-link to="/actions">行动专题</router-link>
        <router-link to="/papers">论文中心</router-link>
        <router-link to="/docs">文档</router-link>
        <router-link to="/settings">设置</router-link>
      </nav>
    </div>
    <div class="navbar-right">
      <el-badge :value="cartCount" :hidden="cartCount === 0">
        <el-button circle @click="$emit('toggle-cart')" title="购物车">
          <el-icon><ShoppingCart /></el-icon>
        </el-button>
      </el-badge>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useCartStore } from '@/stores/cart'

defineEmits(['toggle-cart'])

const cartStore = useCartStore()
const cartCount = computed(() => cartStore.count)
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 56px;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
  background: var(--color-bg-nav, #fff);
}
.navbar-left {
  display: flex;
  align-items: center;
  gap: 32px;
}
.logo {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary, #409eff);
  text-decoration: none;
}
.nav-links {
  display: flex;
  gap: 16px;
}
.nav-links a {
  color: var(--color-text, #374151);
  text-decoration: none;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.2s;
}
.nav-links a:hover,
.nav-links a.router-link-active {
  color: var(--color-primary, #409eff);
}
</style>
