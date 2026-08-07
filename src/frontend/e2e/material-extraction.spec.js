import { expect, test } from '@playwright/test'


const workspaces = [
  { id: 1, name: 'Workspace A', db_path: '/fixture/a.db', item_count: 1, paper_count: 0 },
  { id: 2, name: 'Workspace B', db_path: '/fixture/b.db', item_count: 0, paper_count: 0 },
]

const baseItem = {
  id: 1,
  item_type: 'general',
  title: '离线 OCR 截图',
  content_text: '',
  summary: '用户导入图片',
  source_kind: 'image_import',
  source_url: null,
  status: 'inbox',
  tags: [],
  metadata: {},
  assets: [{ id: 11, original_name: 'fixture.png', mime_type: 'image/png' }],
  created_at: '2026-08-07 10:00:00',
}

const ocrRun = {
  id: 31,
  item_id: 1,
  processor: 'local_tesseract',
  processor_version: '1',
  run_kind: 'ocr',
  status: 'succeeded',
  input_scope: ['asset'],
  provider: 'local',
  model: 'tesseract',
  prompt_version: 'none',
  result: { text: 'accepted-only fixture phrase', character_count: 28 },
  created_at: '2026-08-07 10:01:00',
}

test('accepted OCR survives refresh and remains isolated across workspace switches', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let accepted = null

  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const json = (value, status = 200) => route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(value),
    })

    if (path === '/api/workspaces' && method === 'GET') {
      const active = workspaces.find((workspace) => workspace.db_path === activePath)
      return json({ items: workspaces, active_path: activePath, active_name: active.name })
    }
    if (path === '/api/workspaces/load' && method === 'POST') {
      activePath = url.searchParams.get('db_path')
      return json({ success: true })
    }
    if (path === '/api/candidates') return json({ candidates: [] })
    if (path === '/api/collection-jobs') return json({ jobs: [] })
    if (path === '/api/items' && method === 'GET') {
      if (activePath !== workspaces[0].db_path) {
        return json({ items: [], total: 0, page: 1, page_size: 20 })
      }
      const query = url.searchParams.get('q')
      const expanded = url.searchParams.get('include_accepted_extractions') === 'true'
      const matches = !query || (expanded && accepted?.text_value.includes(query))
      const item = { ...baseItem, has_accepted_extraction: Boolean(accepted) }
      return json({ items: matches ? [item] : [], total: matches ? 1 : 0, page: 1, page_size: 20 })
    }
    if (path === '/api/items/1' && method === 'GET') {
      return json({
        ...baseItem,
        accepted_extractions: accepted ? [accepted] : [],
      })
    }
    if (path === '/api/items/1/analysis-runs') return json({ runs: [ocrRun] })
    if (path === '/api/items/1/extraction-runs/31/accept' && method === 'POST') {
      accepted = {
        item_id: 1,
        extraction_kind: 'ocr',
        run_id: 31,
        text_value: ocrRun.result.text,
        accepted_at: '2026-08-07 10:02:00',
      }
      return json({ accepted_extraction: accepted })
    }
    if (path === '/api/assets/11/content') {
      return route.fulfill({ status: 200, contentType: 'image/png', body: '' })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  await expect(page.getByRole('heading', { name: '离线 OCR 截图', level: 3 })).toBeVisible()
  await page.getByRole('heading', { name: '离线 OCR 截图', level: 3 }).click()
  await expect(page.getByText('accepted-only fixture phrase', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '接受此 OCR 文本' }).click()
  await expect(page.getByText('当前已接受')).toBeVisible()
  await expect(page.getByRole('checkbox', { name: '已接受提取文本', exact: true })).toBeEnabled()

  await page.reload()
  await page.getByRole('heading', { name: '离线 OCR 截图', level: 3 }).click()
  await expect(page.getByText('当前已接受')).toBeVisible()

  await page.getByRole('button', { name: 'Close' }).click()
  await page.getByPlaceholder('搜索标题或正文').fill('accepted-only fixture phrase')
  await page.getByRole('button', { name: '搜索' }).click()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await page.getByText('同时搜索已接受提取文本', { exact: true }).click()
  await page.getByRole('button', { name: '搜索' }).click()
  await expect(page.getByRole('heading', { name: '离线 OCR 截图', level: 3 })).toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Workspace B', { exact: true }).click()
  await expect(page.getByText('工作区: Workspace B')).toBeVisible()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await page.reload()
  await expect(page.getByText('工作区: Workspace B')).toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Workspace A', { exact: true }).click()
  await expect(page.getByRole('heading', { name: '离线 OCR 截图', level: 3 })).toBeVisible()
  await page.getByRole('heading', { name: '离线 OCR 截图', level: 3 }).click()
  await expect(page.getByText('当前已接受')).toBeVisible()
})
