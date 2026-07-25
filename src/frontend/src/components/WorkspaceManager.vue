<template>
  <div>
    <!-- Workspace bar -->
    <div class="workspace-bar">
      <div class="ws-info">
        <el-icon><FolderOpened /></el-icon>
        <span class="ws-label">工作区: {{ wsName }}</span>
        <span class="ws-count">({{ paperCount }} 篇)</span>
      </div>
      <div class="ws-actions">
        <el-button size="small" @click="showDialog = true">切换</el-button>
        <el-button size="small" @click="handleNew">新建</el-button>
        <el-button size="small" type="danger" plain @click="$emit('clear')">清空</el-button>
      </div>
    </div>

    <!-- Workspace dialog -->
    <el-dialog v-model="showDialog" title="切换工作区" width="520px">
      <div v-if="list.length === 0" style="color:#999;text-align:center;padding:20px">暂无工作区</div>
      <div v-for="ws in list" :key="ws.id" class="ws-item"
           :class="{ active: ws.db_path === activePath }"
           @click="handleSwitch(ws)">
        <div>
          <div class="ws-item-name">{{ ws.name }}</div>
          <div class="ws-item-meta">{{ ws.paper_count || 0 }} 篇 · {{ ws.opened_at || '' }}</div>
        </div>
        <el-button v-if="ws.db_path !== activePath" size="small" type="primary" plain>加载</el-button>
        <el-tag v-else size="small" type="success">当前</el-tag>
      </div>
      <template #footer>
        <div class="ws-dialog-footer">
          <div>
            <el-button size="small" @click="handleExport">📤 导出</el-button>
            <el-button size="small" @click="handleImportClick">📥 导入</el-button>
          </div>
          <input ref="importInput" type="file" accept=".db" style="display:none" @change="onImportFile" />
          <el-button @click="showDialog = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchWorkspaces, createWorkspace, loadWorkspace, getExportUrl, importWorkspace } from '@/api'

const props = defineProps({
  paperCount: { type: Number, default: 0 },
})

const emit = defineEmits(['workspace-changed', 'clear'])

const showDialog = ref(false)
const list = ref([])
const activePath = ref('')
const wsName = ref('default')
const importInput = ref(null)

async function loadList() {
  try {
    const res = await fetchWorkspaces()
    const data = res.data || res
    list.value = data.items || []
    activePath.value = data.active_path
    wsName.value = data.active_name || 'default'
  } catch { /* ignore */ }
}

async function handleSwitch(ws) {
  try {
    await loadWorkspace(ws.db_path)
    activePath.value = ws.db_path
    wsName.value = ws.name
    showDialog.value = false
    emit('workspace-changed')
    ElMessage.success(`已切换到: ${ws.name}`)
  } catch { ElMessage.error('切换失败') }
}

async function handleNew() {
  try {
    const name = prompt('工作区名称:')
    if (!name) return
    const res = await createWorkspace(name)
    const data = res.data || res
    activePath.value = data.db_path
    wsName.value = data.name
    emit('workspace-changed')
    await loadList()
    ElMessage.success(`已创建: ${data.name}`)
  } catch { ElMessage.error('创建失败') }
}

function handleExport() {
  window.open(getExportUrl(), '_blank')
}

function handleImportClick() {
  importInput.value?.click()
}

async function onImportFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    const res = await importWorkspace(file)
    const data = res.data || res
    activePath.value = data.db_path
    wsName.value = data.name
    showDialog.value = false
    emit('workspace-changed')
    await loadList()
    ElMessage.success(`已导入: ${data.name}`)
  } catch { ElMessage.error('导入失败') }
  e.target.value = ''
}

onMounted(loadList)

defineExpose({ loadList, wsName })
</script>

<style scoped>
.workspace-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 16px; background: var(--color-bg-elevated);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  margin-bottom: var(--space-md);
}
.ws-info { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-size-sm); }
.ws-label { font-weight: var(--font-weight-medium); }
.ws-count { color: var(--color-text-secondary); }
.ws-actions { display: flex; gap: var(--space-xs); }
.ws-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px; border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm); margin-bottom: 8px; cursor: pointer;
}
.ws-item:hover { border-color: var(--color-primary); }
.ws-item.active { border-color: var(--color-primary); background: var(--color-primary-bg); }
.ws-item-name { font-size: var(--font-size-base); font-weight: var(--font-weight-medium); }
.ws-item-meta { font-size: var(--font-size-xs); color: var(--color-text-secondary); margin-top: 2px; }
.ws-dialog-footer { display: flex; justify-content: space-between; align-items: center; width: 100%; }
</style>
