import { expect, test } from '@playwright/test'


test('paper chat persists audited turns across refresh and workspace switches', async ({ page }) => {
  let activeWorkspace = 'Alpha'
  const workspaceTurns = { Alpha: [], Beta: [] }
  const workspaceSessions = {
    Alpha: [{ id: 1, title: '已有对话', turn_count: 0, updated_at: '2026-08-07' }],
    Beta: [],
  }

  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const json = (value, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })

    if (path === '/api/settings' && method === 'GET') return json({
      ai: { api_type: 'deepseek', has_key: true, model: 'deepseek-v4-pro' },
      crawl: { max_papers_per_source: 50, request_interval: 2, timeout: 30 },
    })
    if (path === '/api/workspaces' && method === 'GET') return json({
      active_name: activeWorkspace,
      active_path: `/fixture/${activeWorkspace}.db`,
      items: [
        { id: 1, name: 'Alpha', db_path: '/fixture/Alpha.db', paper_count: 2 },
        { id: 2, name: 'Beta', db_path: '/fixture/Beta.db', paper_count: 0 },
      ],
    })
    if (path === '/api/workspaces/load' && method === 'POST') {
      activeWorkspace = url.searchParams.get('db_path').includes('Beta') ? 'Beta' : 'Alpha'
      return json({ ok: true })
    }
    if (path === '/api/journals' && method === 'GET') return json([])
    if (path === '/api/keywords' && method === 'GET') return json([])
    if (path === '/api/papers' && method === 'GET') return json({
      items: activeWorkspace === 'Alpha' ? [
        { id: 1, title: 'Fixture Paper One', journal_name: 'arXiv', publish_year: 2026 },
        { id: 2, title: 'Fixture Paper Two', journal_name: 'arXiv', publish_year: 2026 },
      ] : [],
      total: activeWorkspace === 'Alpha' ? 2 : 0,
    })
    if (path === '/api/chat/sessions' && method === 'GET') {
      return json(workspaceSessions[activeWorkspace])
    }
    if (path === '/api/chat/sessions' && method === 'POST') {
      const session = { id: 1, title: '新对话', turn_count: 0, updated_at: '2026-08-07' }
      workspaceSessions[activeWorkspace] = [session]
      return json(session)
    }
    if (path === '/api/chat/sessions/1' && method === 'GET') return json({
      id: 1, title: workspaceSessions[activeWorkspace][0]?.title || '新对话',
      turns: workspaceTurns[activeWorkspace],
    })
    if (path === '/api/chat/sessions/1/turns' && method === 'POST') {
      const body = request.postDataJSON()
      expect(body.paper_ids).toEqual([1, 2])
      if (body.message === '触发离线失败') {
        const failed = {
          id: 2, session_id: 1, user_message: body.message,
          assistant_message: null, status: 'failed', paper_ids: body.paper_ids,
          input_scope: ['message', 'chat_history', 'paper_metadata'], history_turn_ids: [1],
          provider: 'deepseek', model: 'deepseek-v4-pro',
          error_message: '模型请求超时，请稍后重试',
          created_at: '2026-08-07 10:01:00', completed_at: '2026-08-07 10:01:01',
        }
        workspaceTurns[activeWorkspace].push(failed)
        workspaceSessions[activeWorkspace][0].turn_count = 2
        return json(failed)
      }
      expect(body.message).toBe('比较这两篇论文')
      const turn = {
        id: 1, session_id: 1, user_message: body.message,
        assistant_message: '离线 fixture 比较结果', status: 'succeeded',
        paper_ids: body.paper_ids, input_scope: ['message', 'chat_history', 'paper_metadata'],
        history_turn_ids: [], provider: 'deepseek', model: 'deepseek-v4-pro',
        provider_model: 'deepseek-v4-pro-fixture', input_tokens: 80, output_tokens: 20,
        duration_ms: 50, request_id: 'req-chat-e2e', created_at: '2026-08-07 10:00:00',
        completed_at: '2026-08-07 10:00:01',
      }
      workspaceTurns[activeWorkspace].push(turn)
      workspaceSessions[activeWorkspace][0] = {
        ...workspaceSessions[activeWorkspace][0], title: body.message, turn_count: 1,
      }
      return json(turn)
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/papers')
  await expect(page.locator('.chat-header .el-select')).toContainText('已有对话 (0)')
  await page.getByRole('button', { name: '附件' }).click()
  const attachDialog = page.getByRole('dialog', { name: '选择附加论文' })
  await attachDialog.getByText('Fixture Paper One', { exact: true }).click()
  await attachDialog.getByText('Fixture Paper Two', { exact: true }).click()
  await attachDialog.getByRole('button', { name: '确定' }).click()
  await page.getByPlaceholder('输入指令...').fill('比较这两篇论文')
  await page.getByRole('button', { name: '发送', exact: true }).click()

  await expect(page.getByText('离线 fixture 比较结果')).toBeVisible()
  await expect(page.getByText('本轮附加论文 ID：1, 2')).toBeVisible()
  await expect(page.getByText(/deepseek-v4-pro-fixture · 80↑\/20↓ token/)).toBeVisible()

  await page.getByPlaceholder('输入指令...').fill('触发离线失败')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByText('失败：模型请求超时，请稍后重试')).toBeVisible()

  await page.reload()
  await expect(page.getByText('离线 fixture 比较结果')).toBeVisible()
  await expect(page.getByText('失败：模型请求超时，请稍后重试')).toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByRole('dialog', { name: '切换工作区' }).getByText('Beta', { exact: true }).click()
  await expect(page.getByText('离线 fixture 比较结果')).toHaveCount(0)
  await expect(page.getByText(/选择历史会话/)).toBeVisible()
  await page.getByRole('button', { name: '附件' }).click()
  const betaAttachDialog = page.getByRole('dialog', { name: '选择附加论文' })
  await expect(betaAttachDialog.getByText('Fixture Paper One', { exact: true })).toHaveCount(0)
  await expect(betaAttachDialog.getByText('Fixture Paper Two', { exact: true })).toHaveCount(0)
})


