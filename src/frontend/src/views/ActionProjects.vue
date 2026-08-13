<template>
  <div class="actions-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">行动专题</h1>
        <p class="text-secondary text-small">
          围绕一个真实任务组织证据，保存你的目标、笔记和下一步。这里不会自动改写来源资料。
        </p>
      </div>
      <el-button @click="$router.push('/materials')">去资料中心选择证据</el-button>
    </div>

    <WorkspaceManager
      :paper-count="projects.length"
      unit="个专题"
      @workspace-changed="reloadWorkspace"
      @clear="confirmClear"
    />

    <div v-if="loading" class="empty-state">正在加载行动专题…</div>
    <div v-else-if="projects.length === 0" class="empty-state card">
      <div class="empty-state-icon">🎯</div>
      <p>当前工作区还没有行动专题</p>
      <p class="text-small text-secondary">到资料中心勾选 1–20 条资料，然后点击“建立行动专题”。</p>
    </div>

    <div v-else class="actions-layout">
      <aside class="project-list card">
        <article
          v-for="project in projects"
          :key="project.id"
          class="project-list-item"
          :class="{ active: selected?.id === project.id }"
          @click="openProject(project.id)"
        >
          <div class="project-list-head">
            <el-tag size="small" :type="statusTagType(project.status)">{{ statusLabel(project.status) }}</el-tag>
            <span>{{ project.material_count }} 条证据</span>
          </div>
          <strong>{{ project.title }}</strong>
          <p>{{ project.next_action || '尚未填写下一步' }}</p>
        </article>
      </aside>

      <section v-if="selected" class="project-detail card">
        <div class="detail-head">
          <div>
            <h2>{{ selected.title }}</h2>
            <span class="text-small text-secondary">更新于 {{ formatTime(selected.updated_at) }}</span>
          </div>
          <el-select v-model="draft.status" class="project-status" @change="saveProject">
            <el-option label="进行中" value="active" />
            <el-option label="已完成" value="completed" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </div>

        <el-form label-position="top">
          <el-form-item label="专题标题">
            <el-input v-model="draft.title" maxlength="200" />
          </el-form-item>
          <el-form-item label="目标">
            <el-input v-model="draft.objective" type="textarea" :rows="3" maxlength="2000" />
          </el-form-item>
          <el-form-item label="用户笔记 / 当前结论">
            <el-input v-model="draft.notes" type="textarea" :rows="7" maxlength="12000" />
          </el-form-item>
          <el-form-item label="明确下一步">
            <el-input v-model="draft.next_action" type="textarea" :rows="2" maxlength="1000" />
          </el-form-item>
          <el-button
            type="primary"
            :loading="saving"
            :disabled="!draft.title.trim()"
            @click="saveProject"
          >保存专题</el-button>
        </el-form>

        <el-divider />
        <div class="evidence-head">
          <div>
            <h3>有序证据清单</h3>
            <p class="text-small text-secondary">顺序代表阅读或论证顺序；调整清单不会修改资料本身。</p>
          </div>
          <el-button size="small" @click="openEvidenceEditor">添加证据</el-button>
        </div>
        <article v-for="(material, index) in selected.materials" :key="material.id" class="evidence-item">
          <div class="evidence-order">{{ index + 1 }}</div>
          <div class="evidence-main">
            <router-link :to="{ path: '/materials', query: { item: material.id } }">
              #{{ material.id }} {{ material.title }}
            </router-link>
            <p>{{ material.summary || material.content_text.slice(0, 160) }}</p>
          </div>
          <div class="evidence-actions">
            <el-button size="small" :disabled="index === 0 || evidenceSaving" @click="moveEvidence(index, -1)">上移</el-button>
            <el-button size="small" :disabled="index === selected.materials.length - 1 || evidenceSaving" @click="moveEvidence(index, 1)">下移</el-button>
            <el-button size="small" type="danger" plain :disabled="selected.materials.length === 1 || evidenceSaving" @click="removeEvidence(index)">移除</el-button>
          </div>
        </article>
      </section>
    </div>

    <el-dialog v-model="showEvidenceEditor" title="编辑证据清单" width="720px" :close-on-click-modal="false">
      <p class="text-small text-secondary">最多 20 条；新勾选资料追加到清单末尾。清单至少保留一条资料。</p>
      <div class="evidence-search">
        <el-input v-model="materialQuery" placeholder="搜索标题或正文" clearable @keyup.enter="searchMaterials" />
        <el-button :loading="materialsLoading" @click="searchMaterials">搜索资料</el-button>
      </div>
      <div class="evidence-options">
        <label v-for="material in materialOptions" :key="material.id" class="evidence-option">
          <el-checkbox
            :model-value="evidenceIds.includes(material.id)"
            @change="toggleEvidence(material, $event)"
          />
          <span>#{{ material.id }} {{ material.title }}</span>
        </label>
      </div>
      <h4>当前顺序（{{ evidenceIds.length }}）</h4>
      <ol class="ordered-preview">
        <li v-for="material in orderedEvidencePreview" :key="material.id">#{{ material.id }} {{ material.title }}</li>
      </ol>
      <template #footer>
        <el-button @click="showEvidenceEditor = false">取消</el-button>
        <el-button
          type="primary"
          :loading="evidenceSaving"
          :disabled="evidenceIds.length === 0"
          @click="saveEvidenceEditor"
        >保存证据清单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import WorkspaceManager from '@/components/WorkspaceManager.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import {
  clearWorkspace,
  fetchActionProject,
  fetchActionProjects,
  fetchItems,
  replaceActionProjectMaterials,
  updateActionProject,
} from '@/api'

