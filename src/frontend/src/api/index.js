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
export function triggerWorkspaceReview() {
  return api.post('/workspace/review')
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
