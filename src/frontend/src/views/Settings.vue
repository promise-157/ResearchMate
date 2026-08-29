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
          <el-menu-item index="installation">
            <el-icon><InfoFilled /></el-icon>
            <span>安装与卸载</span>
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
                <div class="data-label">工作区与用户资产位置</div>
                <div class="data-value text-secondary">请在“安装与卸载”页查看当前运行方式对应的实际路径</div>
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

        <div v-show="activeSection === 'installation'">
          <h3 class="section-title">安装与卸载</h3>
          <el-alert
            v-if="runtimeError"
            type="error"
            :closable="false"
            :title="runtimeError"
          />
          <div v-else class="installation-section">
            <div class="runtime-platform">当前运行方式：{{ runtimeInfo.platform_label }}</div>
            <div v-for="entry in runtimeInfo.paths" :key="`${entry.label}:${entry.path}`" class="path-row">
              <div class="data-label">{{ entry.label }}</div>
              <code class="path-value">{{ entry.path }}</code>
              <div class="ownership-note">{{ ownershipLabel(entry.ownership) }}</div>
            </div>
            <el-divider />
            <div class="data-label">卸载方法</div>
            <p class="uninstall-summary">{{ runtimeInfo.uninstall.summary }}</p>
            <div v-if="runtimeInfo.uninstall.guide_path">
              <div class="data-label">卸载文档</div>
              <code class="path-value">{{ runtimeInfo.uninstall.guide_path }}</code>
            </div>
            <el-alert
              type="info"
              :closable="false"
              title="这里只显示路径和所有权，不会从网页删除程序、环境或用户数据。"
            />
            <el-divider />
            <div class="data-label">Windows 快捷方式图标</div>
            <p class="uninstall-summary">
              仅 Windows + WSL 桌面窗口可选择 ICO；文件会复制到应用本地状态，原文件之后可以移动。
            </p>
            <div class="icon-actions">
              <el-button :disabled="!shortcutIconAvailable" @click="selectShortcutIcon">
                选择 ICO 文件
              </el-button>
              <el-button :disabled="!shortcutIconAvailable" @click="resetShortcutIcon">
                恢复默认图标
              </el-button>
            </div>
            <div v-if="!shortcutIconAvailable" class="ownership-note">
              当前不是 Windows 桌面宿主窗口；普通浏览器不能修改 Windows 快捷方式。
            </div>
            <div v-if="shortcutIconMessage" :class="['icon-result', shortcutIconStatus]">
              {{ shortcutIconMessage }}
              <code v-if="shortcutIconPath" class="path-value">{{ shortcutIconPath }}</code>
            </div>
          </div>
        </div>

        <!-- Save / Reset bar -->
        <div v-show="activeSection !== 'installation'" class="settings-actions">
          <el-button type="primary" @click="handleSave()" :loading="saving">保存设置</el-button>
          <el-button @click="handleReset">重置为默认</el-button>
          <span v-if="saveMsg" class="save-msg" :class="saveMsgType">{{ saveMsg }}</span>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onBeforeUnmount, onMounted } from 'vue'
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
const runtimeInfo = ref({
  platform_label: '正在读取…', paths: [],
  uninstall: { available: false, summary: '', guide_path: '' },
})
const runtimeError = ref('')
const shortcutIconStatus = ref('')
const shortcutIconMessage = ref('')
const shortcutIconPath = ref('')
const desktopBridge = window.chrome?.webview
const shortcutIconAvailable = computed(() => (
  runtimeInfo.value.platform === 'windows_wsl' && !!desktopBridge
))

function handleDesktopMessage(event) {
  const message = event.data
  if (!message || message.type !== 'shortcut_icon_result') return
  shortcutIconStatus.value = message.status
  shortcutIconMessage.value = message.message || ''
  shortcutIconPath.value = message.path || ''
}

function selectShortcutIcon() {
  desktopBridge?.postMessage({ type: 'select_shortcut_icon' })
}

