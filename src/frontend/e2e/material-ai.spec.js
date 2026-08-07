import { expect, test } from '@playwright/test'


const workspaces = [
  { id: 1, name: 'AI Fixture', db_path: '/fixture/ai.db', item_count: 20, paper_count: 0 },
  { id: 2, name: 'Empty Fixture', db_path: '/fixture/empty-ai.db', item_count: 0, paper_count: 0 },
]
const items = Array.from({ length: 20 }, (_, index) => ({
  id: index + 1,
  item_type: index === 0 ? 'paper' : 'general',
  title: `AI 离线资料 ${index + 1}`,
  content_text: `fixture content ${index + 1}`,
  summary: `fixture summary ${index + 1}`,
  source_kind: 'text_import',
  source_url: null,
  status: 'active',
  tags: [],
  metadata: {},
  assets: [],
  accepted_extractions: [],
  has_accepted_extraction: false,
  created_at: '2026-08-07 12:00:00',
}))

function run(id, status, kind, itemIds, result = null, error = null) {
  return {
    id,
    item_id: itemIds[0],
    processor: 'material_ai',
    processor_version: '2',
    run_kind: kind,
    status,
    input_scope: ['title', 'content_text'],
    input_item_ids: itemIds,
    provider: 'deepseek',
    model: 'deepseek-v4-pro',
    provider_model: status === 'succeeded' ? 'deepseek-v4-pro-fixture' : null,
    input_tokens: status === 'succeeded' ? 42 : null,
    output_tokens: status === 'succeeded' ? 17 : null,
    duration_ms: status === 'succeeded' ? 123 : null,
    request_id: status === 'succeeded' ? `req-${id}` : null,
    prompt_version: kind === 'compare' ? 'material-compare-v1' : 'material-classify-v1',
    result,
    error_message: error,
    created_at: '2026-08-07 12:01:00',
  }
}

test('single failure/success, 2/20-item comparison and workspace isolation persist offline', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let singleAttempts = 0
  const itemRuns = []
  const comparisonRuns = []

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
      const visible = activePath === workspaces[0].db_path ? items : []
      return json({ items: visible, total: visible.length, page: 1, page_size: 20 })
    }
    if (path === '/api/items/analysis-comparisons' && method === 'GET') {
      return json({ runs: activePath === workspaces[0].db_path ? comparisonRuns : [] })
    }
    if (path === '/api/items/analysis-comparisons' && method === 'POST') {
      const body = request.postDataJSON()
      expect([2, 20]).toContain(body.item_ids.length)
      comparisonRuns.unshift(run(90 + comparisonRuns.length, 'succeeded', 'compare', body.item_ids, {
        summary: `${body.item_ids.length} 条资料比较完成`, common_themes: ['fixture'],
        differences: ['编号不同'], item_insights: {},
      }))
      return json({ run: comparisonRuns[0], reused: false })
    }
    const detailMatch = path.match(/^\/api\/items\/(\d+)$/)
    if (detailMatch && method === 'GET') return json(items[Number(detailMatch[1]) - 1])
    const historyMatch = path.match(/^\/api\/items\/(\d+)\/analysis-runs$/)
    if (historyMatch && method === 'GET') {
      const visible = activePath === workspaces[0].db_path ? itemRuns : []
      return json({ runs: visible })
    }
    if (historyMatch && method === 'POST') {
      singleAttempts += 1
      if (singleAttempts === 1) {
        itemRuns.unshift(run(
          70, 'failed', 'classify', [1], null,
          '模型鉴权失败，请检查会话 API Key',
        ))
        return json({ detail: '模型鉴权失败，请检查会话 API Key' }, 422)
      }
      itemRuns.unshift(run(71, 'succeeded', 'classify', [1], {
        suggested_type: 'paper', confidence: 0.95, reason: 'fixture',
      }))
      return json({ run: itemRuns[0], reused: false })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  await page.getByRole('heading', { name: 'AI 离线资料 1', level: 3, exact: true }).click()
  await page.getByRole('button', { name: '确认范围并运行' }).click()
  await expect(page.getByText('模型鉴权失败，请检查会话 API Key').first()).toBeVisible()
  await page.getByRole('button', { name: '确认范围并运行' }).click()
  await expect(page.getByText('服务商返回：deepseek-v4-pro-fixture')).toBeVisible()
  await expect(page.getByText(/token 42\/17/)).toBeVisible()

  await page.reload()
  await page.getByRole('heading', { name: 'AI 离线资料 1', level: 3, exact: true }).click()
  await expect(page.getByText('模型鉴权失败，请检查会话 API Key').first()).toBeVisible()
  await expect(page.getByText('服务商返回：deepseek-v4-pro-fixture')).toBeVisible()
  await page.getByRole('dialog', { name: 'AI 离线资料 1' }).getByRole('button', { name: 'Close' }).click()

  const checkboxes = page.locator('.material-card > .el-checkbox')
  await expect(checkboxes).toHaveCount(20)
  for (let index = 0; index < 2; index += 1) await checkboxes.nth(index).click()
  await page.getByRole('button', { name: '比较所选（2）' }).click()
  await page.getByRole('button', { name: '确认清单并比较' }).click()
  let comparisonDialog = page.getByRole('dialog', { name: '比较所选资料' })
  await expect(comparisonDialog.getByText('2 条资料比较完成')).toBeVisible()
  await comparisonDialog.getByRole('button', { name: 'Close' }).click()

  for (let index = 2; index < 20; index += 1) await checkboxes.nth(index).click()
  await page.getByRole('button', { name: '比较所选（20）' }).click()
  await page.getByRole('button', { name: '确认清单并比较' }).click()
  comparisonDialog = page.getByRole('dialog', { name: '比较所选资料' })
  await expect(comparisonDialog.getByText('20 条资料比较完成')).toBeVisible()
  await expect(comparisonDialog.getByText(/请求 req-91/)).toBeVisible()
  await comparisonDialog.getByRole('button', { name: 'Close' }).click()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Empty Fixture', { exact: true }).click()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await page.reload()
  await expect(page.getByText('工作区: Empty Fixture')).toBeVisible()
  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('AI Fixture', { exact: true }).click()
  await page.getByRole('heading', { name: 'AI 离线资料 1', level: 3, exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'AI 离线资料 1' })
    .getByText('服务商返回：deepseek-v4-pro-fixture')).toBeVisible()
})
