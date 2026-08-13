<template>
  <div class="materials-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">资料中心</h1>
        <p class="text-secondary text-small">
          图片支持 PNG/JPEG/WebP，最大 10 MB、最长边 12,000 像素、总计 4,000 万像素；后端完整解码后才保存。OCR 只使用本机 Tesseract。
        </p>
      </div>
      <div class="head-actions">
        <el-button :disabled="selectedIds.length === 0" @click="openActionProject">建立行动专题（{{ selectedIds.length }}）</el-button>
        <el-button :disabled="selectedIds.length < 2" @click="openComparison">比较所选（{{ selectedIds.length }}）</el-button>
        <el-button @click="showDiscovery = true">发现 arXiv 候选</el-button>
        <el-button @click="showUrlImport = true">导入公开 URL</el-button>
        <el-button @click="imageInput?.click()">导入图片</el-button>
        <input ref="imageInput" class="hidden-input" type="file" accept="image/png,image/jpeg,image/webp" @change="uploadImage" />
        <el-button type="primary" @click="showImport = true">导入文字</el-button>
      </div>
    </div>

    <WorkspaceManager
      :paper-count="total"
      unit="项"
      @workspace-changed="reloadWorkspace"
      @clear="confirmClear"
    />

    <section v-if="pendingCandidates.length || failedCollectionJobs.length" class="candidate-box card">
      <div class="candidate-head">
        <div>
          <h2>候选箱</h2>
          <p class="text-small text-secondary">网页或公开 API 结果不会自动进入资料库，请检查后明确接受或拒绝。</p>
        </div>
        <el-button size="small" :loading="candidatesLoading" @click="loadCandidateData">刷新</el-button>
      </div>
      <el-alert
        v-for="job in failedCollectionJobs"
        :key="`job-${job.id}`"
        type="error"
        :title="job.error_message || '公开来源任务失败'"
        :description="job.query?.url || job.query?.query"
        show-icon
        :closable="false"
      />
      <article v-for="candidate in pendingCandidates" :key="candidate.id" class="candidate-card">
        <div class="candidate-main">
          <h3>{{ candidate.title }}</h3>
          <a :href="candidate.source_url" target="_blank" rel="noopener noreferrer">{{ candidate.source_url }}</a>
          <p>{{ candidate.summary }}</p>
          <span class="text-small text-secondary">
            采集器：{{ candidate.source_facts?.collector }}
            <template v-if="candidate.source_facts?.authors?.length"> · 作者：{{ candidate.source_facts.authors.join('、') }}</template>
            <template v-if="candidate.source_facts?.categories?.length"> · 分类：{{ candidate.source_facts.categories.join('、') }}</template>
            <template v-if="candidate.source_facts?.charset"> · 字符集：{{ candidate.source_facts.charset }}</template>
            <template v-if="candidate.source_facts?.redirect_count"> · 重定向：{{ candidate.source_facts.redirect_count }} 次</template>
            · {{ formatTime(candidate.created_at) }}
          </span>
        </div>
        <div class="candidate-actions">
          <el-button size="small" @click="rejectUrlCandidate(candidate)">拒绝</el-button>
          <el-button size="small" type="primary" @click="acceptUrlCandidate(candidate)">接受入库</el-button>
        </div>
      </article>
    </section>

    <div class="filters card">
      <el-input
        v-model="filters.q"
        placeholder="搜索标题或正文"
        clearable
        @keyup.enter="applyFilters"
        @clear="applyFilters"
      />
      <el-checkbox v-model="filters.include_accepted_extractions" border>
        同时搜索已接受提取文本
      </el-checkbox>
      <el-select v-model="filters.item_type" placeholder="全部类型" clearable @change="applyFilters">
        <el-option v-for="option in typeOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-select v-model="filters.status" placeholder="全部状态" clearable @change="applyFilters">
        <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-input
        v-if="filters.item_type === 'debug'"
        v-model="filters.debug_error"
        placeholder="按 Debug 错误字段筛选"
        clearable
        @keyup.enter="applyFilters"
        @clear="applyFilters"
      />
      <template v-if="filters.item_type === 'job'">
        <el-input
          v-model="filters.job_company"
          placeholder="按公司筛选"
          clearable
          @keyup.enter="applyFilters"
          @clear="applyFilters"
        />
        <el-input
          v-model="filters.job_role"
          placeholder="按岗位筛选"
          clearable
          @keyup.enter="applyFilters"
          @clear="applyFilters"
        />
        <el-input
          v-model="filters.job_application_status"
          placeholder="按投递状态筛选"
          clearable
          @keyup.enter="applyFilters"
          @clear="applyFilters"
        />
      </template>
      <el-button @click="applyFilters">搜索</el-button>
    </div>

    <div v-if="loading" class="empty-state">正在加载资料…</div>
    <div v-else-if="items.length === 0" class="empty-state card">
      <div class="empty-state-icon">🗂️</div>
      <p>当前工作区还没有通用资料</p>
      <p class="text-small text-secondary">先导入一段文字，系统会进行规范化、去重和类型建议。</p>
    </div>

    <div v-else class="material-list">
      <article v-for="item in items" :key="item.id" class="material-card card">
        <el-checkbox :model-value="selectedIds.includes(item.id)" @change="toggleSelection(item.id, $event)" />
        <div class="material-main" @click="openDetail(item)">
          <div class="material-meta">
            <el-tag size="small">{{ typeLabel(item.item_type) }}</el-tag>
            <el-tag v-if="item.has_accepted_extraction" size="small" type="success">含已接受提取</el-tag>
            <span>{{ formatTime(item.created_at) }}</span>
          </div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.summary }}</p>
          <div v-if="item.tags.length" class="tag-list">
            <el-tag v-for="tag in item.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
          </div>
        </div>
        <el-select
          :model-value="item.status"
          size="small"
          class="status-select"
          @change="changeStatus(item, $event)"
        >
          <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </article>
    </div>

    <div v-if="total > pageSize" class="pagination-row">
      <el-pagination
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="changePage"
      />
    </div>

    <el-dialog v-model="showImport" title="导入文字资料" width="680px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="正文">
          <el-input v-model="draft.content_text" type="textarea" :rows="10" maxlength="200000" show-word-limit />
        </el-form-item>
        <el-form-item label="标题（可选）">
          <el-input v-model="draft.title" maxlength="300" placeholder="留空时使用第一行" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="资料类型">
            <el-select v-model="draft.item_type">
              <el-option label="自动建议" value="auto" />
              <el-option v-for="option in typeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="标签（逗号分隔）">
            <el-input v-model="draft.tags" placeholder="例如：Python, 待整理" />
          </el-form-item>
        </div>
        <el-form-item label="来源 URL（可选，仅记录，不会自动访问）">
          <el-input v-model="draft.source_url" placeholder="https://example.com/source" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImport = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!draft.content_text.trim()" @click="saveText">保存资料</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showUrlImport" title="导入单个公开 URL" width="620px" :close-on-click-modal="false">
      <p class="text-small text-secondary">
        后端只读取一个公开 HTML 页面，检查 robots 策略，并限制重定向、超时和大小；不会登录、下载附件或自动入库。
      </p>
      <el-form label-position="top">
        <el-form-item label="公开网页 URL">
          <el-input v-model="urlDraft" maxlength="2000" placeholder="https://example.com/article" @keyup.enter="submitUrlImport" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUrlImport = false">取消</el-button>
        <el-button type="primary" :loading="urlImporting" :disabled="!urlDraft.trim()" @click="submitUrlImport">读取并加入候选箱</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDiscovery" title="从 arXiv 公开 API 发现候选" width="620px" :close-on-click-modal="false">
      <p class="text-small text-secondary">
        仅向 arXiv 官方公开 API 发送下方搜索词，最多返回 20 条摘要元数据；结果先进入候选箱，不下载 PDF，也不会自动入库。
      </p>
      <el-form label-position="top">
        <el-form-item label="搜索词">
          <el-input v-model="discoveryDraft.query" maxlength="200" placeholder="例如：local retrieval" @keyup.enter="submitDiscovery" />
        </el-form-item>
        <el-form-item label="结果上限">
          <el-input-number v-model="discoveryDraft.limit" :min="1" :max="20" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDiscovery = false">取消</el-button>
        <el-button type="primary" :loading="discovering" :disabled="!discoveryDraft.query.trim()" @click="submitDiscovery">搜索并加入候选箱</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDetail" :title="selected?.title || '资料详情'" width="720px">
      <template v-if="selected">
        <div class="detail-meta">
          <el-tag>{{ typeLabel(selected.item_type) }}</el-tag>
          <span>状态：{{ statusLabel(selected.status) }}</span>
          <a v-if="selected.source_url" :href="selected.source_url" target="_blank" rel="noopener noreferrer">查看来源</a>
        </div>
        <pre class="material-content">{{ selected.content_text }}</pre>
        <div v-if="selected.assets?.length" class="asset-list">
          <img v-for="asset in selected.assets" :key="asset.id" :src="`/api/assets/${asset.id}/content`" :alt="asset.original_name" />
          <p class="text-small text-secondary">
            每次点击都会新建一条本地 OCR 审计运行；不会复用旧成功结果，也不会自动更改已接受文本。
          </p>
          <el-button :loading="ocrRunning" @click="runOcr">{{ hasOcrRuns ? '重新运行本地 OCR' : '运行本地 OCR' }}</el-button>
        </div>
        <section v-if="latestOcrRun" class="accepted-extraction-panel">
          <el-divider />
          <div class="section-head">
            <div>
              <h3>OCR 提取预览</h3>
              <p class="text-small text-secondary">
                先检查本地 OCR 文本，再明确接受到独立提取层；不会改写原始资料正文。
              </p>
            </div>
            <el-tag v-if="acceptedOcr?.run_id === latestOcrRun.id" type="success">当前已接受</el-tag>
          </div>
          <pre class="extraction-preview">{{ latestOcrRun.result.text }}</pre>
          <el-button
            type="primary"
            :loading="acceptingExtraction"
            :disabled="acceptedOcr?.run_id === latestOcrRun.id"
            @click="acceptOcrExtraction(latestOcrRun)"
          >接受此 OCR 文本</el-button>
          <p v-if="acceptedOcr && acceptedOcr.run_id !== latestOcrRun.id" class="text-small text-secondary">
            当前接受的是运行 #{{ acceptedOcr.run_id }}；接受此预览后将更新当前采用版本，历史运行仍保留。
          </p>
        </section>
        <el-divider />
        <p class="text-small text-secondary">
          类型建议：{{ typeLabel(selected.metadata?.classification?.suggested_type || 'general') }}
          · 方法：{{ selected.metadata?.classification?.method || '未知' }}
        </p>
        <section v-if="templateDefinition" class="template-panel">
          <el-divider />
          <div class="section-head">
            <div>
              <h3>{{ templateDefinition.title }}</h3>
              <p class="text-small text-secondary">本地规则提取与用户确认分层保存；重新提取不会覆盖确认值。</p>
            </div>
            <el-button size="small" :loading="templateExtracting" @click="rerunTemplateExtraction">重新本地提取</el-button>
          </div>
          <p v-if="templateLoading" class="text-small text-secondary">正在加载模板…</p>
          <el-form v-else-if="itemTemplate" label-position="top">
            <el-form-item v-for="field in templateDefinition.fields" :key="field.key" :label="field.label">
              <el-input
                v-model="templateDraft[field.key]"
                type="textarea"
                :rows="2"
                :placeholder="itemTemplate.extracted?.[field.key] || '本地规则未提取到内容'"
                maxlength="4000"
              />
              <p class="field-source text-small text-secondary">
                本地提取：{{ itemTemplate.extracted?.[field.key] || '—' }}
                <span v-if="itemTemplate.confirmed?.[field.key]"> · 当前采用用户确认值</span>
              </p>
            </el-form-item>
            <el-button type="primary" :loading="templateSaving" @click="saveTemplateConfirmation">保存用户确认值</el-button>
          </el-form>
        </section>
        <section class="similar-panel">
          <el-divider />
          <div class="section-head">
            <div>
              <h3>本地相似资料</h3>
              <p class="text-small text-secondary">使用可解释的 token Jaccard 算法，不会发送到外部服务。</p>
            </div>
            <el-button size="small" :loading="similarLoading" @click="loadSimilarItems">查找相似资料</el-button>
          </div>
          <p v-if="similarSearched && similarMatches.length === 0" class="text-small text-secondary">未找到达到阈值的相似资料。</p>
          <article v-for="match in similarMatches" :key="match.item.id" class="similar-card">
            <strong>#{{ match.item.id }} {{ match.item.title }}</strong>
            <span>相似度 {{ Math.round(match.score * 100) }}%</span>
            <p class="text-small text-secondary">共同特征：{{ match.evidence.shared_tokens.join('、') || '无' }}</p>
          </article>
        </section>
        <el-divider />
        <section class="analysis-panel">
          <h3>显式 AI 分析</h3>
          <p class="text-small text-secondary">只有点击运行后，勾选字段才会发送给设置中的模型。正文最多发送前 12,000 个字符。</p>
          <el-form label-position="top">
            <el-form-item label="分析类型">
              <el-radio-group v-model="analysisDraft.analysis_type">
                <el-radio-button value="classify">类型建议</el-radio-button>
                <el-radio-button value="extract">摘要与字段提取</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="确认发送字段范围">
              <el-checkbox-group v-model="analysisDraft.input_fields">
                <el-checkbox value="title">标题</el-checkbox>
                <el-checkbox value="content_text">正文</el-checkbox>
                <el-checkbox value="accepted_extraction" :disabled="!acceptedExtractionText">已接受提取文本</el-checkbox>
                <el-checkbox value="item_type">当前类型</el-checkbox>
                <el-checkbox value="tags">标签</el-checkbox>
                <el-checkbox value="source_url">来源 URL</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-button
              type="primary"
              :loading="analyzing"
              :disabled="analysisDraft.input_fields.length === 0"
              @click="runAnalysis"
            >确认范围并运行</el-button>
          </el-form>

          <div class="run-history">
            <h3>运行历史</h3>
            <p v-if="runsLoading" class="text-secondary text-small">正在加载…</p>
            <p v-else-if="analysisRuns.length === 0" class="text-secondary text-small">尚无分析记录。</p>
            <article v-for="run in analysisRuns" :key="run.id" class="run-card">
              <div class="run-head">
                <el-tag :type="run.status === 'succeeded' ? 'success' : run.status === 'failed' ? 'danger' : 'warning'">
                  {{ runStatusLabel(run.status) }}
                </el-tag>
                <strong>{{ runKindLabel(run.run_kind) }}</strong>
                <span>{{ formatTime(run.created_at) }}</span>
              </div>
              <p class="text-small text-secondary">
                范围：{{ scopeLabel(run.input_scope) }} · {{ run.provider }}/{{ run.model }} · 提示词 {{ run.prompt_version }}
              </p>
              <p v-if="run.provider_model || run.input_tokens != null || run.output_tokens != null || run.duration_ms != null" class="text-small text-secondary">
                服务商返回：{{ run.provider_model || '未提供模型名' }}
                · token {{ run.input_tokens ?? '—' }}/{{ run.output_tokens ?? '—' }}
                · {{ run.duration_ms ?? '—' }} ms
                <span v-if="run.request_id"> · 请求 {{ run.request_id }}</span>
              </p>
              <p v-if="run.error_message" class="run-error">{{ run.error_message }}</p>
              <pre v-if="run.result" class="run-result">{{ formatResult(run.result) }}</pre>
            </article>
          </div>
        </section>
      </template>
    </el-dialog>

    <el-dialog v-model="showComparison" title="比较所选资料" width="760px">
      <p class="text-secondary text-small">将发送下列 {{ comparisonItems.length }} 条资料；每条正文最多发送前 3,000 个字符，总数限制为 2–20 条。</p>
      <ol class="comparison-list">
        <li v-for="item in comparisonItems" :key="item.id">#{{ item.id }} {{ item.title }}</li>
      </ol>
      <el-form-item label="确认发送字段范围">
        <el-checkbox-group v-model="comparisonFields">
          <el-checkbox value="title">标题</el-checkbox>
          <el-checkbox value="content_text">正文</el-checkbox>
          <el-checkbox value="accepted_extraction">各资料已接受提取文本（没有则为空）</el-checkbox>
          <el-checkbox value="item_type">类型</el-checkbox>
          <el-checkbox value="tags">标签</el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-button type="primary" :loading="comparing" :disabled="comparisonFields.length === 0" @click="runComparison">确认清单并比较</el-button>
      <div class="run-history">
        <h3>比较历史</h3>
        <article v-for="run in comparisonRuns" :key="run.id" class="run-card">
          <div class="run-head"><el-tag :type="run.status === 'succeeded' ? 'success' : 'danger'">{{ runStatusLabel(run.status) }}</el-tag><span>资料 {{ run.input_item_ids?.join('、') }}</span></div>
          <p class="text-small text-secondary">范围：{{ scopeLabel(run.input_scope) }} · 每条正文最多 3,000 字符 · {{ run.provider }}/{{ run.model }}</p>
          <p v-if="run.provider_model || run.input_tokens != null || run.output_tokens != null || run.duration_ms != null" class="text-small text-secondary">
            服务商返回：{{ run.provider_model || '未提供模型名' }}
            · token {{ run.input_tokens ?? '—' }}/{{ run.output_tokens ?? '—' }}
            · {{ run.duration_ms ?? '—' }} ms
            <span v-if="run.request_id"> · 请求 {{ run.request_id }}</span>
          </p>
          <p v-if="run.error_message" class="run-error">{{ run.error_message }}</p>
          <pre v-if="run.result" class="run-result">{{ formatResult(run.result) }}</pre>
        </article>
      </div>
    </el-dialog>

    <el-dialog v-model="showActionProject" title="从所选资料建立行动专题" width="680px" :close-on-click-modal="false">
      <p class="text-secondary text-small">
        下列资料将按当前选择顺序成为证据。专题只保存你的组织、笔记和下一步，不会修改资料来源事实。
      </p>
      <ol class="comparison-list">
        <li v-for="item in actionProjectItems" :key="item.id">#{{ item.id }} {{ item.title }}</li>
      </ol>
      <el-form label-position="top">
        <el-form-item label="专题标题">
          <el-input v-model="actionProjectDraft.title" maxlength="200" />
        </el-form-item>
        <el-form-item label="目标">
          <el-input v-model="actionProjectDraft.objective" type="textarea" :rows="2" maxlength="2000" />
        </el-form-item>
        <el-form-item label="用户笔记">
          <el-input v-model="actionProjectDraft.notes" type="textarea" :rows="4" maxlength="12000" />
        </el-form-item>
        <el-form-item label="明确下一步">
          <el-input v-model="actionProjectDraft.next_action" maxlength="1000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showActionProject = false">取消</el-button>
        <el-button
          type="primary"
          :loading="creatingActionProject"
          :disabled="!actionProjectDraft.title.trim() || actionProjectItems.length === 0"
          @click="submitActionProject"
        >创建并打开专题</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import WorkspaceManager from '@/components/WorkspaceManager.vue'
