<template>
  <div class="ai-config">
    <el-form label-position="top" size="default">
      <el-form-item label="API 类型">
        <el-select v-model="settings.aiConfig.apiType" style="width:100%">
          <el-option label="OpenAI" value="openai" />
          <el-option label="Claude (Anthropic)" value="claude" />
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
        <el-input v-model="settings.aiConfig.apiBaseUrl" placeholder="https://api.openai.com/v1" />
      </el-form-item>

      <el-form-item label="模型名称">
        <el-input v-model="settings.aiConfig.model" placeholder="gpt-4o" />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" plain @click="testConnection">
          测试连接
        </el-button>
      </el-form-item>
    </el-form>

    <!-- Prompt Template (collapsible) -->
    <el-collapse>
      <el-collapse-item title="分析 Prompt 模板（高级）" name="prompt">
        <el-input
          v-model="promptTemplate"
          type="textarea"
          :rows="10"
          placeholder="自定义 AI 分析摘要用的 prompt..."
        />
        <div style="margin-top:8px">
          <el-button size="small" text @click="resetPrompt">恢复默认</el-button>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useSettingsStore } from '@/stores/settings'

const settings = useSettingsStore()

const apiKeyInput = ref(settings.aiConfig.apiKey)

const defaultPrompt = `你是一个论文评审助手。阅读以下论文摘要，用中文回答：
1. 这篇论文是否提到了开源代码或 GitHub 链接？如有请提取 URL
2. 这篇论文的核心创新点是什么？（一句话概括）
3. 论文使用了哪些关键技术/方法/模型？（列出关键词）

摘要: {abstract_text}`

const promptTemplate = ref(defaultPrompt)

function resetPrompt() {
  promptTemplate.value = defaultPrompt
}

function testConnection() {
  if (!settings.aiConfig.apiKey && settings.aiConfig.apiType !== 'ollama') {
    ElMessage.warning('请先填写 API Key')
    return
  }
  ElMessage.info('测试连接功能将在后端实现后接入')
}
</script>

<style scoped>
.form-hint {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
</style>