test('stale chat and attachment responses cannot repopulate a switched workspace', async ({ page }) => {
  let activeWorkspace = 'Alpha'
  let releaseAlpha
  const alphaGate = new Promise((resolve) => { releaseAlpha = resolve })
  let delayedRequests = 0

  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const json = (value, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })

    if (path === '/api/settings' && method === 'GET') return json({
      ai: { api_type: 'deepseek', has_key: true, model: 'fixture' },
      crawl: { max_papers_per_source: 50, request_interval: 2, timeout: 30 },
    })
    if (path === '/api/cart' && method === 'GET') return json([])
    if (path === '/api/workspaces' && method === 'GET') return json({
      active_name: activeWorkspace,
      active_path: `/fixture/${activeWorkspace}.db`,
      items: [
        { id: 1, name: 'Alpha', db_path: '/fixture/Alpha.db', paper_count: 1 },
        { id: 2, name: 'Beta', db_path: '/fixture/Beta.db', paper_count: 0 },
      ],
    })
    if (path === '/api/workspaces/load' && method === 'POST') {
      activeWorkspace = url.searchParams.get('db_path').includes('Beta') ? 'Beta' : 'Alpha'
      return json({ ok: true })
    }
    if (path === '/api/journals' && method === 'GET') return json([])
    if (path === '/api/keywords' && method === 'GET') return json([])
    if (path === '/api/papers' && method === 'GET') {
      const requestedWorkspace = activeWorkspace
      const isAttachmentRequest = url.searchParams.get('page_size') === '100'
      if (requestedWorkspace === 'Alpha' && isAttachmentRequest) {
        delayedRequests += 1
        await alphaGate
      }
      return json(requestedWorkspace === 'Alpha' ? {
        items: [{ id: 1, title: 'Delayed Alpha Paper', journal_name: 'arXiv' }], total: 1,
      } : { items: [], total: 0 })
    }
    if (path === '/api/chat/sessions' && method === 'GET') {
      const requestedWorkspace = activeWorkspace
      if (requestedWorkspace === 'Alpha') {
        delayedRequests += 1
        await alphaGate
      }
      return json(requestedWorkspace === 'Alpha'
        ? [{ id: 1, title: 'Delayed Alpha Session', turn_count: 0 }]
        : [])
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/papers')
  await expect.poll(() => delayedRequests).toBeGreaterThan(0)
  await page.getByRole('button', { name: '切换' }).click()
  await page.getByRole('dialog', { name: '切换工作区' }).getByText('Beta', { exact: true }).click()
  releaseAlpha()

  await expect(page.locator('.chat-header .el-select')).not.toContainText('Delayed Alpha Session')
  await page.getByRole('button', { name: '附件' }).click()
  const dialog = page.getByRole('dialog', { name: '选择附加论文' })
  await expect(dialog.getByText('Delayed Alpha Paper', { exact: true })).toHaveCount(0)
})