import { useWorkspaceStore } from '@/stores/workspace'
import {
  acceptCandidate,
  acceptItemExtraction,
  clearWorkspace,
  createActionProject,
  createItem,
  createItemAnalysisRun,
  createComparisonRun,
  confirmItemTemplate,
  discoverArxiv,
  extractItemTemplate,
  fetchComparisonRuns,
  fetchCollectionJobs,
  fetchItem,
  fetchItemAnalysisRuns,
  fetchItemTemplate,
  fetchItems,
  fetchSimilarItems,
  fetchCandidates,
  importImage,
  createUrlImport,
  rejectCandidate,
  runItemOcr,
  updateItem,
} from '@/api'

const typeOptions = [
  { label: '通用', value: 'general' },
  { label: '论文', value: 'paper' },
  { label: '求职', value: 'job' },
  { label: 'Debug', value: 'debug' },
]
const workspaceStore = useWorkspaceStore()
const route = useRoute()
const router = useRouter()
const statusOptions = [
  { label: '收件箱', value: 'inbox' },
  { label: '处理中', value: 'active' },
  { label: '已归档', value: 'archived' },
]

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const saving = ref(false)
const showImport = ref(false)
const showDetail = ref(false)
const selected = ref(null)
const analyzing = ref(false)
const runsLoading = ref(false)
const analysisRuns = ref([])
const selectedIds = ref([])
const showActionProject = ref(false)
const creatingActionProject = ref(false)
const actionProjectDraft = reactive({ title: '', objective: '', notes: '', next_action: '' })
const imageInput = ref(null)
const ocrRunning = ref(false)
const acceptingExtraction = ref(false)
const showComparison = ref(false)
const comparing = ref(false)
const comparisonRuns = ref([])
const comparisonFields = ref(['title', 'content_text'])
const showUrlImport = ref(false)
const urlDraft = ref('')
const urlImporting = ref(false)
const candidatesLoading = ref(false)
const pendingCandidates = ref([])
const failedCollectionJobs = ref([])
const showDiscovery = ref(false)
const discovering = ref(false)
const discoveryDraft = reactive({ query: '', limit: 10 })
const itemTemplate = ref(null)
const templateLoading = ref(false)
const templateExtracting = ref(false)
const templateSaving = ref(false)
const templateDraft = reactive({})
const templateDefinitions = {
  debug: {
    title: 'Debug 模板',
    fields: [
      { key: 'error', label: '错误' }, { key: 'environment', label: '环境' },
      { key: 'attempts', label: '尝试' }, { key: 'root_cause', label: '根因' },
      { key: 'solution', label: '最终方案' },
    ],
  },
  job: {
    title: '求职模板',
    fields: [
      { key: 'company', label: '公司' }, { key: 'role', label: '岗位' },
      { key: 'location', label: '地区' }, { key: 'salary', label: '薪资' },
      { key: 'skills', label: '技能' }, { key: 'experience', label: '经验年限' },
      { key: 'application_status', label: '投递状态' },
    ],
  },
}
const templateDefinition = computed(() => templateDefinitions[selected.value?.item_type] || null)
const similarLoading = ref(false)
const similarSearched = ref(false)
const similarMatches = ref([])
const filters = reactive({
  q: '', item_type: '', status: '', debug_error: '', job_company: '', job_role: '',
  job_application_status: '', include_accepted_extractions: false,
})
const draft = reactive({ content_text: '', title: '', item_type: 'auto', tags: '', source_url: '' })
const analysisDraft = reactive({ analysis_type: 'classify', input_fields: ['title', 'content_text'] })
const latestOcrRun = computed(() => analysisRuns.value.find(
  (run) => run.run_kind === 'ocr' && run.status === 'succeeded' && run.result?.text,
))
const hasOcrRuns = computed(() => analysisRuns.value.some((run) => run.run_kind === 'ocr'))
const acceptedOcr = computed(() => selected.value?.accepted_extractions?.find(
  (entry) => entry.extraction_kind === 'ocr',
))
const acceptedExtractionText = computed(() => (
  selected.value?.accepted_extractions || []
).map((entry) => entry.text_value).filter(Boolean).join('\n\n'))

