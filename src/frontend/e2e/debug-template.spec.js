import { expect, test } from '@playwright/test'


const workspaces = [
  { id: 1, name: 'Debug Workspace', db_path: '/fixture/debug.db', item_count: 0, paper_count: 0 },
  { id: 2, name: 'Empty Workspace', db_path: '/fixture/debug-empty.db', item_count: 0, paper_count: 0 },
]

const debugItem = {
  id: 31,
  item_type: 'debug',
  title: 'Python requests 导入失败',
  content_text: [
    '错误: ModuleNotFoundError: requests',
    '环境: Python 3.12 Ubuntu',
    '尝试: 重装 requests',
    '根因: 虚拟环境未激活',
    '方案: 激活环境后重新安装',
  ].join('\n'),
  summary: 'Python requests 导入失败排查记录',
  source_kind: 'text_import',
  source_url: null,
  status: 'inbox',
  tags: ['Python', '待复盘'],
  metadata: { classification: { suggested_type: 'debug', method: 'rules-v1' } },
  assets: [],
  accepted_extractions: [],
  has_accepted_extraction: false,
  created_at: '2026-08-13 14:00:00',
}

const similarItem = {
  ...debugItem,
  id: 32,
  title: 'pytest 中 requests 缺失',
  content_text: `${debugItem.content_text}\n场景: pytest`,
}

function extractionRun(id) {
  return {
    id,
    item_id: debugItem.id,
    processor: 'debug_label_rules',
    processor_version: '1',
    run_kind: 'template_extract',
    status: 'succeeded',
    input_scope: ['content_text'],
    input_item_ids: [debugItem.id],
    provider: 'local',
    model: 'deterministic-rules',
    prompt_version: 'none',
    result: { error: 'ModuleNotFoundError: requests' },
    error_message: null,
    created_at: `2026-08-13 14:0${id - 80}:00`,
  }
}

