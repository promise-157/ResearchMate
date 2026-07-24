<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="购物车"
    direction="rtl"
    size="380px"
  >
    <div v-if="cartStore.items.length === 0" class="cart-empty">
      <p>购物车为空</p>
      <p class="hint">浏览论文时点击 🛒 即可加入购物车</p>
    </div>
    <div v-else class="cart-list">
      <div v-for="item in cartStore.items" :key="item.id" class="cart-item">
        <div class="cart-item-info">
          <div class="cart-item-title">{{ item.title }}</div>
          <div class="cart-item-source">{{ item.journal_name }}</div>
        </div>
        <el-button type="danger" text circle @click="cartStore.removeItem(item.id)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
      <div class="cart-actions">
        <el-button @click="copyTitles">复制标题列表</el-button>
        <el-button type="primary" @click="exportCSV">导出 CSV</el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { useCartStore } from '@/stores/cart'

defineProps({ visible: Boolean })
defineEmits(['update:visible'])

const cartStore = useCartStore()

function copyTitles() {
  const titles = cartStore.items.map((p) => p.title).join('\n')
  navigator.clipboard.writeText(titles)
  ElMessage.success('已复制到剪贴板')
}

function exportCSV() {
  ElMessage.info('CSV 导出将在后端实现后接入')
}
</script>

<style scoped>
.cart-empty {
  text-align: center;
  padding: 40px 0;
  color: #999;
}
.cart-empty .hint {
  font-size: 13px;
  margin-top: 8px;
}
.cart-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border, #eee);
}
.cart-item-title {
  font-size: 14px;
  font-weight: 500;
}
.cart-item-source {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}
.cart-actions {
  margin-top: 20px;
  display: flex;
  gap: 8px;
}
</style>
