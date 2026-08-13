import { expect, test } from '@playwright/test'


const pngFixture = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFElEQVR4nGP8z8DAwMDAxMDAwMDAAAANHQEDasKb6QAAAABJRU5ErkJggg==',
  'base64',
)

const workspace = {
  id: 1, name: 'Image Fixture', db_path: '/fixture/image.db', item_count: 0, paper_count: 0,
}

const item = {
  id: 41,
  item_type: 'general',
  title: 'complete.png',
  content_text: '',
  summary: '用户导入图片',
  source_kind: 'image_import',
  source_url: null,
  status: 'inbox',
  tags: [],
  metadata: {},
  assets: [{
    id: 51, original_name: 'complete.png', mime_type: 'image/png',
    size_bytes: pngFixture.length, image_width: 2, image_height: 2,
  }],
  accepted_extractions: [],
  created_at: '2026-08-13 10:00:00',
}

test('image import errors are visible and OCR success/failure remain auditable', async ({ page }) => {
  let imported = false
  let uploadCount = 0
  let ocrCount = 0
  let runs = []

  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const json = (value, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })

    if (path === '/api/workspaces' && method === 'GET') {
      return json({ items: [workspace], active_path: workspace.db_path, active_name: workspace.name })
    }
    if (path === '/api/candidates') return json({ candidates: [] })
    if (path === '/api/collection-jobs') return json({ jobs: [] })
    if (path === '/api/items' && method === 'GET') {
      return json({ items: imported ? [item] : [], total: imported ? 1 : 0, page: 1, page_size: 20 })
    }
    if (path === '/api/items/import-image' && method === 'POST') {
      uploadCount += 1
      if (uploadCount === 1) {
        return json({ detail: '图片已损坏、格式伪装或无法完整解码' }, 400)
      }
      imported = true
      return json({ item, created: true, duplicate: false }, 200)
    }
    if (path === '/api/items/41' && method === 'GET') return json(item)
    if (path === '/api/assets/51/content') {
      return route.fulfill({ status: 200, contentType: 'image/png', body: pngFixture })
    }
    if (path === '/api/items/41/analysis-runs' && method === 'GET') return json({ runs })
    if (path === '/api/items/41/ocr-runs' && method === 'POST') {
      ocrCount += 1
      if (ocrCount === 1) {
        runs = [{
          id: 61, item_id: 41, processor: 'local_tesseract', processor_version: '1',
          run_kind: 'ocr', status: 'failed', input_scope: ['asset'], provider: 'local',
          model: 'tesseract', prompt_version: 'none', result: null,
          error_message: 'fixture OCR failure', created_at: '2026-08-13 10:01:00',
        }]
        return json({ detail: 'fixture OCR failure' }, 422)
      }
      const succeeded = {
        id: 62, item_id: 41, processor: 'local_tesseract', processor_version: '1',
        run_kind: 'ocr', status: 'succeeded', input_scope: ['asset'], provider: 'local',
        model: 'tesseract', prompt_version: 'none',
        result: { text: 'ResearchMate OCR 2026', character_count: 21 },
        error_message: null, created_at: '2026-08-13 10:02:00',
      }
      runs = [succeeded, ...runs]
      return json({ run: succeeded })
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  const input = page.locator('input[type="file"]')
  await input.setInputFiles({ name: 'fake.png', mimeType: 'image/png', buffer: Buffer.from('not-image') })
  await expect(page.getByText('图片已损坏、格式伪装或无法完整解码')).toBeVisible()
  await expect(page.getByText('当前工作区还没有通用资料')).toBeVisible()

  await input.setInputFiles({ name: 'complete.png', mimeType: 'image/png', buffer: pngFixture })
  await expect(page.getByText('图片已保存到本地工作区')).toBeVisible()
  await page.getByRole('heading', { name: 'complete.png', level: 3 }).click()
  await expect(page.getByRole('img', { name: 'complete.png' })).toBeVisible()

  await page.getByRole('button', { name: '运行本地 OCR' }).click()
  await expect(page.locator('.run-error').getByText('fixture OCR failure', { exact: true })).toBeVisible()
  await expect(page.getByText('失败', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '运行本地 OCR' }).click()
  await expect(page.getByText('ResearchMate OCR 2026', { exact: true })).toBeVisible()
  await expect(page.getByText('成功', { exact: true })).toBeVisible()
})