function typeLabel(value) {
  return typeOptions.find((option) => option.value === value)?.label || '通用'
}
function statusLabel(value) {
  return statusOptions.find((option) => option.value === value)?.label || value
}
function formatTime(value) {
  return value ? value.slice(0, 16) : ''
}

async function loadItems() {
  loading.value = true
  try {
    const result = await fetchItems({
      q: filters.q || undefined,
      item_type: filters.item_type || undefined,
      status: filters.status || undefined,
      debug_error: filters.item_type === 'debug' ? filters.debug_error || undefined : undefined,
      job_company: filters.item_type === 'job' ? filters.job_company || undefined : undefined,
      job_role: filters.item_type === 'job' ? filters.job_role || undefined : undefined,
      job_application_status: filters.item_type === 'job' ? filters.job_application_status || undefined : undefined,
      include_accepted_extractions: filters.include_accepted_extractions || undefined,
      page: page.value,
      page_size: pageSize,
    })
    items.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '资料加载失败')
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  selectedIds.value = []
  loadItems()
}
function changePage(value) {
  page.value = value
  selectedIds.value = []
  loadItems()
}
function reloadWorkspace() {
  page.value = 1
  selectedIds.value = []
  showDetail.value = false
  showComparison.value = false
  selected.value = null
  itemTemplate.value = null
  analysisRuns.value = []
  Object.assign(analysisDraft, { analysis_type: 'classify', input_fields: ['title', 'content_text'] })
  loadItems()
  loadCandidateData()
}

