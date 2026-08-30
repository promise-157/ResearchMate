import axios from 'axios'
import { AI_REQUEST_TIMEOUT_MS, MAX_CART_ANALYSIS_PAPERS } from '../constants/aiLimits'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export function getApiErrorMessage(error, fallback = '请求失败') {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((entry) => entry?.msg).filter(Boolean)
    if (messages.length) return messages.join('；')
  }
  return error?.message || fallback
}

function cartAnalysisTimeout(paperCount) {
  const count = Math.max(1, Math.min(Number(paperCount) || 1, MAX_CART_ANALYSIS_PAPERS))
  return AI_REQUEST_TIMEOUT_MS * count
}

// 响应拦截：统一错误处理
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = getApiErrorMessage(err)
    console.error('[API Error]', msg)
    return Promise.reject(err)
  },
)

// ---- 期刊源 ----
export function fetchJournals() {
  return api.get('/journals')
}

export function addJournal(url, label) {
  return api.post('/journals', { url, label })
}

export function deleteJournal(id) {
  return api.delete(`/journals/${id}`)
}

// ---- 爬取 ----
export function startCrawl(sourceIds, mode = 'new', keywords = '', sortMode = 'newest') {
  return api.post('/crawl', { source_ids: sourceIds, mode, keywords, sort_mode: sortMode })
}

export function getCrawlStatus() {
  return api.get('/crawl/status')
}

// ---- 论文 ----
export function fetchPapers(params) {
  return api.get('/papers', { params })
}

export function fetchPaperDetail(id) {
  return api.get(`/papers/${id}`)
}

export function updatePaper(id, data) {
  return api.patch(`/papers/${id}`, data)
}

// ---- 通用资料 ----
export function fetchItems(params) {
  return api.get('/items', { params })
}

export function createItem(data) {
  return api.post('/items', data)
}

export function fetchItem(id) {
  return api.get(`/items/${id}`)
}

export function updateItem(id, data) {
  return api.patch(`/items/${id}`, data)
}

export function fetchItemAnalysisRuns(id) {
  return api.get(`/items/${id}/analysis-runs`)
}

export function createItemAnalysisRun(id, data) {
  return api.post(`/items/${id}/analysis-runs`, data)
}

export function fetchComparisonRuns() {
  return api.get('/items/analysis-comparisons')
}

export function createComparisonRun(data) {
  return api.post('/items/analysis-comparisons', data)
}

