import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const theme = ref('system') // 'light' | 'dark' | 'system'
  const aiConfig = ref({
    apiType: 'openai',
    apiKey: '',
    keyStorageMode: 'session',
    keySource: 'none',
    configPath: '',
    apiBaseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o',
    _hasKey: false,
  })
  const crawlConfig = ref({
    maxPapersPerSource: 50,
    requestInterval: 2,
    timeout: 30,
  })

  return { theme, aiConfig, crawlConfig }
})
