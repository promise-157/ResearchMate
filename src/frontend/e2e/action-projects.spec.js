import { expect, test } from '@playwright/test'


const workspaces = [
  { id: 1, name: 'Action Workspace', db_path: '/fixture/actions.db', item_count: 3, paper_count: 0 },
  { id: 2, name: 'Empty Workspace', db_path: '/fixture/actions-empty.db', item_count: 0, paper_count: 0 },
]

const materials = Array.from({ length: 3 }, (_, index) => ({
  id: index + 1,
  item_type: 'general',
  title: `证据资料 ${index + 1}`,
  content_text: `immutable source fact ${index + 1}`,
  summary: `用于行动专题的离线证据 ${index + 1}`,
  source_kind: 'text_import',
  source_url: null,
  status: 'active',
  tags: [],
  metadata: {},
  assets: [],
  accepted_extractions: [],
  has_accepted_extraction: false,
  created_at: '2026-08-13 16:00:00',
}))

test('selected materials become an editable, ordered and isolated action project', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let project = null
  let updateAttempts = 0

  const projectSummary = () => project && {
    ...project,
    material_count: project.materials.length,
    materials: undefined,
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
      const visible = activePath === workspaces[0].db_path ? materials : []
      return json({ items: visible, total: visible.length, page: 1, page_size: 20 })
    }
    const itemMatch = path.match(/^\/api\/items\/(\d+)$/)
    if (itemMatch && method === 'GET') return json(materials[Number(itemMatch[1]) - 1])
    if (/^\/api\/items\/\d+\/analysis-runs$/.test(path)) return json({ runs: [] })

    if (path === '/api/action-projects' && method === 'POST') {
      const body = request.postDataJSON()
      expect(body.item_ids).toEqual([1, 2])
      project = {
        id: 91,
        title: body.title,
        objective: body.objective,
        notes: body.notes,
        next_action: body.next_action,
        status: 'active',
        materials: body.item_ids.map((id, position) => ({ ...materials[id - 1], position })),
        material_count: body.item_ids.length,
        created_at: '2026-08-13 16:10:00',
        updated_at: '2026-08-13 16:10:00',
      }
      return json({ project }, 201)
    }
    if (path === '/api/action-projects' && method === 'GET') {
      const visible = activePath === workspaces[0].db_path && project ? [projectSummary()] : []
      return json({ projects: visible })
    }
    if (path === '/api/action-projects/91' && method === 'GET') return json({ project })
    if (path === '/api/action-projects/91' && method === 'PATCH') {
      updateAttempts += 1
      if (updateAttempts === 1) return json({ detail: 'fixture 专题保存失败' }, 400)
      project = {
        ...project,
        ...request.postDataJSON(),
        updated_at: '2026-08-13 16:20:00',
      }
      return json({ project })
    }
    if (path === '/api/action-projects/91/materials' && method === 'PUT') {
      const ids = request.postDataJSON().item_ids
      project = {
        ...project,
        materials: ids.map((id, position) => ({ ...materials[id - 1], position })),
        material_count: ids.length,
        updated_at: '2026-08-13 16:30:00',
      }
      return json({ project })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  const checkboxes = page.locator('.material-card > .el-checkbox')
  await checkboxes.nth(0).click()
  await checkboxes.nth(1).click()
  await page.getByRole('button', { name: '建立行动专题（2）' }).click()
  const createDialog = page.getByRole('dialog', { name: '从所选资料建立行动专题' })
  await expect(createDialog.getByText('#1 证据资料 1')).toBeVisible()
  await expect(createDialog.getByText('#2 证据资料 2')).toBeVisible()
  await createDialog.getByLabel('专题标题').fill('选择本地检索方案')
  await createDialog.getByLabel('目标').fill('基于现有证据决定是否引入 FTS')
  await createDialog.getByLabel('用户笔记').fill('先测量，再决定。')
  await createDialog.getByLabel('明确下一步').fill('比较 5 万条数据的延迟与体积')
  await createDialog.getByRole('button', { name: '创建并打开专题' }).click()

  await expect(page).toHaveURL(/\/actions\?project=91/)
  await expect(page.getByRole('heading', { name: '选择本地检索方案', level: 2 })).toBeVisible()
  await expect(page.locator('.evidence-item')).toHaveCount(2)

  await page.getByLabel('用户笔记 / 当前结论').fill('结论：当前规模继续使用 LIKE。')
  await page.getByLabel('明确下一步').fill('超过 5 万条或 p95 超过 100ms 时重测')
  await page.getByRole('button', { name: '保存专题' }).click()
  await expect(page.getByText('fixture 专题保存失败')).toBeVisible()
  await page.getByRole('button', { name: '保存专题' }).click()
  await expect(page.getByText('行动专题已保存')).toBeVisible()

  await page.locator('.project-status').click()
  await page.locator('.el-select-dropdown:visible').getByText('已完成', { exact: true }).click()
  await expect(page.getByText('已完成', { exact: true }).first()).toBeVisible()

  await page.locator('.evidence-item').first().getByRole('button', { name: '下移' }).click()
  await expect(page.locator('.evidence-item').first()).toContainText('#2 证据资料 2')
  await page.getByRole('button', { name: '添加证据' }).click()
  const evidenceDialog = page.getByRole('dialog', { name: '编辑证据清单' })
  await evidenceDialog.locator('.evidence-option').filter({ hasText: '#3 证据资料 3' }).locator('.el-checkbox').click()
  await evidenceDialog.getByRole('button', { name: '保存证据清单' }).click()
  await expect(page.locator('.evidence-item')).toHaveCount(3)
  await expect(page.locator('.evidence-item').nth(2)).toContainText('#3 证据资料 3')

  await page.locator('.evidence-item').nth(1).getByRole('button', { name: '移除' }).click()
  await expect(page.locator('.evidence-item')).toHaveCount(2)
  expect(materials[0].content_text).toBe('immutable source fact 1')

  await page.reload()
  await expect(page.getByLabel('用户笔记 / 当前结论')).toHaveValue('结论：当前规模继续使用 LIKE。')
  await expect(page.locator('.evidence-item').first()).toContainText('#2 证据资料 2')
  await expect(page.locator('.evidence-item').nth(1)).toContainText('#3 证据资料 3')

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Empty Workspace', { exact: true }).click()
  await expect(page.getByText('当前工作区还没有行动专题')).toBeVisible()
  await page.reload()
  await expect(page.getByText('工作区: Empty Workspace')).toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Action Workspace', { exact: true }).click()
  await expect(page.getByLabel('明确下一步')).toHaveValue('超过 5 万条或 p95 超过 100ms 时重测')

  await page.locator('.evidence-item').first().getByRole('link').click()
  await expect(page).toHaveURL(/\/materials\?item=2/)
  await expect(page.getByRole('dialog', { name: '证据资料 2' })).toBeVisible()
})