test('Debug import, confirmation, reprocessing, filtering and isolation form a browser loop', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let imported = false
  let confirmed = {}
  let extractedRootCause = '虚拟环境未激活'
  let runs = [extractionRun(81)]

  const template = () => ({
    item_id: debugItem.id,
    template_key: 'debug',
    schema_version: 1,
    extracted: {
      error: 'ModuleNotFoundError: requests',
      environment: 'Python 3.12 Ubuntu',
      attempts: '重装 requests',
      root_cause: extractedRootCause,
      solution: '激活环境后重新安装',
    },
    confirmed,
    effective: {
      error: 'ModuleNotFoundError: requests',
      environment: 'Python 3.12 Ubuntu',
      attempts: '重装 requests',
      root_cause: extractedRootCause,
      solution: '激活环境后重新安装',
      ...confirmed,
    },
  })

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
    if (path === '/api/items' && method === 'POST') {
      const body = request.postDataJSON()
      expect(body.item_type).toBe('debug')
      expect(body.content_text).toContain('ModuleNotFoundError')
      expect(body.tags).toEqual(['Python', '待复盘'])
      imported = true
      workspaces[0].item_count = 1
      return json({ created: true, duplicate: false, item: debugItem }, 201)
    }
    if (path === '/api/items' && method === 'GET') {
      const requestedError = url.searchParams.get('debug_error')
      const effectiveError = template().effective.error
      const matches = activePath === workspaces[0].db_path
        && imported
        && (!requestedError || effectiveError.includes(requestedError))
      return json({
        items: matches ? [debugItem] : [],
        total: matches ? 1 : 0,
        page: 1,
        page_size: 20,
      })
    }
    if (path === '/api/items/31' && method === 'GET') return json(debugItem)
    if (path === '/api/items/31/analysis-runs' && method === 'GET') return json({ runs })
    if (path === '/api/items/31/template' && method === 'GET') return json(template())
    if (path === '/api/items/31/template/confirmation' && method === 'PUT') {
      confirmed = Object.fromEntries(
        Object.entries(request.postDataJSON()).filter(([, value]) => value?.trim()),
      )
      return json(template())
    }
    if (path === '/api/items/31/template/extract' && method === 'POST') {
      extractedRootCause = '重新提取的规则根因'
      runs = [extractionRun(82), ...runs]
      return json(template())
    }
    if (path === '/api/items/31/similar' && method === 'GET') {
      return json({
        algorithm: 'token-jaccard-v1',
        matches: [{
          item: similarItem,
          score: 0.72,
          evidence: { algorithm: 'token-jaccard-v1', shared_tokens: ['requests', 'python'] },
        }],
      })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await page.getByRole('button', { name: '导入文字' }).click()
  const importDialog = page.getByRole('dialog', { name: '导入文字资料' })
  await importDialog.getByLabel('正文').fill(debugItem.content_text)
  await importDialog.getByLabel('标题（可选）').fill(debugItem.title)
  await importDialog.locator('.el-select').click()
  await page.locator('.el-select-dropdown:visible').getByText('Debug', { exact: true }).click()
  await importDialog.getByLabel('标签（逗号分隔）').fill('Python, 待复盘')
  await importDialog.getByRole('button', { name: '保存资料' }).click()
  await expect(page.getByText('已保存为“Debug”资料')).toBeVisible()

  await page.getByRole('heading', { name: debugItem.title, level: 3 }).click()
  const detail = page.getByRole('dialog', { name: debugItem.title })
  await expect(detail.getByRole('heading', { name: 'Debug 模板' })).toBeVisible()
  await expect(detail.getByText(/本地提取：Python 3.12 Ubuntu/)).toBeVisible()
  await detail.getByLabel('错误').fill('用户确认错误：requests 环境隔离')
  await detail.getByLabel('根因').fill('用户确认：shell 使用系统 Python')
  await detail.getByRole('button', { name: '保存用户确认值' }).click()
  await expect(page.getByText('用户确认值已保存')).toBeVisible()

  await detail.getByRole('button', { name: '重新本地提取' }).click()
  await expect(page.getByText('本地规则提取完成，用户确认值已保留')).toBeVisible()
  await expect(detail.getByText(/本地提取：重新提取的规则根因/)).toBeVisible()
  await expect(detail.getByLabel('根因')).toHaveValue('用户确认：shell 使用系统 Python')
  await expect(detail.getByText('本地模板提取', { exact: true })).toHaveCount(2)

  await detail.getByRole('button', { name: '查找相似资料' }).click()
  await expect(detail.getByText('#32 pytest 中 requests 缺失')).toBeVisible()
  await expect(detail.getByText('相似度 72%')).toBeVisible()
  await expect(detail.getByText('共同特征：requests、python')).toBeVisible()
  await detail.getByRole('button', { name: 'Close' }).click()

  await page.locator('.filters .el-select').first().click()
  await page.locator('.el-select-dropdown:visible').getByText('Debug', { exact: true }).click()
  await page.getByPlaceholder('按 Debug 错误字段筛选').fill('用户确认错误')
  await page.getByRole('button', { name: '搜索' }).click()
  await expect(page.getByRole('heading', { name: debugItem.title, level: 3 })).toBeVisible()

  await page.reload()
  await page.getByRole('heading', { name: debugItem.title, level: 3 }).click()
  await expect(page.getByLabel('错误')).toHaveValue('用户确认错误：requests 环境隔离')
  await page.getByRole('dialog', { name: debugItem.title }).getByRole('button', { name: 'Close' }).click()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Empty Workspace', { exact: true }).click()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await page.reload()
  await expect(page.getByText('工作区: Empty Workspace')).toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Debug Workspace', { exact: true }).click()
  await page.getByRole('heading', { name: debugItem.title, level: 3 }).click()
  await expect(page.getByLabel('根因')).toHaveValue('用户确认：shell 使用系统 Python')
})
