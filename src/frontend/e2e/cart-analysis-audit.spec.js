import { expect, test } from '@playwright/test'


const workspaces = [
  { id: 1, name: 'Alpha', db_path: '/fixture/alpha.db', item_count: 2, paper_count: 2 },
  { id: 2, name: 'Beta', db_path: '/fixture/beta.db', item_count: 0, paper_count: 0 },
]

const alphaPapers = [
  {
    id: 1,
    title: 'Alpha Audited Paper One',
    abstract: 'Source abstract one stays immutable.',
    authors: 'Alice Example',
    paper_url: 'https://example.test/papers/one',
    journal_name: 'Fixture Journal',
    publish_year: 2026,
    in_cart: true,
    has_code: true,
    code_url: 'https://example.test/source-code/one',
    ai_analyzed: true,
    ai_innovation: '迁移前兼容创新结果',
    ai_technologies: '["legacy-tech"]',
    ai_code_url: 'https://example.test/legacy-ai-code',
    analysis_runs: [],
  },
  {
    id: 2,
    title: 'Alpha Audited Paper Two',
    abstract: 'Source abstract two stays immutable.',
    authors: 'Bob Example',
    paper_url: 'https://example.test/papers/two',
    journal_name: 'Fixture Journal',
    publish_year: 2026,
    in_cart: true,
    has_code: false,
    code_url: null,
    analysis_runs: [],
  },
]

const immutableSourceFacts = alphaPapers.map((paper) => ({
  id: paper.id,
  title: paper.title,
  abstract: paper.abstract,
  authors: paper.authors,
  paper_url: paper.paper_url,
  has_code: paper.has_code,
  code_url: paper.code_url,
}))

function auditRun(id, paperId, status, result = null, errorMessage = null) {
  return {
    id,
    paper_id: paperId,
    run_kind: 'paper_analysis',
    status,
    paper_ids: [paperId],
    input_scope: ['title', 'abstract'],
    provider: 'deepseek',
    model: 'deepseek-v4-pro',
    provider_model: status === 'succeeded' ? 'deepseek-v4-pro-fixture' : null,
    input_tokens: status === 'succeeded' ? 51 + paperId : null,
    output_tokens: status === 'succeeded' ? 21 + paperId : null,
    duration_ms: status === 'succeeded' ? 101 + paperId : null,
    request_id: status === 'succeeded' ? `req-cart-${id}` : null,
    prompt_version: 'paper-analysis-v1',
    result,
    error_message: errorMessage,
    created_at: `2026-08-12 10:0${id}:00`,
    completed_at: `2026-08-12 10:0${id}:01`,
  }
}

