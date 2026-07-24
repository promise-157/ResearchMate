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
import { ref, onMounted, watch } from 'vue'
import NavBar from '@/components/NavBar.vue'
import CartDrawer from '@/components/CartDrawer.vue'
import { useSettingsStore } from '@/stores/settings'

const showCart = ref(false)
const settings = useSettingsStore()

function applyTheme(theme) {
  if (theme === 'system') {
    document.documentElement.setAttribute('data-theme', 'system')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
}

onMounted(() => {
  const saved = localStorage.getItem('rm-theme') || 'system'
  settings.theme = saved
  applyTheme(saved)
})

watch(() => settings.theme, (val) => {
  localStorage.setItem('rm-theme', val)
  applyTheme(val)
})
</script>