const route = useRoute()
const router = useRouter()
const workspaceStore = useWorkspaceStore()
const projects = ref([])
const selected = ref(null)
const loading = ref(false)
const saving = ref(false)
const evidenceSaving = ref(false)
const showEvidenceEditor = ref(false)
const materialsLoading = ref(false)
const materialQuery = ref('')
const materialOptions = ref([])
const evidenceIds = ref([])
const draft = reactive({ title: '', objective: '', notes: '', next_action: '', status: 'active' })

const orderedEvidencePreview = computed(() => {
  const known = new Map([
    ...(selected.value?.materials || []),
    ...materialOptions.value,
  ].map((material) => [material.id, material]))
  return evidenceIds.value.map((id) => known.get(id)).filter(Boolean)
})

function applyProject(project) {
  selected.value = project
  Object.assign(draft, {
    title: project.title,
    objective: project.objective,
    notes: project.notes,
    next_action: project.next_action,
    status: project.status,
  })
}

async function loadProjects(preferredId = null) {
  const generation = workspaceStore.generation
  loading.value = true
  try {
    const result = await fetchActionProjects()
    if (generation !== workspaceStore.generation) return
    projects.value = result.projects || []
    const requested = Number(preferredId || route.query.project)
    const nextId = projects.value.some((project) => project.id === requested)
      ? requested
      : projects.value[0]?.id
    if (nextId) await openProject(nextId)
    else selected.value = null
  } catch (error) {
    if (generation === workspaceStore.generation) {
      ElMessage.error(error.response?.data?.detail || '行动专题加载失败')
    }
  } finally {
    if (generation === workspaceStore.generation) loading.value = false
  }
}

async function openProject(projectId) {
  const generation = workspaceStore.generation
  try {
    const result = await fetchActionProject(projectId)
    if (generation !== workspaceStore.generation) return
    applyProject(result.project)
    if (String(route.query.project || '') !== String(projectId)) {
      await router.replace({ query: { ...route.query, project: projectId } })
    }
  } catch (error) {
    if (generation === workspaceStore.generation) {
      ElMessage.error(error.response?.data?.detail || '行动专题详情加载失败')
    }
  }
}

async function saveProject() {
  const generation = workspaceStore.generation
  const projectId = selected.value.id
  saving.value = true
  try {
    const result = await workspaceStore.runMutation(() => updateActionProject(projectId, { ...draft }))
    if (generation !== workspaceStore.generation) return
    applyProject(result.project)
    await refreshListSummary(generation)
    if (generation === workspaceStore.generation) ElMessage.success('行动专题已保存')
  } catch (error) {
    if (generation === workspaceStore.generation) {
      ElMessage.error(error.response?.data?.detail || '行动专题保存失败')
    }
  } finally { saving.value = false }
}

async function refreshListSummary(generation = workspaceStore.generation) {
  const result = await fetchActionProjects()
  if (generation !== workspaceStore.generation) return
  projects.value = result.projects || []
}

async function persistEvidence(ids) {
  const generation = workspaceStore.generation
  const projectId = selected.value.id
  evidenceSaving.value = true
  try {
    const result = await workspaceStore.runMutation(
      () => replaceActionProjectMaterials(projectId, ids),
    )
    if (generation !== workspaceStore.generation) return false
    applyProject(result.project)
    await refreshListSummary(generation)
    return true
  } catch (error) {
    if (generation === workspaceStore.generation) {
      ElMessage.error(error.response?.data?.detail || '证据清单保存失败')
    }
    return false
  } finally { evidenceSaving.value = false }
}

async function moveEvidence(index, offset) {
  const ids = selected.value.materials.map((material) => material.id)
  const target = index + offset
  ;[ids[index], ids[target]] = [ids[target], ids[index]]
  if (await persistEvidence(ids)) ElMessage.success('证据顺序已更新')
}

