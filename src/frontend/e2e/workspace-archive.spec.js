import { expect, test } from '@playwright/test'


const initial = {
  id: 1, name: 'Portable Source', db_path: '/fixture/source.db', item_count: 0, paper_count: 0,
}
const imported = {
  id: 2, name: 'Portable Imported', db_path: '/fixture/imported.db', item_count: 1, paper_count: 0,
}
const importedItem = {
  id: 201, item_type: 'general', title: 'Portable image fixture', content_text: '',
  summary: '用户导入图片', source_kind: 'image_import', source_url: null,
  status: 'inbox', tags: [], metadata: {},
  assets: [{ id: 301, original_name: 'portable.png', mime_type: 'image/png' }],
  created_at: '2026-08-13 12:00:00',
}

test('workspace archive export and import errors are visible before a successful switch', async ({ page }) => {
  let active = initial
  let exportCount = 0
  let importCount = 0

  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const json = (value, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })

    if (path === '/api/workspaces' && method === 'GET') {
      return json({
        items: active === initial ? [initial] : [imported, initial],
        active_path: active.db_path,
        active_name: active.name,
      })
    }
    if (path === '/api/items' && method === 'GET') {
      const items = active === imported ? [importedItem] : []
      return json({ items, total: items.length, page: 1, page_size: 20 })
    }
    if (path === '/api/candidates') return json({ candidates: [] })
    if (path === '/api/collection-jobs') return json({ jobs: [] })
    if (path === '/api/workspace/export' && method === 'GET') {
      exportCount += 1
      if (exportCount === 1) {
        return json({ detail: '图片资产哈希与数据库记录不一致' }, 422)
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/zip',
        headers: { 'Content-Disposition': 'attachment; filename="source.researchmate.zip"' },
        body: Buffer.from('offline portable archive'),
      })
    }
    if (path === '/api/workspace/import' && method === 'POST') {
      importCount += 1
      if (importCount === 1) {
        return json({ detail: '归档包含缺失、重复或未声明的文件' }, 400)
      }
      active = imported
      return json({
        ok: true, name: imported.name, db_path: imported.db_path,
        legacy_database_only: false,
      })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  await page.getByRole('button', { name: '切换' }).click()
  await expect(page.getByText('完整归档包含工作区数据库和用户导入的图片资产')).toBeVisible()

  await page.getByRole('button', { name: '导出完整归档' }).click()
  await expect(page.getByText('图片资产哈希与数据库记录不一致')).toBeVisible()

  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出完整归档' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('Portable Source.researchmate.zip')

  const input = page.locator('input[type="file"][accept*=".zip"]')
  await input.setInputFiles({
    name: 'broken.researchmate.zip', mimeType: 'application/zip', buffer: Buffer.from('broken'),
  })
  await expect(page.getByText('归档包含缺失、重复或未声明的文件')).toBeVisible()

  await input.setInputFiles({
    name: 'portable.researchmate.zip', mimeType: 'application/zip',
    buffer: Buffer.from('valid offline archive fixture'),
  })
  await expect(page.getByText('工作区: Portable Imported')).toBeVisible()
  await expect(page.getByRole('heading', { name: importedItem.title, level: 3 })).toBeVisible()
  await expect(page.getByText('已导入: Portable Imported')).toBeVisible()
})
