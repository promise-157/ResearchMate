<template>
  <div class="settings-page">
    <h1 class="page-title">全局设置</h1>

    <div class="settings-layout">
      <!-- Sidebar -->
      <aside class="settings-sidebar">
        <el-menu
          :default-active="activeSection"
          @select="activeSection = $event"
        >
          <el-menu-item index="appearance">
            <el-icon><Brush /></el-icon>
            <span>外观</span>
          </el-menu-item>
          <el-menu-item index="ai">
            <el-icon><Cpu /></el-icon>
            <span>AI 配置</span>
          </el-menu-item>
          <el-menu-item index="crawl">
            <el-icon><Download /></el-icon>
            <span>爬取设置</span>
          </el-menu-item>
          <el-menu-item index="data">
            <el-icon><FolderOpened /></el-icon>
            <span>数据管理</span>
          </el-menu-item>
        </el-menu>
      </aside>

      <!-- Content -->
      <section class="settings-content card">
        <!-- Appearance -->
        <div v-show="activeSection === 'appearance'">
          <h3 class="section-title">主题模式</h3>
          <ThemeSwitch />
        </div>

        <!-- AI Config -->
        <div v-show="activeSection === 'ai'">
          <h3 class="section-title">AI 接口配置</h3>
          <AIConfig />
        </div>

        <!-- Crawl Config -->
        <div v-show="activeSection === 'crawl'">
          <h3 class="section-title">爬取参数</h3>
          <CrawlConfig />
        </div>

        <!-- Data Management -->
        <div v-show="activeSection === 'data'">
          <h3 class="section-title">数据管理</h3>
          <div class="data-section">
            <div class="data-row flex-between">
              <div>
                <div class="data-label">数据库位置</div>
                <div class="data-value text-secondary">src/data/（主数据库 + workspaces/）</div>
              </div>
            </div>

            <el-divider />

            <div class="data-row flex-between">
              <div>
                <div class="data-label">清空论文数据</div>
                <div class="data-value text-secondary">删除所有已爬取的论文和分析结果</div>
              </div>
              <el-button type="danger" plain @click="confirmClearPapers">
                清空论文
              </el-button>
            </div>

          </div>
        </div>

        <!-- Save / Reset bar -->
        <div class="settings-actions">
          <el-button type="primary" @click="handleSave()" :loading="saving">保存设置</el-button>
          <el-button @click="handleReset">重置为默认</el-button>
          <span v-if="saveMsg" class="save-msg" :class="saveMsgType">{{ saveMsg }}</span>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import ThemeSwitch from '@/components/ThemeSwitch.vue'
import AIConfig from '@/components/AIConfig.vue'
import CrawlConfig from '@/components/CrawlConfig.vue'
import { fetchSettings, updateSettings, clearWorkspace } from '@/api'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const activeSection = ref('appearance')
const saving = ref(false)
const saveMsg = ref('')
const saveMsgType = ref('')

onMounted(async () => {
  try {
    const res = await fetchSettings()
    const data = res.data || res
    if (data.ai) {
      settingsStore.aiConfig.apiType = data.ai.api_type
      settingsStore.aiConfig.apiBaseUrl = data.ai.api_base_url
      settingsStore.aiConfig.model = data.ai.model
      settingsStore.aiConfig._hasKey = !!data.ai.has_key
      // Don't override apiKey - it's not returned by server for security
    }
    if (data.crawl) {
      settingsStore.crawlConfig.maxPapersPerSource = data.crawl.max_papers_per_source
      settingsStore.crawlConfig.requestInterval = data.crawl.request_interval
      settingsStore.crawlConfig.timeout = data.crawl.timeout
    }
  } catch { /* server may not be running */ }
})

async function handleSave(clearKey = false) {
  saving.value = true
  saveMsg.value = ''
  try {
    const ai = {
        api_type: settingsStore.aiConfig.apiType,
        api_base_url: settingsStore.aiConfig.apiBaseUrl,
        model: settingsStore.aiConfig.model,
    }
    if (settingsStore.aiConfig.apiKey) ai.api_key = settingsStore.aiConfig.apiKey
    if (clearKey) ai.clear_api_key = true
    await updateSettings({
      ai,
      crawl: {
        max_papers_per_source: settingsStore.crawlConfig.maxPapersPerSource,
        request_interval: settingsStore.crawlConfig.requestInterval,
        timeout: settingsStore.crawlConfig.timeout,
      },
    })
    saveMsg.value = '✓ 设置已保存'
    saveMsgType.value = 'ok'
  } catch {
    saveMsg.value = '保存失败'
    saveMsgType.value = 'error'
  } finally {
    saving.value = false
    setTimeout(() => { saveMsg.value = '' }, 3000)
  }
}

async function handleReset() {
  try {
    await ElMessageBox.confirm('确定恢复所有设置为默认值？', '确认重置', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
    })
    settingsStore.aiConfig = { apiType: 'openai', apiKey: '', apiBaseUrl: 'https://api.openai.com/v1', model: 'gpt-4o' }
    settingsStore.crawlConfig = { maxPapersPerSource: 50, requestInterval: 2, timeout: 30 }
    settingsStore.theme = 'system'
    await handleSave(true)
    ElMessage.success('已恢复并保存默认设置')
  } catch { /* cancelled */ }
}

async function confirmClearPapers() {
  try {
    await ElMessageBox.confirm(
      '此操作将删除所有已爬取的论文数据和分析结果，不可恢复。确定继续？',
      '确认清空',
      { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning' }
    )
    await clearWorkspace()
    ElMessage.success('当前工作区已清空')
  } catch { /* cancelled */ }
}

</script>

<style scoped>
.settings-page {
  padding-top: var(--space-lg);
}

.settings-layout {
  display: flex;
  gap: var(--space-lg);
  align-items: flex-start;
}

.settings-sidebar {
  width: 200px;
  flex-shrink: 0;
}

.settings-sidebar .el-menu {
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.settings-content {
  flex: 1;
  padding: var(--space-xl);
  min-height: 400px;
}

.data-section {
  padding: var(--space-md) 0;
}

.data-row {
  padding: var(--space-sm) 0;
}

.data-label {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
}

.data-value {
  font-size: var(--font-size-sm);
  margin-top: 2px;
}

.settings-actions {
  margin-top: var(--space-xl);
  padding-top: var(--space-md);
  border-top: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.save-msg { font-size: var(--font-size-sm); }
.save-msg.ok { color: var(--color-success); }
.save-msg.error { color: var(--color-danger); }

@media (max-width: 700px) {
  .settings-layout {
    flex-direction: column;
  }
  .settings-sidebar {
    width: 100%;
  }
}
</style>