export function importImage(file, title = '') {
  const form = new FormData()
  form.append('file', file)
  form.append('title', title)
  return api.post('/items/import-image', form, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export function runItemOcr(id) {
  return api.post(`/items/${id}/ocr-runs`)
}

export function acceptItemExtraction(itemId, runId) {
  return api.post(`/items/${itemId}/extraction-runs/${runId}/accept`)
}

export function fetchItemTemplate(id) {
  return api.get(`/items/${id}/template`)
}

export function extractItemTemplate(id) {
  return api.post(`/items/${id}/template/extract`)
}

export function confirmItemTemplate(id, data) {
  return api.put(`/items/${id}/template/confirmation`, data)
}

export function fetchSimilarItems(id, params) {
  return api.get(`/items/${id}/similar`, { params })
}

export function fetchActionProjects() {
  return api.get('/action-projects')
}

export function createActionProject(data) {
  return api.post('/action-projects', data)
}

export function fetchActionProject(id) {
  return api.get(`/action-projects/${id}`)
}

export function updateActionProject(id, data) {
  return api.patch(`/action-projects/${id}`, data)
}

export function replaceActionProjectMaterials(id, itemIds) {
  return api.put(`/action-projects/${id}/materials`, { item_ids: itemIds })
}

export function createUrlImport(url) {
  return api.post('/url-imports', { url }, { timeout: 35000 })
}

export function fetchUrlImports() {
  return api.get('/url-imports')
}

export function discoverArxiv(query, limit = 10) {
  return api.post('/discoveries/arxiv', { query, limit }, { timeout: 30000 })
}

export function discoverCrossref(data) {
  return api.post('/discoveries/crossref', data, { timeout: 30000 })
}

export function enrichOpenAlex(candidateIds) {
  return api.post('/discoveries/openalex/enrich', { candidate_ids: candidateIds }, { timeout: 90000 })
}

export function checkCodeEvidence(candidateIds) {
  return api.post('/discoveries/code/evidence', { candidate_ids: candidateIds }, { timeout: 40000 })
}

export function rankDiscoveryCandidates(data) { return api.post('/discoveries/candidates/rank', data) }
export function fetchCandidateBriefs() { return api.get('/discoveries/candidates/briefs') }
export function createCandidateBrief(data) { return api.post('/discoveries/candidates/briefs', data, { timeout: 120000 }) }

export function fetchDiscoveryRules() { return api.get('/discovery-rules') }
export function saveDiscoveryRule(data) { return api.post('/discovery-rules', data) }
export function updateDiscoveryRule(id, data) { return api.put(`/discovery-rules/${id}`, data) }
export function runDiscoveryRule(id) { return api.post(`/discovery-rules/${id}/run`, undefined, { timeout: 30000 }) }
export function runAllDiscoveryRules() { return api.post('/discovery-rules/run', undefined, { timeout: 120000 }) }
export function deleteDiscoveryRule(id) { return api.delete(`/discovery-rules/${id}`) }

export function fetchCollectionJobs() {
  return api.get('/collection-jobs')
}

export function fetchCandidates(params) {
  return api.get('/candidates', { params })
}

export function acceptCandidate(id) {
  return api.post(`/candidates/${id}/accept`)
}

export function rejectCandidate(id) {
  return api.post(`/candidates/${id}/reject`)
}

// ---- 购物车 ----
export function fetchCart() {
  return api.get('/cart')
}

export function exportCart(format = 'csv') {
  return api.get('/cart/export', { params: { format } })
}

export function analyzeCartPapers(paperIds) {
  return api.post(
    '/cart/analyze',
    { paper_ids: paperIds },
    { timeout: cartAnalysisTimeout(paperIds?.length) },
  )
}

export function analyzeAllCart(paperCount = MAX_CART_ANALYSIS_PAPERS) {
  return api.post('/cart/analyze/all', undefined, { timeout: cartAnalysisTimeout(paperCount) })
}

export function fetchWorkspaceReviews() {
  return api.get('/workspace/reviews')
}

export function createWorkspaceReview(paperIds) {
  return api.post(
    '/workspace/reviews',
    { paper_ids: paperIds },
    { timeout: AI_REQUEST_TIMEOUT_MS },
  )
}

// ---- 设置 ----
export function fetchSettings() {
  return api.get('/settings')
}

export function updateSettings(data) {
  return api.put('/settings', data)
}

export function testAIConnection() {
  return api.post('/settings/ai/test', {}, { timeout: 35000 })
}

// ---- Audited paper chat ----
export function fetchChatSessions() {
  return api.get('/chat/sessions')
}

export function createChatSession(title = '新对话') {
  return api.post('/chat/sessions', { title })
}

export function fetchChatSession(id) {
  return api.get(`/chat/sessions/${id}`)
}

export function createChatTurn(id, data) {
  return api.post(`/chat/sessions/${id}/turns`, data, { timeout: AI_REQUEST_TIMEOUT_MS })
}

// ---- 统计 ----
export function fetchStats() {
  return api.get('/stats')
}

export function fetchLatestSession() {
  return api.get('/sessions/latest')
}

export function fetchDoc(name) {
  return api.get(`/docs/${name}`)
}

// ---- 关键词 ----
export function fetchKeywords() {
  return api.get('/keywords')
}

// ---- 工作区 ----
export function fetchWorkspaces() {
  return api.get('/workspaces')
}
export function createWorkspace(name) {
  return api.post('/workspaces', null, { params: { name } })
}
export function loadWorkspace(dbPath) {
  return api.post('/workspaces/load', null, { params: { db_path: dbPath } })
}
export function deleteWorkspace(id) {
  return api.delete(`/workspaces/${id}`)
}
export function clearWorkspace() {
  return api.post('/workspaces/current/clear')
}
export function exportWorkspaceArchive() {
  return api.get('/workspace/export', { responseType: 'blob', timeout: 130000 })
}

export function importWorkspace(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/workspace/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 130000,
  })
}
