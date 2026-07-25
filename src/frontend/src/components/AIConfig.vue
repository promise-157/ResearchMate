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
          v-model="apiKeyInput"
          type="password"
          show-password
          placeholder="sk-..."
          @change="settings.aiConfig.apiKey = $event"
        />
        <template #extra>
          <span class="form-hint">密钥仅存储在本地，不会上传</span>
        </template>
      </el-form-item>

      <el-form-item label="API Base URL">
        <el-input v-model="settings.aiConfig.apiBaseUrl" @change="modelsFetched = false" />
      </el-form-item>

      <el-form-item label="模型名称">
        <el-select
          v-if="availableModels.length > 0"
          v-model="settings.aiConfig.model"
          style="width:100%"
          filterable
          allow-create
        >
          <el-option v-for="m in availableModels" :key="m" :label="m" :value="m" />
        </el-select>
        <el-input v-else v-model="settings.aiConfig.model" />
      </el-form-item>

      <el-form-item>
        <div class="ai-actions">
          <el-button type="primary" plain @click="testConnection">
            测试连接
          </el-button>
          <el-button :loading="fetchingModels" @click="fetchModels">
            📋 获取可用模型
          </el-button>
        </div>
        <div v-if="modelStatus" class="model-status" :class="modelStatus.type">
          {{ modelStatus.text }}
        </div>
      </el-form-item>
    </el-form>

  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()
const apiKeyInput = ref(settings.aiConfig.apiKey)

const availableModels = ref([])
const modelsFetched = ref(false)
const fetchingModels = ref(false)
const modelStatus = ref(null)

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
  modelsFetched.value = false
  availableModels.value = []
  modelStatus.value = null
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
    await updateSettings({
      ai: {
        api_type: settings.aiConfig.apiType,
        api_key: settings.aiConfig.apiKey,
        api_base_url: settings.aiConfig.apiBaseUrl,
        model: settings.aiConfig.model,
      },
    })
  } catch { /* backend may not be running */ }
}

async function fetchModels() {
  if (!settings.aiConfig.apiKey && settings.aiConfig.apiType !== 'ollama') {
    ElMessage.warning('请先填写 API Key')
    return
  }

  fetchingModels.value = true
  modelStatus.value = null
  const baseUrl = settings.aiConfig.apiBaseUrl.replace(/\/$/, '')

  try {
    const resp = await axios.get(`${baseUrl}/models`, {
      headers: {
        Authorization: `Bearer ${settings.aiConfig.apiKey}`,
      },
      timeout: 10000,
    })

    const models = resp.data?.data || resp.data || []
    const ids = models
      .map((m) => (typeof m === 'string' ? m : m.id))
      .filter(Boolean)
      .sort()

    if (ids.length > 0) {
      availableModels.value = ids
      modelsFetched.value = true
      modelStatus.value = { type: 'ok', text: `找到 ${ids.length} 个模型` }
      ElMessage.success(`找到 ${ids.length} 个可用模型`)
      // 如果当前模型不在列表中，清空让用户选择
      if (!ids.includes(settings.aiConfig.model)) {
        settings.aiConfig.model = ids[0]
      }
    } else {
      modelStatus.value = { type: 'warn', text: '未找到模型列表' }
    }
  } catch (e) {
    const msg = e.response?.status === 401 ? 'API Key 无效'
      : e.response?.status === 404 ? '该接口不支持查询模型列表'
      : `查询失败: ${e.message}`
    modelStatus.value = { type: 'error', text: msg }
    ElMessage.warning(msg)
  } finally {
    fetchingModels.value = false
  }
}

function testConnection() {
  if (!settings.aiConfig.apiKey && settings.aiConfig.apiType !== 'ollama') {
    ElMessage.warning('请先填写 API Key')
    return
  }
  saveToBackend()
  fetchModels()
}
</script>

<style scoped>
.form-hint { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.ai-actions { display: flex; gap: var(--space-sm); }
.model-status { font-size: var(--font-size-xs); margin-top: var(--space-xs); }
.model-status.ok { color: var(--color-success); }
.model-status.error { color: var(--color-danger); }
.model-status.warn { color: var(--color-warning); }
</style>
