import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useWorkspaceStore = defineStore('workspace', () => {
  const generation = ref(0)
  const transitioning = ref(false)
  const consumers = new Map()
  const pendingMutations = new Set()

  function registerConsumer(key, handlers) {
    consumers.set(key, handlers)
    return () => {
      if (consumers.get(key) === handlers) consumers.delete(key)
    }
  }

  function invalidateConsumers() {
    generation.value += 1
    for (const consumer of consumers.values()) consumer.invalidate?.()
  }

  async function reloadConsumers() {
    await Promise.allSettled(
      [...consumers.values()].map((consumer) => consumer.reload?.()),
    )
  }

  async function runTransition(action) {
    if (transitioning.value) throw new Error('工作区正在切换，请稍候')
    transitioning.value = true
    let result
    let actionError
    try {
      await Promise.allSettled([...pendingMutations])
      invalidateConsumers()
      result = await action()
    } catch (error) {
      actionError = error
    } finally {
      transitioning.value = false
      await reloadConsumers()
    }
    if (actionError) throw actionError
    return result
  }

  async function runMutation(action) {
    if (transitioning.value) throw new Error('工作区正在切换，请稍候')
    const mutation = Promise.resolve().then(action)
    pendingMutations.add(mutation)
    try {
      return await mutation
    } finally {
      pendingMutations.delete(mutation)
    }
  }

  async function refreshCurrentWorkspace() {
    invalidateConsumers()
    await reloadConsumers()
  }

  return {
    generation,
    transitioning,
    registerConsumer,
    runTransition,
    runMutation,
    refreshCurrentWorkspace,
  }
})