async function loadCandidateData() {
  candidatesLoading.value = true
  try {
    const [candidateResult, jobResult] = await Promise.all([
      fetchCandidates({ status: 'pending' }),
      fetchCollectionJobs(),
    ])
    pendingCandidates.value = candidateResult.candidates || []
    failedCollectionJobs.value = (jobResult.jobs || []).filter((job) => job.status === 'failed').slice(0, 3)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '候选箱加载失败')
  } finally { candidatesLoading.value = false }
}

async function submitUrlImport() {
  urlImporting.value = true
  try {
    await createUrlImport(urlDraft.value.trim())
    urlDraft.value = ''
    showUrlImport.value = false
    await loadCandidateData()
    ElMessage.success('网页已提取，请在候选箱检查后决定是否入库')
  } catch (error) {
    await loadCandidateData()
    ElMessage.error(error.response?.data?.detail || '公开 URL 导入失败')
  } finally { urlImporting.value = false }
}

async function submitDiscovery() {
  discovering.value = true
  try {
    const result = await discoverArxiv(discoveryDraft.query.trim(), discoveryDraft.limit)
    showDiscovery.value = false
    await loadCandidateData()
    ElMessage.success(`发现 ${result.candidates?.length || 0} 条结果，请在候选箱审核`)
  } catch (error) {
    await loadCandidateData()
    ElMessage.error(error.response?.data?.detail || 'arXiv 发现失败')
  } finally { discovering.value = false }
}

