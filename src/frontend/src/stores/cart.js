import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useCartStore = defineStore('cart', () => {
  const items = ref([])

  const count = computed(() => items.value.length)

  function isInCart(paperId) {
    return items.value.some((p) => p.id === paperId)
  }

  function addItem(paper) {
    if (!isInCart(paper.id)) {
      items.value.push(paper)
    }
  }

  function removeItem(paperId) {
    items.value = items.value.filter((p) => p.id !== paperId)
  }

  function clear() {
    items.value = []
  }

  return { items, count, isInCart, addItem, removeItem, clear }
})
