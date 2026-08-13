import { expect, test } from '@playwright/test'


const workspace = {
  id: 1, name: 'URL Fixture', db_path: '/fixture/url.db', item_count: 0, paper_count: 0,
}

const candidates = [
  {
    id: 71, job_id: 11, title: '待拒绝网页', content_text: '离线候选正文一',
    summary: '离线候选正文一', source_kind: 'public_url',
    source_url: 'https://example.com/reject', status: 'pending',
    source_facts: { collector: 'single_public_url', charset: 'utf-8', redirect_count: 0 },
    created_at: '2026-08-13 11:00:00',
  },
  {
    id: 72, job_id: 12, title: '待接受网页', content_text: '离线候选正文二',
    summary: '离线候选正文二', source_kind: 'public_url',
    source_url: 'https://example.org/final', status: 'pending',
    source_facts: { collector: 'single_public_url', charset: 'gb18030', redirect_count: 1 },
    created_at: '2026-08-13 11:01:00',
  },
]

const acceptedItem = {
  id: 81, item_type: 'general', title: '待接受网页', content_text: '离线候选正文二',
  summary: '离线候选正文二', source_kind: 'public_url',
  source_url: 'https://example.org/final', status: 'inbox', tags: [], metadata: {},
  created_at: '2026-08-13 11:02:00',
}

test('public URL failures persist and candidates require explicit review', async ({ page }) => {
  let importCount = 0
  let visibleCandidates = []
  let accepted = false
  let jobs = []

  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const json = (value, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })

    if (path === '/api/workspaces' && method === 'GET') {
      return json({ items: [workspace], active_path: workspace.db_path, active_name: workspace.name })
    }
    if (path === '/api/items' && method === 'GET') {
      return json({ items: accepted ? [acceptedItem] : [], total: accepted ? 1 : 0, page: 1, page_size: 20 })
    }
    if (path === '/api/candidates' && method === 'GET') {
      return json({ candidates: visibleCandidates.filter((candidate) => candidate.status === 'pending') })
    }
    if (path === '/api/collection-jobs' && method === 'GET') return json({ jobs })
    if (path === '/api/url-imports' && method === 'POST') {
      importCount += 1
      if (importCount === 1) {
        jobs = [{
          id: 10, collector: 'single_public_url', status: 'failed', candidate_count: 0,
          query: { url: 'https://example.com/broken' },
          error_message: '页面内容无法按声明字符集 ascii 解码',
        }]
        return json({ detail: jobs[0].error_message }, 422)
      }
      const candidate = candidates[importCount - 2]
      visibleCandidates.push(candidate)
      return json({ job: { id: candidate.job_id, status: 'succeeded' }, candidate }, 201)
    }
    if (path === '/api/candidates/71/reject' && method === 'POST') {
      visibleCandidates = visibleCandidates.map((candidate) => (
        candidate.id === 71 ? { ...candidate, status: 'rejected' } : candidate
      ))
      return json({ ...candidates[0], status: 'rejected' })
    }
    if (path === '/api/candidates/72/accept' && method === 'POST') {
      visibleCandidates = visibleCandidates.map((candidate) => (
        candidate.id === 72 ? { ...candidate, status: 'accepted', accepted_item_id: 81 } : candidate
      ))
      accepted = true
      return json({ candidate: visibleCandidates[1], item: acceptedItem, duplicate: false }, 201)
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  const openImport = () => page.getByRole('button', { name: '导入公开 URL' }).click()
  const submit = async (url) => {
    await page.getByLabel('公开网页 URL').fill(url)
    await page.getByRole('button', { name: '读取并加入候选箱' }).click()
  }

  await openImport()
  await submit('https://example.com/broken')
  await expect(page.getByText('页面内容无法按声明字符集 ascii 解码').first()).toBeVisible()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()

  await submit('https://example.com/reject')
  await expect(page.getByRole('heading', { name: '待拒绝网页', level: 3 })).toBeVisible()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await page.getByRole('button', { name: '拒绝' }).click()
  await expect(page.getByRole('heading', { name: '待拒绝网页', level: 3 })).not.toBeVisible()

  await openImport()
  await submit('https://example.com/redirect')
  await expect(page.getByRole('heading', { name: '待接受网页', level: 3 })).toBeVisible()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await page.getByRole('button', { name: '接受入库' }).click()
  await expect(page.getByRole('heading', { name: '待接受网页', level: 3 })).toBeVisible()
  await expect(page.getByText('当前工作区还没有通用资料')).not.toBeVisible()
})
