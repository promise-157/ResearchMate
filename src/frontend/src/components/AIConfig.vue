<template>
  <div class="ai-config">
    <el-form label-position="top" size="default">
      <el-form-item label="API 类型">
        <el-select v-model="settings.aiConfig.apiType" style="width:100%" @change="onTypeChange">
          <el-option label="OpenAI" value="openai" />
          <el-option label="Claude (Anthropic)" value="claude" />
          <el-option label="DeepSeek" value="deepseek" />
          <el-option label="Ollama (本地)" value="ollama" />
          <el-option label="自定义兼容接口" value="custom" />
        </el-select>
      </el-form-item>

      <el-form-item label="API Key">
        <el-input
          v-model="settings.aiConfig.apiKey"
          type="password"
          show-password
          placeholder="sk-..."
        />
        <template #extra>
          <span class="form-hint">密钥只保留在当前后端进程内；长期使用请设置环境变量</span>
          <el-button
            v-if="settings.aiConfig._hasKey || settings.aiConfig.apiKey"
            size="small"
            text
            type="danger"
            @click="clearSessionKey"
          >清除会话 Key</el-button>
        </template>
      </el-form-item>

      <el-form-item label="API Base URL">
        <el-input v-model="settings.aiConfig.apiBaseUrl" />
      </el-form-item>

      <el-form-item label="模型名称">
        <el-input v-model="settings.aiConfig.model" />
      </el-form-item>

      <el-alert
        title="浏览器不会直接连接模型服务。保存后，只有你主动发起分析时，后端才会发送所选论文内容。"
        type="info"
        :closable="false"
        show-icon
      />
    </el-form>

  </div>
</template>

<script setup>
import { watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()
const PRESETS = {
  openai:   { baseUrl: 'https://api.openai.com/v1',   model: 'gpt-4o' },
  claude:   { baseUrl: 'https://api.anthropic.com',    model: 'claude-sonnet-5' },
  deepseek: { baseUrl: 'https://api.deepseek.com/v1',  model: 'deepseek-v4-pro' },
  ollama:   { baseUrl: 'http://localhost:11434/v1',    model: 'llama3.1:8b' },
  custom:   { baseUrl: '', model: '' },
}

// 切换类型时强制刷新预设
function onTypeChange(type) {
  const preset = PRESETS[type]
  if (preset) {
    settings.aiConfig.apiBaseUrl = preset.baseUrl
    settings.aiConfig.model = preset.model
  }
}

// 自动保存
let saveTimer = null
function scheduleSave() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(saveToBackend, 800)
}

watch(
  () => [settings.aiConfig.apiType, settings.aiConfig.apiKey, settings.aiConfig.apiBaseUrl, settings.aiConfig.model],
  () => scheduleSave(),
)

async function saveToBackend() {
  try {
    const { updateSettings } = await import('@/api')
    const ai = {
        api_type: settings.aiConfig.apiType,
        api_base_url: settings.aiConfig.apiBaseUrl,
        model: settings.aiConfig.model,
    }
    if (settings.aiConfig.apiKey) ai.api_key = settings.aiConfig.apiKey
    await updateSettings({ ai })
    if (settings.aiConfig.apiKey) settings.aiConfig._hasKey = true
  } catch { /* backend may not be running */ }
}

async function clearSessionKey() {
  const { updateSettings } = await import('@/api')
  await updateSettings({ ai: { clear_api_key: true } })
  settings.aiConfig.apiKey = ''
  settings.aiConfig._hasKey = false
}
</script>

<style scoped>
.form-hint { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
</style>