test('cart analysis persists per-paper audit, partial failure, reload and workspace isolation', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let singleAttempts = 0
  const carts = { Alpha: alphaPapers, Beta: [] }

  const activeName = () => (activePath === workspaces[0].db_path ? 'Alpha' : 'Beta')
  const assertSourceFactsUnchanged = () => {
    expect(alphaPapers.map((paper) => ({
      id: paper.id,
      title: paper.title,
      abstract: paper.abstract,
      authors: paper.authors,
      paper_url: paper.paper_url,
      has_code: paper.has_code,
      code_url: paper.code_url,
    }))).toEqual(immutableSourceFacts)
  }

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
      ai: { api_type: 'deepseek', has_key: true, model: 'deepseek-v4-pro' },
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
    if (path === '/api/papers' && method === 'GET') {
      const visible = carts[activeName()]
      return json({ items: visible, total: visible.length })
    }
    if (path === '/api/cart' && method === 'GET') {
      assertSourceFactsUnchanged()
      return json(carts[activeName()])
    }
    if (path === '/api/cart/analyze' && method === 'POST') {
      const body = request.postDataJSON()
      expect(body).toEqual({ paper_ids: [1] })
      assertSourceFactsUnchanged()
      singleAttempts += 1
      if (singleAttempts === 1) {
        const failed = auditRun(1, 1, 'failed', null, 'fixture 单篇模型超时')
        alphaPapers[0].analysis_runs.unshift(failed)
        return json({
          ok: false,
          overall_status: 'failed',
          requested: 1,
          succeeded: 0,
          failed: 1,
          analyzed: 0,
          runs: [failed],
          message: '全部论文分析失败，请查看逐篇失败原因',
        })
      }
      const succeeded = auditRun(2, 1, 'succeeded', {
        has_code: false,
        code_url: null,
        innovation: '统一审计成功建议',
        technologies: ['fixture-ai'],
      })
      alphaPapers[0].analysis_runs.unshift(succeeded)
      return json({
        ok: true,
        overall_status: 'succeeded',
        requested: 1,
        succeeded: 1,
        failed: 0,
        analyzed: 1,
        runs: [succeeded],
        message: '已完成 1/1 篇论文分析',
      })
    }
    if (path === '/api/cart/analyze/all' && method === 'POST') {
      assertSourceFactsUnchanged()
      const succeeded = auditRun(3, 1, 'succeeded', {
        has_code: true,
        code_url: 'https://example.test/ai-suggestion/one',
        innovation: '批量中的成功建议',
        technologies: ['batch-fixture'],
      })
      const failed = auditRun(4, 2, 'failed', null, 'fixture 第二篇结构校验失败')
      alphaPapers[0].analysis_runs.unshift(succeeded)
      alphaPapers[1].analysis_runs.unshift(failed)
      return json({
        ok: false,
        overall_status: 'partial',
        requested: 2,
        succeeded: 1,
        failed: 1,
        analyzed: 1,
        runs: [succeeded, failed],
        message: '部分完成：成功 1/2 篇，请查看逐篇失败原因',
      })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/papers')
  await page.getByRole('button', { name: '购物车', exact: true }).click()
  const cartDrawer = page.locator('.el-drawer')
  await expect(cartDrawer.getByText('Alpha Audited Paper One', { exact: true })).toBeVisible()
  await expect(cartDrawer.getByText('Alpha Audited Paper Two', { exact: true })).toBeVisible()
  await expect(cartDrawer.getByText('旧兼容结果（只读）', { exact: true })).toBeVisible()

  await cartDrawer.getByRole('button', { name: '分析 Alpha Audited Paper One' }).click()
  await expect(cartDrawer.getByText('失败：fixture 单篇模型超时', { exact: true })).toBeVisible()
  await expect(page.getByText(/分析失败：0\/1 篇成功，1 篇失败/)).toBeVisible()

  await cartDrawer.getByRole('button', { name: '分析 Alpha Audited Paper One' }).click()
  await expect(cartDrawer.getByText('统一审计成功建议', { exact: false })).toBeVisible()
  await expect(cartDrawer.getByText(/服务商返回：deepseek-v4-pro-fixture/).first()).toBeVisible()
  await expect(cartDrawer.getByText(/token 52\/22/).first()).toBeVisible()
  await expect(cartDrawer.getByText('请求 ID：req-cart-2', { exact: true })).toBeVisible()
  await expect(page.getByText('单篇分析成功，AI 建议已记录', { exact: true })).toBeVisible()

  await cartDrawer.getByRole('button', { name: /批量 AI 分析/ }).click()
  await expect(page.getByText(/1\/2 篇成功，1 篇失败/)).toBeVisible()
  await expect(page.getByText('失败：fixture 第二篇结构校验失败', { exact: true })).toBeVisible()
  await expect(page.getByText('批量分析完成', { exact: true })).toHaveCount(0)
  assertSourceFactsUnchanged()

  await page.reload()
  await page.getByRole('button', { name: '购物车', exact: true }).click()
  await expect(cartDrawer.getByText('统一审计成功建议', { exact: false })).toBeVisible()
  await expect(cartDrawer.getByText('失败：fixture 第二篇结构校验失败', { exact: true })).toBeVisible()
  await expect(cartDrawer.getByText('旧兼容结果（只读）', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Close' }).click()
  await page.getByRole('button', { name: '切换' }).click()
  await page.getByRole('dialog', { name: '切换工作区' }).getByText('Beta', { exact: true }).click()
  await expect(page.getByText('工作区: Beta', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '购物车', exact: true }).click()
  await expect(cartDrawer.getByText('购物车为空', { exact: true })).toBeVisible()

  await page.reload()
  await page.getByRole('button', { name: '购物车', exact: true }).click()
  await expect(cartDrawer.getByText('购物车为空', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Close' }).click()
  await page.getByRole('button', { name: '切换' }).click()
  await page.getByRole('dialog', { name: '切换工作区' }).getByText('Alpha', { exact: true }).click()
  await page.getByRole('button', { name: '购物车', exact: true }).click()
  await expect(cartDrawer.getByText('统一审计成功建议', { exact: false })).toBeVisible()
  await expect(cartDrawer.getByText('失败：fixture 第二篇结构校验失败', { exact: true })).toBeVisible()
  assertSourceFactsUnchanged()
})
