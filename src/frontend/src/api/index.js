import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 响应拦截：统一错误处理
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
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

export function createUrlImport(url) {
  return api.post('/url-imports', { url }, { timeout: 35000 })
}

export function fetchUrlImports() {
  return api.get('/url-imports')
}

export function discoverArxiv(query, limit = 10) {
  return api.post('/discoveries/arxiv', { query, limit }, { timeout: 30000 })
}

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
  return api.post('/cart/analyze', { paper_ids: paperIds })
}

export function analyzeAllCart() {
  return api.post('/cart/analyze/all')
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
export function triggerWorkspaceReview(customPrompt) {
  return api.post('/workspace/review', { prompt: customPrompt || '' })
}

export function getExportUrl() {
  return '/api/workspace/export'
}

export function importWorkspace(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/workspace/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