async function acceptUrlCandidate(candidate) {
  try {
    const result = await acceptCandidate(candidate.id)
    await Promise.all([loadCandidateData(), loadItems()])
    ElMessage.success(result.duplicate ? '内容已存在，候选已关联到已有资料' : '候选已正式入库')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '候选入库失败')
  }
}

async function rejectUrlCandidate(candidate) {
  try {
    await rejectCandidate(candidate.id)
    await loadCandidateData()
    ElMessage.success('候选已拒绝')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '候选拒绝失败')
  }
}
async function openDetail(item) {
  try {
    selected.value = await fetchItem(item.id)
    if (!(selected.value.accepted_extractions || []).some((entry) => entry.text_value)) {
      analysisDraft.input_fields = analysisDraft.input_fields.filter(
        (field) => field !== 'accepted_extraction',
      )
    }
    showDetail.value = true
    itemTemplate.value = null
    similarMatches.value = []
    similarSearched.value = false
    await Promise.all([loadAnalysisRuns(), templateDefinition.value ? loadItemTemplate() : Promise.resolve()])
  } catch (error) {
    showDetail.value = false
    ElMessage.error(error.response?.data?.detail || '资料详情加载失败')
  }
}

function applyTemplate(template) {
  itemTemplate.value = template
  for (const key of Object.keys(templateDraft)) delete templateDraft[key]
  for (const field of templateDefinition.value?.fields || []) {
    templateDraft[field.key] = template.confirmed?.[field.key] || ''
  }
}

