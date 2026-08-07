import { expect, test } from '@playwright/test'


test('AI connection test is explicit, confirmed and sends no workspace data', async ({ page }) => {
  let testRequests = 0
  const settingsUpdates = []

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
      ai: {
        api_type: 'deepseek', has_key: true,
        key_source: 'config', key_storage_mode: 'config',
        config_path: '/fixture/src/backend/config.yaml',
        api_base_url: 'https://api.deepseek.com', model: 'deepseek-v4-pro',
      },
      crawl: { max_papers_per_source: 50, request_interval: 2, timeout: 30 },
    })
    if (path === '/api/settings' && method === 'PUT') {
      const body = request.postDataJSON()
      settingsUpdates.push(body)
      const cleared = body.ai?.clear_api_key === true
      return json({
        ok: true,
        ai: {
          has_key: !cleared,
          key_source: cleared ? 'none' : 'config',
          key_storage_mode: body.ai?.key_storage_mode || 'config',
          config_path: '/fixture/src/backend/config.yaml',
        },
      })
    }
    if (path === '/api/settings/ai/test' && method === 'POST') {
      testRequests += 1
      expect(request.postDataJSON()).toEqual({})
      return json({
        ok: true, provider: 'deepseek', configured_model: 'deepseek-v4-pro',
        provider_model: 'deepseek-v4-pro-fixture', input_tokens: 8,
        output_tokens: 1, duration_ms: 25, request_id: 'req-settings',
      })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/settings')
  await page.getByText('AI 配置', { exact: true }).click()
  await expect(page.getByText(/明文写入 \/fixture\/src\/backend\/config.yaml/)).toBeVisible()
  await expect(page.getByText(/Key 已保存在 \/fixture\/src\/backend\/config.yaml/)).toBeVisible()
  await expect(page.getByRole('button', { name: '测试连接' })).toBeVisible()
  expect(testRequests).toBe(0)

  await page.getByRole('button', { name: '测试连接' }).click()
  await expect(page.getByText(/可能产生少量费用/)).toBeVisible()
  await page.getByRole('button', { name: '取消' }).click()
  expect(testRequests).toBe(0)

  await page.getByRole('button', { name: '测试连接' }).click()
  await page.getByRole('button', { name: '发送一次测试' }).click()
  await expect(page.getByText('连接成功 · deepseek · deepseek-v4-pro-fixture · 25 ms')).toBeVisible()
  expect(testRequests).toBe(1)

  await page.getByRole('button', { name: '清除 Key' }).click()
  await expect.poll(() => settingsUpdates.some(body => body.ai?.clear_api_key === true)).toBe(true)
  await expect(page.getByText('尚未配置 Key。')).toBeVisible()
})