function resetShortcutIcon() {
  desktopBridge?.postMessage({ type: 'reset_shortcut_icon' })
}

onMounted(async () => {
  desktopBridge?.addEventListener('message', handleDesktopMessage)
  try {
    const res = await fetchSettings()
    const data = res.data || res
    if (data.ai) {
      settingsStore.aiConfig.apiType = data.ai.api_type
      settingsStore.aiConfig.apiBaseUrl = data.ai.api_base_url
      settingsStore.aiConfig.model = data.ai.model
      settingsStore.aiConfig._hasKey = !!data.ai.has_key
      settingsStore.aiConfig.keyStorageMode = data.ai.key_storage_mode || 'session'
      settingsStore.aiConfig.keySource = data.ai.key_source || 'none'
      settingsStore.aiConfig.configPath = data.ai.config_path || ''
      // Don't override apiKey - it's not returned by server for security
    }
    if (data.crawl) {
      settingsStore.crawlConfig.maxPapersPerSource = data.crawl.max_papers_per_source
      settingsStore.crawlConfig.requestInterval = data.crawl.request_interval
      settingsStore.crawlConfig.timeout = data.crawl.timeout
    }
    if (data.runtime) runtimeInfo.value = data.runtime
  } catch {
    runtimeError.value = '无法读取当前安装信息，请确认后端正在运行。'
  }
})

onBeforeUnmount(() => desktopBridge?.removeEventListener('message', handleDesktopMessage))

function ownershipLabel(ownership) {
  return {
    application: '卸载 ResearchMate 时删除',
    application_state: '应用本地状态；仅明确选择时彻底删除',
    rebuildable: '可重新生成',
    user: '用户所有；卸载时保留',
    user_data: '用户数据；卸载时保留并应先备份',
    external: '外部依赖；卸载时保留',
  }[ownership] || '请按卸载文档确认所有权'
}

async function handleSave(clearKey = false) {
  saving.value = true
  saveMsg.value = ''
  try {
    const ai = {
        api_type: settingsStore.aiConfig.apiType,
        api_base_url: settingsStore.aiConfig.apiBaseUrl,
        model: settingsStore.aiConfig.model,
        key_storage_mode: settingsStore.aiConfig.keyStorageMode,
    }
    if (settingsStore.aiConfig.apiKey) ai.api_key = settingsStore.aiConfig.apiKey
    if (clearKey) ai.clear_api_key = true
    const result = await updateSettings({
      ai,
      crawl: {
        max_papers_per_source: settingsStore.crawlConfig.maxPapersPerSource,
        request_interval: settingsStore.crawlConfig.requestInterval,
        timeout: settingsStore.crawlConfig.timeout,
      },
    })
    if (result.ai) {
      settingsStore.aiConfig._hasKey = !!result.ai.has_key
      settingsStore.aiConfig.keySource = result.ai.key_source
      settingsStore.aiConfig.keyStorageMode = result.ai.key_storage_mode
      settingsStore.aiConfig.configPath = result.ai.config_path
    }
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
    settingsStore.aiConfig = {
      apiType: 'openai', apiKey: '', apiBaseUrl: 'https://api.openai.com/v1',
      model: 'gpt-4o', keyStorageMode: 'session', keySource: 'none', configPath: '',
      _hasKey: false,
    }
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

.installation-section {
  display: grid;
  gap: var(--space-md);
}

.runtime-platform {
  font-weight: var(--font-weight-medium);
}

.path-row {
  display: grid;
  gap: 4px;
}

.path-value {
  display: block;
  padding: var(--space-sm);
  border-radius: var(--radius-sm);
  background: var(--color-bg-secondary);
  overflow-wrap: anywhere;
  user-select: text;
}

.ownership-note,
.uninstall-summary {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.icon-actions {
  display: flex;
  gap: 10px;
  margin: 10px 0;
}

.icon-result {
  margin-top: 10px;
  color: var(--text-secondary);
}

.icon-result.error {
  color: var(--el-color-danger);
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