async function loadItemTemplate() {
  templateLoading.value = true
  try {
    applyTemplate(await fetchItemTemplate(selected.value.id))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '模板加载失败')
  } finally { templateLoading.value = false }
}

async function rerunTemplateExtraction() {
  templateExtracting.value = true
  try {
    applyTemplate(await extractItemTemplate(selected.value.id))
    await loadAnalysisRuns()
    ElMessage.success('本地规则提取完成，用户确认值已保留')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '模板提取失败')
  } finally { templateExtracting.value = false }
}

async function saveTemplateConfirmation() {
  templateSaving.value = true
  try {
    applyTemplate(await confirmItemTemplate(selected.value.id, { ...templateDraft }))
    ElMessage.success('用户确认值已保存')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '确认值保存失败')
  } finally { templateSaving.value = false }
}

async function loadSimilarItems() {
  similarLoading.value = true
  try {
    const result = await fetchSimilarItems(selected.value.id, { threshold: 0.2, limit: 10 })
    similarMatches.value = result.matches || []
    similarSearched.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '相似资料检索失败')
  } finally { similarLoading.value = false }
}

function toggleSelection(id, checked) {
  if (checked && selectedIds.value.length >= 20) {
    ElMessage.warning('最多选择 20 条资料')
    return
  }
  selectedIds.value = checked
    ? [...selectedIds.value, id].slice(0, 20)
    : selectedIds.value.filter((value) => value !== id)
}
const comparisonItems = computed(() => items.value.filter((item) => selectedIds.value.includes(item.id)))
const actionProjectItems = computed(() => selectedIds.value.map(
  (id) => items.value.find((item) => item.id === id),
).filter(Boolean))

