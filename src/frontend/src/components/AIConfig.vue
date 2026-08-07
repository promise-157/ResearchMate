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
        <div class="key-actions">
          <span class="form-hint">{{ keyStatusText }}</span>
          <el-button
            v-if="settings.aiConfig._hasKey || settings.aiConfig.apiKey"
            size="small"
            text
            type="danger"
            @click="clearSessionKey"
          >清除 Key</el-button>
        </div>
      </el-form-item>

      <el-form-item label="Key 保存方式">
        <el-radio-group v-model="settings.aiConfig.keyStorageMode">
          <el-radio-button value="session">安全模式</el-radio-button>
          <el-radio-button value="config">便利模式</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-alert
        v-if="settings.aiConfig.keyStorageMode === 'config'"
        :title="`便利模式会将 Key 明文写入 ${settings.aiConfig.configPath || 'src/backend/config.yaml'}。该文件已被 Git 忽略，但本机上能读取此文件的程序仍可看到 Key。`"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else
        title="安全模式不会把 Key 写入磁盘；关闭后端后需要重新输入。切换到此模式会删除 config.yaml 中已保存的 Key。"
        type="info"
        :closable="false"
        show-icon
      />

      <el-form-item label="API Base URL">
        <el-input v-model="settings.aiConfig.apiBaseUrl" />
      </el-form-item>

      <el-form-item label="模型名称">
        <el-input v-model="settings.aiConfig.model" />
      </el-form-item>

      <el-alert
        title="浏览器不会直接连接模型服务。只有你主动测试连接或确认分析时，后端才会发出外部请求。"
        type="info"
        :closable="false"
        show-icon
      />
      <el-button
        type="primary"
        plain
        :loading="testing"
        style="margin-top: 12px"
        @click="testConnection"
      >测试连接</el-button>
      <p v-if="testResult" class="form-hint test-result">{{ testResult }}</p>
    </el-form>

  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()
const testing = ref(false)
const testResult = ref('')
const keyStatusText = computed(() => {
  if (settings.aiConfig.keySource === 'environment') return '当前 Key 来自环境变量，网页清除不会删除环境变量。'
  if (settings.aiConfig.keySource === 'config') return `Key 已保存在 ${settings.aiConfig.configPath}`
  if (settings.aiConfig._hasKey) return 'Key 当前仅在后端进程内。'
  return '尚未配置 Key。'
})
const PRESETS = {
  openai:   { baseUrl: 'https://api.openai.com/v1',   model: 'gpt-4o' },
  claude:   { baseUrl: 'https://api.anthropic.com',    model: 'claude-sonnet-5' },
  deepseek: { baseUrl: 'https://api.deepseek.com',     model: 'deepseek-v4-pro' },
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
  () => [settings.aiConfig.apiType, settings.aiConfig.apiKey, settings.aiConfig.keyStorageMode, settings.aiConfig.apiBaseUrl, settings.aiConfig.model],
  () => scheduleSave(),
)

async function saveToBackend(rethrow = false) {
  try {
    const { updateSettings } = await import('@/api')
    const ai = {
        api_type: settings.aiConfig.apiType,
        api_base_url: settings.aiConfig.apiBaseUrl,
        model: settings.aiConfig.model,
        key_storage_mode: settings.aiConfig.keyStorageMode,
    }
    if (settings.aiConfig.apiKey) ai.api_key = settings.aiConfig.apiKey
    const result = await updateSettings({ ai })
    if (result.ai) {
      settings.aiConfig._hasKey = !!result.ai.has_key
      settings.aiConfig.keySource = result.ai.key_source
      settings.aiConfig.keyStorageMode = result.ai.key_storage_mode
      settings.aiConfig.configPath = result.ai.config_path
    }
    if (settings.aiConfig.apiKey) {
      settings.aiConfig._hasKey = true
      settings.aiConfig.keySource = settings.aiConfig.keyStorageMode === 'config' ? 'config' : 'session'
    } else if (settings.aiConfig.keyStorageMode === 'session' && settings.aiConfig.keySource === 'config') {
      settings.aiConfig.keySource = 'session'
    }
  } catch (error) {
    if (rethrow) throw error
    const message = error.response?.data?.detail || 'AI 设置保存失败'
    ElMessage.error(message)
    try {
      const { fetchSettings } = await import('@/api')
      const current = await fetchSettings()
      if (current.ai) {
        settings.aiConfig._hasKey = !!current.ai.has_key
        settings.aiConfig.keySource = current.ai.key_source
        settings.aiConfig.keyStorageMode = current.ai.key_storage_mode
        settings.aiConfig.configPath = current.ai.config_path
      }
    } catch { /* keep the original actionable save error visible */ }
  }
}

async function clearSessionKey() {
  const { updateSettings } = await import('@/api')
  const result = await updateSettings({ ai: { clear_api_key: true } })
  settings.aiConfig.apiKey = ''
  if (result.ai) {
    settings.aiConfig._hasKey = !!result.ai.has_key
    settings.aiConfig.keySource = result.ai.key_source
  }
}

async function testConnection() {
  try {
    await ElMessageBox.confirm(
      '测试会由后端向当前服务商发送一次最小请求，可能产生少量费用。不会发送工作区资料。是否继续？',
      '确认外部请求',
      { confirmButtonText: '发送一次测试', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  testing.value = true
  testResult.value = ''
  try {
    await saveToBackend(true)
    const { testAIConnection } = await import('@/api')
    const result = await testAIConnection()
    const model = result.provider_model || result.configured_model
    testResult.value = `连接成功 · ${result.provider} · ${model} · ${result.duration_ms} ms`
    ElMessage.success('AI 连接测试成功')
  } catch (error) {
    const message = error.response?.data?.detail || 'AI 连接测试失败'
    testResult.value = message
    ElMessage.error(message)
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.form-hint { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.key-actions {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
}
.test-result { margin: 8px 0 0; }
</style>