async function removeEvidence(index) {
  const ids = selected.value.materials.map((material) => material.id)
  ids.splice(index, 1)
  if (await persistEvidence(ids)) ElMessage.success('证据已移出专题，原资料仍保留')
}

async function openEvidenceEditor() {
  evidenceIds.value = selected.value.materials.map((material) => material.id)
  materialQuery.value = ''
  showEvidenceEditor.value = true
  await searchMaterials()
}

async function searchMaterials() {
  const generation = workspaceStore.generation
  materialsLoading.value = true
  try {
    const result = await fetchItems({ q: materialQuery.value || undefined, page: 1, page_size: 100 })
    if (generation !== workspaceStore.generation) return
    materialOptions.value = result.items || []
  } catch (error) {
    if (generation === workspaceStore.generation) {
      ElMessage.error(error.response?.data?.detail || '资料搜索失败')
    }
  } finally { materialsLoading.value = false }
}

function toggleEvidence(material, checked) {
  if (checked) {
    if (evidenceIds.value.length >= 20) {
      ElMessage.warning('证据清单最多 20 条')
      return
    }
    if (!evidenceIds.value.includes(material.id)) evidenceIds.value.push(material.id)
  } else if (evidenceIds.value.length > 1) {
    evidenceIds.value = evidenceIds.value.filter((id) => id !== material.id)
  } else {
    ElMessage.warning('行动专题至少保留一条证据')
  }
}

async function saveEvidenceEditor() {
  if (await persistEvidence(evidenceIds.value)) {
    showEvidenceEditor.value = false
    ElMessage.success('证据清单已保存')
  }
}

function reloadWorkspace() {
  selected.value = null
  projects.value = []
  showEvidenceEditor.value = false
  router.replace({ query: {} })
  loadProjects()
}

async function confirmClear() {
  try {
    await ElMessageBox.confirm(
      '确定清空当前工作区的全部资料、行动专题和论文数据？此操作不可恢复。',
      '确认清空',
      { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning' },
    )
    await workspaceStore.runMutation(() => clearWorkspace())
    await workspaceStore.refreshCurrentWorkspace()
    await loadProjects()
    ElMessage.success('当前工作区已清空')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.detail || '工作区清空失败')
    }
  }
}

function statusLabel(status) {
  return { active: '进行中', completed: '已完成', archived: '已归档' }[status] || status
}

function statusTagType(status) {
  return { active: 'primary', completed: 'success', archived: 'info' }[status] || 'info'
}

function formatTime(value) {
  return value ? value.slice(0, 16) : '—'
}

onMounted(() => loadProjects())
</script>

<style scoped>
.actions-page { padding-top: var(--space-lg); }
.page-head, .detail-head, .evidence-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-md); }
.actions-layout { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: var(--space-md); align-items: start; }
.project-list { padding: 0; overflow: hidden; }
.project-list-item { padding: var(--space-md); border-bottom: 1px solid var(--color-border-light); cursor: pointer; }
.project-list-item:last-child { border-bottom: 0; }
.project-list-item.active { background: var(--color-primary-bg); }
.project-list-head { display: flex; justify-content: space-between; align-items: center; gap: var(--space-xs); color: var(--color-text-secondary); font-size: var(--font-size-xs); margin-bottom: var(--space-xs); }
.project-list-item strong { display: block; }
.project-list-item p { color: var(--color-text-secondary); font-size: var(--font-size-xs); margin-bottom: 0; }
.project-detail h2, .evidence-head h3 { margin-top: 0; }
.project-status { width: 120px; }
.evidence-item { display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; gap: var(--space-sm); padding: var(--space-sm) 0; border-top: 1px solid var(--color-border-light); align-items: start; }
.evidence-order { width: 28px; height: 28px; border-radius: 50%; background: var(--color-primary-bg); color: var(--color-primary); display: flex; align-items: center; justify-content: center; font-weight: 600; }
.evidence-main a { color: var(--color-primary); font-weight: 600; text-decoration: none; }
.evidence-main p { color: var(--color-text-secondary); font-size: var(--font-size-xs); margin-bottom: 0; }
.evidence-actions { display: flex; gap: var(--space-xs); }
.evidence-search { display: flex; gap: var(--space-xs); margin-bottom: var(--space-sm); }
.evidence-options { max-height: 260px; overflow: auto; border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.evidence-option { display: flex; align-items: center; gap: var(--space-xs); padding: 8px 12px; border-bottom: 1px solid var(--color-border-light); }
.ordered-preview { max-height: 180px; overflow: auto; }
@media (max-width: 900px) {
  .actions-layout { grid-template-columns: 1fr; }
  .evidence-item { grid-template-columns: 34px minmax(0, 1fr); }
  .evidence-actions { grid-column: 2; flex-wrap: wrap; }
}
</style>