function openActionProject() {
  if (actionProjectItems.value.length === 0) return
  Object.assign(actionProjectDraft, {
    title: '', objective: '', notes: '', next_action: '',
  })
  showActionProject.value = true
}

async function submitActionProject() {
  creatingActionProject.value = true
  try {
    const result = await workspaceStore.runMutation(() => createActionProject({
      ...actionProjectDraft,
      item_ids: actionProjectItems.value.map((item) => item.id),
    }))
    showActionProject.value = false
    selectedIds.value = []
    ElMessage.success('行动专题已创建')
    await router.push({ path: '/actions', query: { project: result.project.id } })
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '行动专题创建失败')
  } finally { creatingActionProject.value = false }
}

async function openComparison() {
  showComparison.value = true
  const result = await fetchComparisonRuns()
  comparisonRuns.value = result.runs || []
}

async function runComparison() {
  comparing.value = true
  try {
    const result = await createComparisonRun({ item_ids: selectedIds.value, input_fields: comparisonFields.value })
    const history = await fetchComparisonRuns()
    comparisonRuns.value = history.runs || []
    ElMessage.success(result.reused ? '已复用相同输入的比较结果' : '比较完成')
  } catch (error) {
    const history = await fetchComparisonRuns().catch(() => ({ runs: [] }))
    comparisonRuns.value = history.runs || []
    ElMessage.error(error.response?.data?.detail || '比较失败')
  } finally { comparing.value = false }
}

async function uploadImage(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('图片不能超过 10 MB')
    event.target.value = ''
    return
  }
  try {
    const result = await importImage(file)
    await loadItems()
    ElMessage.success(result.duplicate ? '相同图片已存在' : '图片已保存到本地工作区')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '图片导入失败')
  } finally { event.target.value = '' }
}

async function runOcr() {
  ocrRunning.value = true
  try {
    await runItemOcr(selected.value.id)
    await loadAnalysisRuns()
    ElMessage.success('新的 OCR 审计运行已完成；已接受文本未改变')
  } catch (error) {
    await loadAnalysisRuns()
    ElMessage.error(error.response?.data?.detail || '本地 OCR 失败')
  } finally { ocrRunning.value = false }
}

async function acceptOcrExtraction(run) {
  acceptingExtraction.value = true
  try {
    await acceptItemExtraction(selected.value.id, run.id)
    selected.value = await fetchItem(selected.value.id)
    await loadItems()
    ElMessage.success('OCR 文本已接受到独立提取层')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '接受提取结果失败')
  } finally { acceptingExtraction.value = false }
}

async function loadAnalysisRuns() {
  if (!selected.value) return
  runsLoading.value = true
  try {
    const result = await fetchItemAnalysisRuns(selected.value.id)
    analysisRuns.value = result.runs || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '分析历史加载失败')
  } finally {
    runsLoading.value = false
  }
}

async function runAnalysis() {
  analyzing.value = true
  try {
    const result = await createItemAnalysisRun(selected.value.id, {
      analysis_type: analysisDraft.analysis_type,
      input_fields: analysisDraft.input_fields,
    })
    await loadAnalysisRuns()
    ElMessage.success(result.reused ? '输入未变化，已显示已有成功结果' : '分析完成，结果已记录为建议')
  } catch (error) {
    await loadAnalysisRuns()
    ElMessage.error(error.response?.data?.detail || 'AI 分析失败')
  } finally {
    analyzing.value = false
  }
}

function runStatusLabel(value) {
  return { running: '运行中', succeeded: '成功', failed: '失败' }[value] || value
}
function runKindLabel(value) {
  return {
    classify: '类型建议',
    extract: '摘要与字段提取',
    ocr: '本地 OCR',
    template_extract: '本地模板提取',
  }[value] || value
}
function scopeLabel(fields = []) {
  const labels = {
    title: '标题', content_text: '正文', accepted_extraction: '已接受提取文本',
    item_type: '当前类型', tags: '标签', source_url: '来源 URL',
  }
  return fields.map((field) => labels[field] || field).join('、')
}
function formatResult(result) {
  return JSON.stringify(result, null, 2)
}

