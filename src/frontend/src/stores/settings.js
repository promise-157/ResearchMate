import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const theme = ref('system') // 'light' | 'dark' | 'system'
  const aiConfig = ref({
    apiType: 'openai',
    apiKey: '',
    apiBaseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o',
  })
  const crawlConfig = ref({
    maxPapersPerSource: 50,
    requestInterval: 2,
    timeout: 30,
  })

  function loadSettings() {
    // TODO: 从后端 API 加载设置
  }

  function saveSettings() {
    // TODO: 保存设置到后端 API
  }

  return { theme, aiConfig, crawlConfig, loadSettings, saveSettings }
})
