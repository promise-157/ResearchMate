<template>
  <div id="app-container">
    <NavBar @toggle-cart="showCart = !showCart" />
    <main class="main-content">
      <router-view />
    </main>
    <CartDrawer v-model:visible="showCart" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import NavBar from '@/components/NavBar.vue'
import CartDrawer from '@/components/CartDrawer.vue'

const showCart = ref(false)
</script>

<style>
/* 全局样式和 CSS 变量将在阶段二引入 */
</style>