async function saveText() {
  saving.value = true
  try {
    const result = await createItem({
      content_text: draft.content_text,
      title: draft.title || null,
      item_type: draft.item_type,
      source_url: draft.source_url || null,
      tags: draft.tags.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean),
    })
    showImport.value = false
    resetDraft()
    await loadItems()
    if (result.duplicate) {
      ElMessage.info(`已存在相同资料：${result.item.title}`)
    } else {
      ElMessage.success(`已保存为“${typeLabel(result.item.item_type)}”资料`)
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '资料保存失败')
  } finally {
    saving.value = false
  }
}

async function changeStatus(item, status) {
  const previous = item.status
  item.status = status
  try {
    const updated = await updateItem(item.id, { status })
    Object.assign(item, updated)
  } catch {
    item.status = previous
    ElMessage.error('状态更新失败')
  }
}

async function confirmClear() {
  try {
    await ElMessageBox.confirm('确定清空当前工作区的全部资料和论文数据？此操作不可恢复。', '确认清空', {
      confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning',
    })
    await clearWorkspace()
    await workspaceStore.refreshCurrentWorkspace()
    await loadItems()
    ElMessage.success('当前工作区已清空')
  } catch { /* cancelled */ }
}

function resetDraft() {
  Object.assign(draft, { content_text: '', title: '', item_type: 'auto', tags: '', source_url: '' })
}

onMounted(async () => {
  await Promise.all([loadItems(), loadCandidateData()])
  const requestedItemId = Number(route.query.item)
  if (Number.isInteger(requestedItemId) && requestedItemId > 0) {
    await openDetail({ id: requestedItemId })
  }
})
</script>

<style scoped>
.materials-page { padding-top: var(--space-lg); }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-md); }
.head-actions { display: flex; gap: var(--space-xs); flex-wrap: wrap; }
.hidden-input { display: none; }
.candidate-box { margin-bottom: var(--space-lg); }
.candidate-head, .candidate-card { display: flex; justify-content: space-between; gap: var(--space-md); align-items: flex-start; }
.candidate-head h2, .candidate-main h3 { margin-top: 0; }
.candidate-card { padding: var(--space-sm) 0; border-top: 1px solid var(--color-border); }
.candidate-main { min-width: 0; flex: 1; }
.candidate-main a { overflow-wrap: anywhere; }
.candidate-actions { display: flex; gap: var(--space-xs); flex-shrink: 0; }
.filters { display: grid; grid-template-columns: 1fr 150px 150px auto; gap: var(--space-sm); margin-bottom: var(--space-lg); }
.material-list { display: flex; flex-direction: column; gap: var(--space-sm); }
.material-card { display: flex; justify-content: space-between; gap: var(--space-lg); align-items: flex-start; }
.material-card:hover { transform: none; }
.material-main { flex: 1; min-width: 0; cursor: pointer; }
.material-main h3 { margin: 8px 0; font-size: var(--font-size-md); }
.material-main p { color: var(--color-text-secondary); line-height: 1.6; }
.material-meta, .detail-meta, .tag-list { display: flex; align-items: center; gap: var(--space-xs); flex-wrap: wrap; font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.status-select { width: 110px; flex-shrink: 0; }
.pagination-row { display: flex; justify-content: center; padding: var(--space-lg); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md); }
.section-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-sm); }
.section-head h3 { margin-top: 0; }
.field-source { width: 100%; margin: 4px 0 0; white-space: pre-wrap; }
.similar-card { border-top: 1px solid var(--color-border); padding: var(--space-sm) 0; }
.similar-card span { margin-left: var(--space-sm); color: var(--color-text-secondary); }
.material-content { white-space: pre-wrap; word-break: break-word; font-family: inherit; line-height: 1.7; max-height: 55vh; overflow: auto; margin-top: var(--space-md); }
.analysis-panel h3 { margin: var(--space-sm) 0; }
.run-history { margin-top: var(--space-lg); }
.run-card { border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-sm); margin-top: var(--space-sm); }
.run-head { display: flex; align-items: center; gap: var(--space-xs); font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.run-error { color: var(--el-color-danger); white-space: pre-wrap; }
.run-result { white-space: pre-wrap; word-break: break-word; overflow: auto; background: var(--color-bg-secondary); padding: var(--space-sm); border-radius: var(--radius-sm); }
.asset-list { display: flex; flex-direction: column; gap: var(--space-sm); margin-top: var(--space-md); }
.asset-list img { max-width: 100%; max-height: 420px; object-fit: contain; border: 1px solid var(--color-border); }
.accepted-extraction-panel { margin-top: var(--space-sm); }
.extraction-preview { white-space: pre-wrap; max-height: 260px; overflow: auto; background: var(--color-bg-secondary); padding: var(--space-sm); border-radius: var(--radius-sm); }
.comparison-list { max-height: 180px; overflow: auto; }
@media (max-width: 720px) {
  .filters, .form-grid { grid-template-columns: 1fr; }
  .material-card { flex-direction: column; }
}
</style>
