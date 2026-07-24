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
                <div class="data-value text-secondary">src/data/researchmate.db</div>
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

            <el-divider />

            <div class="data-row flex-between">
              <div>
                <div class="data-label">重置所有设置</div>
                <div class="data-value text-secondary">恢复所有设置项为默认值</div>
              </div>
              <el-button type="danger" plain @click="confirmResetAll">
                重置设置
              </el-button>
            </div>
          </div>
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
import { fetchSettings } from '@/api'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const activeSection = ref('appearance')

onMounted(async () => {
  try {
    const res = await fetchSettings()
    const data = res.data || res
    if (data.ai) {
      settingsStore.aiConfig.apiType = data.ai.api_type
      settingsStore.aiConfig.apiBaseUrl = data.ai.api_base_url
      settingsStore.aiConfig.model = data.ai.model
      // Don't override apiKey - it's not returned by server for security
    }
    if (data.crawl) {
      settingsStore.crawlConfig.maxPapersPerSource = data.crawl.max_papers_per_source
      settingsStore.crawlConfig.requestInterval = data.crawl.request_interval
      settingsStore.crawlConfig.timeout = data.crawl.timeout
    }
  } catch { /* server may not be running */ }
})

async function confirmClearPapers() {
  try {
    await ElMessageBox.confirm(
      '此操作将删除所有已爬取的论文数据和分析结果，不可恢复。确定继续？',
      '确认清空',
      { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning' }
    )
    ElMessage.info('清空论文功能将在后端实现后接入')
  } catch { /* cancelled */ }
}

async function confirmResetAll() {
  try {
    await ElMessageBox.confirm(
      '此操作将恢复所有设置为默认值。确定继续？',
      '确认重置',
      { confirmButtonText: '确定重置', cancelButtonText: '取消', type: 'warning' }
    )
    ElMessage.info('重置设置功能将在后端实现后接入')
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

@media (max-width: 700px) {
  .settings-layout {
    flex-direction: column;
  }
  .settings-sidebar {
    width: 100%;
  }
}
</style>
