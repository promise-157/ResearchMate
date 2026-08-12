import { expect, test } from '@playwright/test'


const workspaces = [
  { id: 1, name: 'Alpha', db_path: '/fixture/alpha.db', item_count: 2, paper_count: 2 },
  { id: 2, name: 'Beta', db_path: '/fixture/beta.db', item_count: 0, paper_count: 0 },
]

const alphaPapers = [
  {
    id: 11,
    title: 'Review Fixture Paper One',
    abstract: 'Immutable source abstract one.',
    authors: '["Alice"]',
    paper_url: 'https://example.test/one',
    journal_name: 'Fixture Journal',
    publish_year: 2026,
    has_code: true,
    code_url: 'https://example.test/source-code/one',
    in_cart: false,
  },
  {
    id: 22,
    title: 'Review Fixture Paper Two',
    abstract: 'Immutable source abstract two.',
    authors: '["Bob"]',
    paper_url: 'https://example.test/two',
    journal_name: 'Fixture Journal',
    publish_year: 2026,
    has_code: false,
    code_url: null,
    in_cart: false,
  },
]

const sourceSnapshot = JSON.stringify(alphaPapers)

function reviewRun(id, status, errorMessage = null) {
  return {
    id,
    paper_id: null,
    paper_ids: [11, 22],
    run_kind: 'workspace_review',
    status,
    input_scope: ['title:300', 'abstract:2000'],
    input_hash: 'f'.repeat(64),
    processor: 'workspace_review',
    processor_version: '1',
    prompt_version: 'workspace-review-v1',
    provider: 'deepseek',
    model: 'fixture-configured-model',
    provider_model: status === 'succeeded' ? 'fixture-returned-model' : null,
    input_tokens: status === 'succeeded' ? 120 : null,
    output_tokens: status === 'succeeded' ? 40 : null,
    duration_ms: status === 'succeeded' ? 80 : null,
    request_id: status === 'succeeded' ? `req-review-${id}` : null,
    result: status === 'succeeded' ? {
      hot_topics: '显式范围的离线热门方向',
      recommendations: [{ paper_id: 11, reason: '证据完整' }],
      tech_trends: '可审计工作流',
    } : null,
    error_message: errorMessage,
    created_at: `2026-08-12 11:0${id}:00`,
    completed_at: `2026-08-12 11:0${id}:01`,
  }
}

test('workspace review confirms exact scope and restores isolated audited history', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let postAttempts = 0
  const runsByWorkspace = { Alpha: [], Beta: [] }
  const activeName = () => activePath === workspaces[0].db_path ? 'Alpha' : 'Beta'

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

    if (path === '/api/settings' && method === 'GET') return json({
      ai: { api_type: 'deepseek', has_key: true, model: 'fixture-configured-model' },
      crawl: { max_papers_per_source: 50, request_interval: 2, timeout: 30 },
    })
    if (path === '/api/workspaces' && method === 'GET') return json({
      items: workspaces,
      active_path: activePath,
      active_name: activeName(),
    })
    if (path === '/api/workspaces/load' && method === 'POST') {
      activePath = url.searchParams.get('db_path')
      return json({ ok: true })
    }
    if (path === '/api/journals' && method === 'GET') return json([])
    if (path === '/api/keywords' && method === 'GET') return json([])
    if (path === '/api/chat/sessions' && method === 'GET') return json([])
    if (path === '/api/cart' && method === 'GET') return json([])
    if (path === '/api/papers' && method === 'GET') {
      const items = activeName() === 'Alpha' ? alphaPapers : []
      return json({ items, total: items.length })
    }
    if (path === '/api/workspace/reviews' && method === 'GET') return json({
      runs: runsByWorkspace[activeName()],
      legacy_reviews: activeName() === 'Alpha' ? [{
        id: 7,
        task_ids: [],
        review: { hot_topics: '旧综述 fixture' },
        compatibility: 'legacy_read_only',
        created_at: '2026-08-11 09:00:00',
      }] : [],
      limits: {
        min_papers: 2,
        max_papers: 20,
        fields: [
          { name: 'title', max_chars_per_paper: 300 },
          { name: 'abstract', max_chars_per_paper: 2000 },
        ],
      },
    })
    if (path === '/api/workspace/reviews' && method === 'POST') {
      expect(activeName()).toBe('Alpha')
      expect(request.postDataJSON()).toEqual({ paper_ids: [11, 22] })
      expect(JSON.stringify(alphaPapers)).toBe(sourceSnapshot)
      postAttempts += 1
      await new Promise((resolve) => setTimeout(resolve, 150))
      const run = postAttempts === 1
        ? reviewRun(1, 'succeeded')
        : reviewRun(2, 'failed', 'fixture 脱敏结构校验失败')
      runsByWorkspace.Alpha.unshift(run)
      return json({ ok: run.status === 'succeeded', run })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/papers')
  await expect(page.getByText('迁移前综述（只读兼容）', { exact: true })).toBeVisible()
  await expect(page.getByText('旧综述 fixture', { exact: true })).toBeVisible()
  const submit = page.getByRole('button', { name: '生成工作区综述' })
  await expect(submit).toBeDisabled()

  await page.locator('.selection-list .el-checkbox').nth(0).click()
  await page.locator('.selection-list .el-checkbox').nth(1).click()
  const scope = page.getByTestId('workspace-review-scope')
  await expect(scope).toContainText('论文 ID（按发送顺序）：11、22')
  await expect(scope).toContainText('标题（每篇最多 300 字符）')
  await expect(scope).toContainText('摘要（每篇最多 2,000 字符）')
  await expect(scope).toContainText('不发送作者、来源链接、关键词或全文')
  await expect(submit).toBeDisabled()

  await page.getByText(/我确认只把以上精确 ID/).click()
  await submit.click()
  await expect(page.getByText('运行中', { exact: true })).toBeVisible()
  await expect(page.getByText('工作区综述成功，审计记录已保存', { exact: true })).toBeVisible()
  await expect(page.locator('.ai-result').getByText(/显式范围的离线热门方向/)).toBeVisible()
  await expect(page.getByText('请求 ID：req-review-1', { exact: true })).toBeVisible()
  expect(JSON.stringify(alphaPapers)).toBe(sourceSnapshot)

  await page.reload()
  await expect(page.locator('.ai-result').getByText(/显式范围的离线热门方向/)).toBeVisible()
  await expect(page.getByText(/论文 ID：11、22/)).toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByRole('dialog', { name: '切换工作区' }).getByText('Beta', { exact: true }).click()
  await expect(page.getByText('工作区: Beta', { exact: true })).toBeVisible()
  await expect(page.locator('.ai-result').getByText(/显式范围的离线热门方向/)).toHaveCount(0)
  await expect(page.getByText('旧综述 fixture', { exact: true })).toHaveCount(0)
  await expect(page.getByText('尚无统一审计运行。', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByRole('dialog', { name: '切换工作区' }).getByText('Alpha', { exact: true }).click()
  await page.locator('.selection-list .el-checkbox').nth(0).click()
  await page.locator('.selection-list .el-checkbox').nth(1).click()
  await page.getByText(/我确认只把以上精确 ID/).click()
  await submit.click()
  await expect(page.getByText('失败：fixture 脱敏结构校验失败', { exact: true })).toBeVisible()
  await expect(page.getByText(/工作区综述失败：fixture 脱敏结构校验失败/)).toBeVisible()
})