test('explicit OCR reprocessing creates history without replacing accepted text', async ({ page }) => {
  const acceptedRun = {
    id: 71, item_id: 41, processor: 'local_tesseract', processor_version: '1',
    run_kind: 'ocr', status: 'succeeded', input_scope: ['asset'], provider: 'local',
    model: 'tesseract', prompt_version: 'none',
    result: { text: '已接受的旧 OCR', character_count: 10 },
    error_message: null, created_at: '2026-08-13 11:00:00',
  }
  const accepted = {
    extraction_kind: 'ocr', run_id: acceptedRun.id, text_value: acceptedRun.result.text,
  }
  const acceptedItem = { ...item, accepted_extractions: [accepted] }
  let runs = [acceptedRun]
  let reprocessCount = 0

  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    const json = (value, status = 200) => route.fulfill({
      status, contentType: 'application/json', body: JSON.stringify(value),
    })

    if (path === '/api/workspaces' && method === 'GET') {
      return json({ items: [workspace], active_path: workspace.db_path, active_name: workspace.name })
    }
    if (path === '/api/candidates') return json({ candidates: [] })
    if (path === '/api/collection-jobs') return json({ jobs: [] })
    if (path === '/api/items' && method === 'GET') {
      return json({ items: [acceptedItem], total: 1, page: 1, page_size: 20 })
    }
    if (path === '/api/items/41' && method === 'GET') return json(acceptedItem)
    if (path === '/api/assets/51/content') {
      return route.fulfill({ status: 200, contentType: 'image/png', body: pngFixture })
    }
    if (path === '/api/items/41/analysis-runs' && method === 'GET') return json({ runs })
    if (path === '/api/items/41/ocr-runs' && method === 'POST') {
      reprocessCount += 1
      if (reprocessCount === 1) {
        const succeeded = {
          ...acceptedRun,
          id: 72,
          result: { text: '尚未接受的新 OCR', character_count: 11 },
          created_at: '2026-08-13 11:01:00',
        }
        runs = [succeeded, ...runs]
        return json({ run: succeeded })
      }
      const failed = {
        ...acceptedRun,
        id: 73,
        status: 'failed',
        result: null,
        error_message: '重新处理 fixture 失败',
        created_at: '2026-08-13 11:02:00',
      }
      runs = [failed, ...runs]
      return json({ detail: failed.error_message }, 422)
    }
    return json({ detail: `Unhandled fixture route: ${method} ${path}` }, 500)
  })

  await page.goto('/materials')
  await page.getByRole('heading', { name: 'complete.png', level: 3 }).click()
  await expect(page.getByText('每次点击都会新建一条本地 OCR 审计运行')).toBeVisible()
  await expect(page.getByRole('button', { name: '重新运行本地 OCR' })).toBeVisible()
  await expect(page.getByText('当前已接受')).toBeVisible()

  await page.getByRole('button', { name: '重新运行本地 OCR' }).click()
  await expect(page.getByText('新的 OCR 审计运行已完成；已接受文本未改变')).toBeVisible()
  await expect(page.getByText('尚未接受的新 OCR', { exact: true })).toBeVisible()
  await expect(page.getByText('当前接受的是运行 #71')).toBeVisible()
  await expect(page.getByText('当前已接受')).toHaveCount(0)

  await page.getByRole('button', { name: '重新运行本地 OCR' }).click()
  await expect(page.locator('.run-error').getByText('重新处理 fixture 失败')).toBeVisible()
  await expect(page.getByText('当前接受的是运行 #71')).toBeVisible()
  await expect(page.locator('.run-card')).toHaveCount(3)
  expect(reprocessCount).toBe(2)
})
