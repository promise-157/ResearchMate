import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchCart, getApiErrorMessage, updatePaper } from '@/api'
import { useWorkspaceStore } from '@/stores/workspace'

export const useCartStore = defineStore('cart', () => {
  const workspaceStore = useWorkspaceStore()
  const items = ref([])
  const loading = ref(false)
  const error = ref('')
  let workspaceGeneration = 0
  let latestRequest = 0

  const count = computed(() => items.value.length)

  function isInCart(paperId) {
    return items.value.some((p) => p.id === paperId)
  }

  function addItem(paper) {
    if (!isInCart(paper.id)) {
      items.value.push(paper)
    }
    error.value = ''
  }

  function removeItem(paperId) {
    items.value = items.value.filter((p) => p.id !== paperId)
    error.value = ''
  }

  async function removeFromCart(paperId) {
    await workspaceStore.runMutation(() => updatePaper(paperId, { in_cart: false }))
    removeItem(paperId)
  }

  function clear() {
    workspaceGeneration += 1
    latestRequest += 1
    items.value = []
    loading.value = false
    error.value = ''
  }

  async function refreshFromBackend() {
    const generation = workspaceGeneration
    const requestId = ++latestRequest
    loading.value = true
    error.value = ''
    try {
      const res = await fetchCart()
      const data = res.data || res
      if (!Array.isArray(data)) throw new Error('购物车响应格式无效')
      if (generation !== workspaceGeneration || requestId !== latestRequest) return false
      items.value = data
      return true
    } catch (requestError) {
      if (generation !== workspaceGeneration || requestId !== latestRequest) return false
      error.value = getApiErrorMessage(requestError, '购物车加载失败')
      return false
    } finally {
      if (generation === workspaceGeneration && requestId === latestRequest) {
        loading.value = false
      }
    }
  }

  workspaceStore.registerConsumer('cart', {
    invalidate: clear,
    reload: refreshFromBackend,
  })

  return {
    items,
    count,
    loading,
    error,
    isInCart,
    addItem,
    removeItem,
    removeFromCart,
    clear,
    refreshFromBackend,
  }
})
