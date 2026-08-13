import { expect, test } from '@playwright/test'


const workspaces = [
  { id: 1, name: 'Arxiv A', db_path: '/fixture/arxiv-a.db', item_count: 0, paper_count: 0 },
  { id: 2, name: 'Arxiv B', db_path: '/fixture/arxiv-b.db', item_count: 0, paper_count: 0 },
]

const discovered = [
  {
    id: 91, job_id: 21, title: 'Offline Retrieval Paper',
    content_text: 'Offline Retrieval Paper\n\nFirst fixture abstract.',
    summary: 'First fixture abstract.', source_kind: 'arxiv_api',
    source_url: 'https://arxiv.org/abs/2608.00001', status: 'pending',
    source_facts: {
      collector: 'arxiv_api', arxiv_id: '2608.00001', authors: ['Alice'],
      categories: ['cs.IR'], published: '2026-08-01T00:00:00Z',
      fetched_at: '2026-08-13T03:00:00+00:00', suggested_item_type: 'paper',
    },
    created_at: '2026-08-13 11:00:00',
  },
  {
    id: 92, job_id: 21, title: 'Rejected Fixture Paper',
    content_text: 'Rejected Fixture Paper\n\nSecond fixture abstract.',
    summary: 'Second fixture abstract.', source_kind: 'arxiv_api',
    source_url: 'https://arxiv.org/abs/2608.00002', status: 'pending',
    source_facts: {
      collector: 'arxiv_api', arxiv_id: '2608.00002', authors: ['Bob'],
      categories: ['cs.AI'], published: '2026-08-02T00:00:00Z',
      fetched_at: '2026-08-13T03:00:00+00:00', suggested_item_type: 'paper',
    },
    created_at: '2026-08-13 11:00:00',
  },
]

const acceptedItem = {
  id: 101, item_type: 'paper', title: discovered[0].title,
  content_text: discovered[0].content_text, summary: discovered[0].summary,
  source_kind: 'arxiv_api', source_url: discovered[0].source_url,
  status: 'inbox', tags: [], metadata: { provenance: discovered[0].source_facts },
  created_at: '2026-08-13 11:01:00',
}

test('arXiv discovery persists failures and isolates explicitly reviewed candidates', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let discoveryCount = 0
  let candidates = []
  let accepted = false
  let jobs = []
  const requests = []

  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const json = (value, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })

    if (path === '/api/workspaces' && method === 'GET') {
      const active = workspaces.find((workspace) => workspace.db_path === activePath)
      return json({ items: workspaces, active_path: activePath, active_name: active.name })
    }
    if (path === '/api/workspaces/load' && method === 'POST') {
      activePath = url.searchParams.get('db_path')
      return json({ success: true })
    }
    if (path === '/api/items' && method === 'GET') {
      const items = activePath === workspaces[0].db_path && accepted ? [acceptedItem] : []
      return json({ items, total: items.length, page: 1, page_size: 20 })
    }
    if (path === '/api/candidates' && method === 'GET') {
      const items = activePath === workspaces[0].db_path
        ? candidates.filter((candidate) => candidate.status === 'pending') : []
      return json({ candidates: items })
    }
    if (path === '/api/collection-jobs' && method === 'GET') {
      return json({ jobs: activePath === workspaces[0].db_path ? jobs : [] })
    }
    if (path === '/api/discoveries/arxiv' && method === 'POST') {
      const body = request.postDataJSON()
      requests.push(body)
      discoveryCount += 1
      if (discoveryCount === 1) {
        jobs = [{
          id: 20, collector: 'arxiv_api', status: 'failed', candidate_count: 0,
          query: body, error_message: 'fixture arXiv timeout',
        }]
        return json({ detail: 'fixture arXiv timeout' }, 422)
      }
      candidates = discovered.map((candidate) => ({ ...candidate }))
      jobs = [{
        id: 21, collector: 'arxiv_api', status: 'succeeded', candidate_count: 2,
        query: body, error_message: null,
      }, ...jobs]
      return json({ job: jobs[0], candidates }, 201)
    }
    if (path === '/api/candidates/91/accept' && method === 'POST') {
      candidates = candidates.map((candidate) => (
        candidate.id === 91
          ? { ...candidate, status: 'accepted', accepted_item_id: acceptedItem.id }
          : candidate
      ))
      accepted = true
      return json({ candidate: candidates[0], item: acceptedItem, duplicate: false }, 201)
    }
    if (path === '/api/candidates/92/reject' && method === 'POST') {
      candidates = candidates.map((candidate) => (
        candidate.id === 92 ? { ...candidate, status: 'rejected' } : candidate
      ))
      return json(candidates[1])
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  await page.getByRole('button', { name: '发现 arXiv 候选' }).click()
  await page.getByLabel('搜索词').fill('local retrieval')
  await page.getByRole('spinbutton', { name: '结果上限' }).fill('2')
  await page.getByRole('button', { name: '搜索并加入候选箱' }).click()
  await expect(page.getByText('fixture arXiv timeout').first()).toBeVisible()

  await page.getByRole('button', { name: '搜索并加入候选箱' }).click()
  await expect(page.getByRole('heading', { name: discovered[0].title, level: 3 })).toBeVisible()
  await expect(page.getByText('作者：Alice')).toBeVisible()
  await expect(page.getByText('分类：cs.IR')).toBeVisible()
  expect(requests).toEqual([
    { query: 'local retrieval', limit: 2 },
    { query: 'local retrieval', limit: 2 },
  ])
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()

  const acceptedCandidate = page.getByRole('heading', { name: discovered[0].title, level: 3 })
  await acceptedCandidate.locator('xpath=../..').getByRole('button', { name: '接受入库' }).click()
  const rejectedCandidate = page.getByRole('heading', { name: discovered[1].title, level: 3 })
  await rejectedCandidate.locator('xpath=../..').getByRole('button', { name: '拒绝' }).click()
  await expect(page.getByRole('heading', { name: discovered[1].title, level: 3 })).not.toBeVisible()
  await expect(page.getByRole('heading', { name: discovered[0].title, level: 3 })).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: discovered[0].title, level: 3 })).toBeVisible()
  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Arxiv B', { exact: true }).click()
  await expect(page.getByText('工作区: Arxiv B')).toBeVisible()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await expect(page.getByText('fixture arXiv timeout')).not.toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Arxiv A', { exact: true }).click()
  await expect(page.getByRole('heading', { name: discovered[0].title, level: 3 })).toBeVisible()
})
