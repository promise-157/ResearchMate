import { expect, test } from '@playwright/test'


const workspaces = [
  { id: 1, name: 'Job Workspace', db_path: '/fixture/jobs.db', item_count: 1, paper_count: 0 },
  { id: 2, name: 'Empty Workspace', db_path: '/fixture/empty.db', item_count: 0, paper_count: 0 },
]

const jobItem = {
  id: 9,
  item_type: 'job',
  title: '星河科技后端工程师',
  content_text: '公司: 星河科技\n岗位: 后端工程师\n投递状态: 待投递',
  summary: '星河科技后端工程师招聘描述',
  source_kind: 'text_import',
  source_url: null,
  status: 'active',
  tags: ['求职'],
  metadata: { classification: { suggested_type: 'job', method: 'rules-v1' } },
  assets: [],
  accepted_extractions: [],
  created_at: '2026-08-07 11:00:00',
}

test('job confirmation, filtering and workspace isolation survive refresh', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let extractedCompany = '星河科技'
  let confirmed = {}
  let extractionShouldFail = true

  const template = () => ({
    item_id: jobItem.id,
    template_key: 'job',
    schema_version: 1,
    extracted: {
      company: extractedCompany,
      role: '后端工程师',
      location: '上海',
      salary: '30k-45k·14薪',
      skills: 'Python, FastAPI, SQLite',
      experience: '3-5年',
      application_status: '待投递',
    },
    confirmed,
    effective: {
      company: extractedCompany,
      role: '后端工程师',
      location: '上海',
      salary: '30k-45k·14薪',
      skills: 'Python, FastAPI, SQLite',
      experience: '3-5年',
      application_status: '待投递',
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
    if (path === '/api/items' && method === 'GET') {
      const company = url.searchParams.get('job_company')
      const role = url.searchParams.get('job_role')
      const applicationStatus = url.searchParams.get('job_application_status')
      const effective = template().effective
      const matches = activePath === workspaces[0].db_path
        && (!company || effective.company.includes(company))
        && (!role || effective.role.includes(role))
        && (!applicationStatus || effective.application_status.includes(applicationStatus))
      return json({
        items: matches ? [{ ...jobItem, has_accepted_extraction: false }] : [],
        total: matches ? 1 : 0,
        page: 1,
        page_size: 20,
      })
    }
    if (path === '/api/items/9' && method === 'GET') return json(jobItem)
    if (path === '/api/items/9/analysis-runs') return json({ runs: [] })
    if (path === '/api/items/9/template' && method === 'GET') return json(template())
    if (path === '/api/items/9/template/confirmation' && method === 'PUT') {
      confirmed = Object.fromEntries(
        Object.entries(request.postDataJSON()).filter(([, value]) => value?.trim()),
      )
      return json(template())
    }
    if (path === '/api/items/9/template/extract' && method === 'POST') {
      if (extractionShouldFail) {
        extractionShouldFail = false
        return json({ detail: 'fixture 本地模板提取失败' }, 422)
      }
      extractedCompany = '源文本中的新公司名'
      return json(template())
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  await page.getByRole('heading', { name: jobItem.title, level: 3 }).click()
  await expect(page.getByRole('heading', { name: '求职模板' })).toBeVisible()
  await page.getByLabel('公司').fill('用户确认公司')
  await page.getByLabel('投递状态').fill('已投递')
  await page.getByRole('button', { name: '保存用户确认值' }).click()
  await expect(page.getByText('用户确认值已保存')).toBeVisible()

  await page.getByRole('button', { name: '重新本地提取' }).click()
  await expect(page.getByText('fixture 本地模板提取失败')).toBeVisible()
  await page.getByRole('button', { name: '重新本地提取' }).click()
  await expect(page.getByText(/本地提取：源文本中的新公司名/)).toBeVisible()
  await expect(page.getByLabel('公司')).toHaveValue('用户确认公司')

  const detailDialog = page.getByRole('dialog', { name: jobItem.title })
  await detailDialog.getByRole('button', { name: 'Close' }).click()
  await expect(detailDialog).toBeHidden()
  await page.locator('.filters .el-select').first().click()
  await page.getByText('求职', { exact: true }).last().click()
  await page.getByPlaceholder('按公司筛选').fill('用户确认')
  await page.getByPlaceholder('按岗位筛选').fill('后端')
  await page.getByPlaceholder('按投递状态筛选').fill('已投递')
  await page.getByRole('button', { name: '搜索' }).click()
  await expect(page.getByRole('heading', { name: jobItem.title, level: 3 })).toBeVisible()

  await page.reload()
  await page.getByRole('heading', { name: jobItem.title, level: 3 }).click()
  await expect(page.getByLabel('公司')).toHaveValue('用户确认公司')
  await detailDialog.getByRole('button', { name: 'Close' }).click()
  await expect(detailDialog).toBeHidden()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Empty Workspace', { exact: true }).click()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()
  await page.reload()
  await expect(page.getByText('工作区: Empty Workspace')).toBeVisible()

  await page.getByRole('button', { name: '切换' }).click()
  await page.getByText('Job Workspace', { exact: true }).click()
  await page.getByRole('heading', { name: jobItem.title, level: 3 }).click()
  await expect(page.getByLabel('公司')).toHaveValue('用户确认公司')
})
