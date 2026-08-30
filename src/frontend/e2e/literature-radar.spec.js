import { expect, test } from '@playwright/test'

const workspaces = [
  { id: 1, name: 'Radar A', db_path: '/fixture/radar-a.db', item_count: 0, paper_count: 0 },
  { id: 2, name: 'Radar B', db_path: '/fixture/radar-b.db', item_count: 0, paper_count: 0 },
]

test('Crossref radar confirms bounded conditions and preserves review state offline', async ({ page }) => {
  let activePath = workspaces[0].db_path
  let jobs = []
  let candidates = []
  let rules = []
  const requests = []
  const enrichmentRequests = []
  const codeRequests = []
  const rankingRequests = []
  const briefRequests = []
  let briefs = []
  await page.route('http://127.0.0.1:4173/api/**', async (route) => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname
    const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
    if (path === '/api/workspaces') return json({ items: workspaces, active_path: activePath, active_name: activePath.includes('a.db') ? 'Radar A' : 'Radar B' })
    if (path === '/api/workspaces/load') { activePath = url.searchParams.get('db_path'); return json({ success: true }) }
    if (path === '/api/collection-jobs') return json({ jobs: activePath.includes('a.db') ? jobs : [] })
    if (path === '/api/discovery-rules' && request.method() === 'GET') return json({ rules: activePath.includes('a.db') ? rules : [] })
    if (path === '/api/discoveries/candidates/briefs' && request.method() === 'GET') return json({ runs: activePath.includes('a.db') ? briefs : [] })
    if (path === '/api/discoveries/candidates/rank') { const body = request.postDataJSON(); rankingRequests.push(body); return json({ ranking: body.candidate_ids.map((id) => ({ candidate_id: id, score: id === 301 ? 90 : 15, reasons: id === 301 ? ['标题包含完整关注词 +45', '有可追溯摘要 +10'] : ['本工作区新发现 +15'] })) }) }
    if (path === '/api/discoveries/candidates/briefs' && request.method() === 'POST') { const body = request.postDataJSON(); briefRequests.push(body); const run = { id: 81, status: 'succeeded', candidate_ids: body.candidate_ids, result: { overview: '优先核对 MIGHTY', priorities: [{ candidate_id: 301, reason: '证据更完整' }], caveats: '没有阅读全文' } }; briefs = [run]; return json({ ok: true, run }, 201) }
    if (path === '/api/discovery-rules' && request.method() === 'POST') { const body = request.postDataJSON(); const rule = { id: 71, name: body.name, source_kind: 'crossref_ieee', query: body.query }; rules = [rule]; return json(rule, 201) }
    if (path === '/api/discovery-rules/71/run') { const job = { id: 72, collector: 'crossref_ieee', status: 'succeeded', candidate_count: 0, query: rules[0].query, result: { empty: true } }; jobs = [job, ...jobs]; rules[0] = { ...rules[0], last_run_status: 'succeeded', last_success_at: '2026-08-30T00:00:00+00:00' }; return json({ job, candidates: [] }, 201) }
    if (path === '/api/discovery-rules/run') return json({ results: rules.map((rule) => ({ rule_id: rule.id, status: 'succeeded', candidate_count: 0 })) }, 201)
    if (path === '/api/discovery-rules/71' && request.method() === 'PUT') { const body = request.postDataJSON(); rules[0] = { ...rules[0], ...body }; return json(rules[0]) }
    if (path === '/api/discovery-rules/71' && request.method() === 'DELETE') { rules = []; return route.fulfill({ status: 204 }) }
    if (path === '/api/candidates' && request.method() === 'GET') return json({ candidates: activePath.includes('a.db') ? candidates.filter((item) => item.status === 'pending') : [] })
    if (path === '/api/discoveries/crossref') {
      const body = request.postDataJSON(); requests.push(body)
      if (requests.length === 1) {
        jobs = [{ id: 30, collector: 'crossref_ieee', status: 'failed', candidate_count: 0, query: body, result: {}, error_message: 'fixture Crossref timeout' }]
        return json({ detail: 'fixture Crossref timeout' }, 422)
      }
      if (body.query === 'no fixture results') {
        const emptyJob = { id: 32, collector: 'crossref_ieee', status: 'succeeded', candidate_count: 0, query: body, result: { truncated: false, skipped_count: 0, empty: true } }
        jobs = [emptyJob, ...jobs]
        return json({ job: emptyJob, candidates: [] }, 201)
      }
      const candidate = { id: 301, job_id: 31, title: 'MIGHTY Fixture', summary: '', source_kind: 'crossref_ieee', source_url: 'https://doi.org/10.1109/lra.2026.3681187', status: 'pending', source_records: [], source_facts: { doi: '10.1109/lra.2026.3681187', container_title: 'IEEE Robotics and Automation Letters', issn: ['2377-3766'], authors: ['Fixture Author'], work_type: 'journal-article', published: '2026-07-01', result_position: 1, has_abstract: false } }
      const seen = { id: 302, job_id: 31, title: 'Previously Rejected Fixture', summary: '', source_kind: 'crossref_ieee', source_url: 'https://doi.org/10.1109/lra.2026.1', status: 'pending', source_records: [], source_facts: { doi: '10.1109/lra.2026.1', existing_candidate_id: 99, existing_candidate_status: 'rejected', existing_candidate_seen_at: '2026-08-01' } }
      candidates = [candidate, seen]
      jobs = [{ id: 31, collector: 'crossref_ieee', status: 'succeeded', candidate_count: 2, query: body, result: { truncated: true, skipped_count: 2, empty: false } }, ...jobs]
      return json({ job: jobs[0], candidates }, 201)
    }
    if (path === '/api/discoveries/openalex/enrich') {
      const body = request.postDataJSON(); enrichmentRequests.push(body)
      candidates[0].source_records = [
        { id: 402, source_kind: 'arxiv_version', status: 'succeeded', source_record_id: '2511.10822v1', error_message: null, facts: { arxiv_id: '2511.10822v1', source_url: 'https://arxiv.org/abs/2511.10822v1', abstract: 'Strictly matched public preprint abstract', published: '2025-11-14T00:00:00Z', matched_authors: ['fixture author'] } },
        { id: 401, source_kind: 'openalex', status: 'succeeded', source_record_id: 'W123', error_message: null, facts: { abstract: '', institutions: ['Robotics Lab'], topics: ['Motion Planning'], is_open_access: true, oa_status: 'green', best_open_url: 'https://repository.example/paper', primary_source: 'IEEE RA-L' } },
      ]
      const job = { id: 40, collector: 'openalex_enrichment', status: 'succeeded', candidate_count: 1, query: { candidates: [{ candidate_id: 301, doi: '10.1109/lra.2026.3681187', title: 'MIGHTY Fixture' }] }, result: { requested_count: 1, succeeded_count: 1, failed_count: 0, partial: false, arxiv_checked_count: 1, arxiv_succeeded_count: 1, arxiv_failed_count: 0 } }
      jobs = [job, ...jobs]
      return json({ job, candidates }, 201)
    }
    if (path === '/api/discoveries/code/evidence') {
      const body = request.postDataJSON(); codeRequests.push(body)
      candidates[0].source_records = [{ id: 403, source_kind: 'github_code', status: 'succeeded', source_record_id: 'candidate:301', error_message: null, facts: { repositories: [{ repository_url: 'https://github.com/mit-acl/mighty', full_name: 'mit-acl/mighty', level: 'strong_identifier', matched_fields: ['doi'], license_spdx: 'BSD-3-Clause', archived: false, stars: 42 }] } }, ...candidates[0].source_records]
      const job = { id: 41, collector: 'github_code_evidence', status: 'succeeded', candidate_count: 1, query: { candidates: [{ candidate_id: 301, doi: '10.1109/lra.2026.3681187', title: 'MIGHTY Fixture' }] }, result: { requested_count: 1, succeeded_count: 1, failed_count: 0, found_count: 1, not_found_count: 0, partial: false } }
      jobs = [job, ...jobs]
      return json({ job, candidates }, 201)
    }
    if (path === '/api/candidates/301/reject') { candidates[0].status = 'rejected'; return json(candidates[0]) }
    return json({ detail: `Unhandled ${request.method()} ${path}` }, 500)
  })

  await page.goto('/literature-radar')
  await page.getByLabel('主题关键词').fill('Hermite spline trajectory planning')
  await page.getByLabel('开始日期').fill('2026-01-01')
  await page.getByLabel('结束日期').fill('2026-08-29')
  await page.getByLabel('期刊/会议（可选）').fill('Robotics and Automation Letters')
  await page.getByLabel('ISSN（可选）').fill('2377-3766')
  await page.getByRole('spinbutton', { name: '本次最大返回数' }).fill('5')
  await expect(page.getByText(/IEEE 期刊；按进入 Crossref 索引日期查 2026-01-01 至 2026-08-29/)).toBeVisible()
  await page.getByRole('button', { name: '保存当前条件' }).click()
  await page.getByPlaceholder('规则名称').fill('轨迹规划追踪')
  await page.getByRole('button', { name: '保存规则' }).click()
  await expect(page.getByText('轨迹规划追踪')).toBeVisible()
  await page.getByRole('button', { name: '手动运行' }).click()
  await expect(page.getByText('上次成功 2026-08-30')).toBeVisible()
  await page.getByRole('button', { name: '运行全部' }).click()
  await expect(page.getByText(/将按顺序运行 1 条规则/)).toBeVisible()
  await page.getByRole('button', { name: '确认并运行全部' }).click()
  await page.getByRole('button', { name: '编辑' }).click()
  await page.getByPlaceholder('规则名称').fill('轨迹规划增量追踪')
  await page.getByRole('button', { name: '更新规则' }).click()
  await expect(page.getByText('轨迹规划增量追踪')).toBeVisible()
  await page.getByRole('button', { name: '确认条件并检索' }).click()
  await expect(page.getByText('fixture Crossref timeout').first()).toBeVisible()
  await page.getByRole('button', { name: '确认条件并检索' }).click()
  await expect(page.getByRole('heading', { name: 'MIGHTY Fixture' })).toBeVisible()
  await expect(page.getByText('Previously Rejected Fixture')).not.toBeVisible()
  await page.getByText('显示以前见过的结果（1）').click()
  await expect(page.getByText('Previously Rejected Fixture')).toBeVisible()
  await expect(page.getByText('以前拒绝')).toBeVisible()
  await page.getByText('显示以前见过的结果（1）').click()
  await expect(page.getByText('公开索引未提供摘要')).toBeVisible()
  await expect(page.getByText('结果已截断')).toBeVisible()
  await expect(page.getByText('跳过 2 条')).toBeVisible()
  expect(requests[1]).toMatchObject({ intent: 'topic', query: 'Hermite spline trajectory planning', scope: 'journal', date_from: '2026-01-01', date_to: '2026-08-29', date_basis: 'indexed', container_title: 'Robotics and Automation Letters', issn: '2377-3766', sort: 'relevance', limit: 5 })
  await page.locator('.candidate-row .el-checkbox').click()
  await page.getByRole('button', { name: '补全所选（1）' }).click()
  await expect(page.getByText(/#301 · 10.1109\/lra.2026.3681187 · MIGHTY Fixture/)).toBeVisible()
  await expect(page.getByText(/不会覆盖 Crossref 标题、摘要或候选状态/)).toBeVisible()
  await page.getByRole('button', { name: '确认并补全' }).click()
  await expect(page.getByText('OpenAlex 未提供摘要')).toBeVisible()
  await expect(page.getByText('Strictly matched public preprint abstract')).toBeVisible()
  await expect(page.getByText(/标题完全一致，作者 fixture author 一致/)).toBeVisible()
  await expect(page.getByText(/机构：Robotics Lab/)).toBeVisible()
  expect(enrichmentRequests).toEqual([{ candidate_ids: [301] }])
  await page.locator('.candidate-row .el-checkbox').click()
  await page.getByRole('button', { name: '查源码（1）' }).click()
  await expect(page.getByText(/不会克隆仓库、下载代码或保存 README/)).toBeVisible()
  await page.getByRole('button', { name: '确认并检查' }).click()
  await expect(page.getByRole('link', { name: 'mit-acl/mighty' })).toHaveAttribute('href', 'https://github.com/mit-acl/mighty')
  await expect(page.getByText('强身份关联')).toBeVisible()
  await expect(page.getByText(/README 含同一 DOI/)).toBeVisible()
  expect(codeRequests).toEqual([{ candidate_ids: [301] }])
  await page.getByText('显示以前见过的结果（1）').click()
  await page.getByRole('heading', { name: 'MIGHTY Fixture' }).locator('xpath=..').locator('.el-checkbox').click()
  await page.getByRole('heading', { name: 'Previously Rejected Fixture' }).locator('xpath=..').locator('.el-checkbox').click()
  await page.getByRole('button', { name: '本地解释排序（2）' }).click()
  await expect(page.getByText('本地确定性评分 90')).toBeVisible()
  await expect(page.getByText(/标题包含完整关注词 \+45/)).toBeVisible()
  expect(rankingRequests[0].candidate_ids).toEqual([301, 302])
  await page.getByRole('button', { name: 'AI 候选简报（2）' }).click()
  await expect(page.getByText(/最佳可追溯摘要（每篇最多 2000 字）/)).toBeVisible()
  await page.getByRole('button', { name: '确认并生成简报' }).click()
  await expect(page.getByText('优先核对 MIGHTY')).toBeVisible()
  await expect(page.getByText(/#301 证据更完整/)).toBeVisible()
  expect(briefRequests[0].candidate_ids).toEqual([301, 302])
  await page.getByText('显示以前见过的结果（1）').click()
  const requestsBeforeContext = requests.length
  await page.getByRole('button', { name: '查首位作者' }).click()
  await expect(page.getByLabel('作者姓名')).toHaveValue('Fixture Author')
  await expect(page.getByText(/搜索作者“Fixture Author”/).first()).toBeVisible()
  expect(requests).toHaveLength(requestsBeforeContext)
  await page.getByRole('button', { name: '查同一期刊' }).click()
  expect(requests).toHaveLength(requestsBeforeContext)

  await page.getByText('指定期刊最新', { exact: true }).click()
  await expect(page.getByLabel('主题关键词')).not.toBeVisible()
  await expect(page.getByText(/查看 IEEE Robotics and Automation Letters 的最新论文/).first()).toBeVisible()
  await page.getByRole('button', { name: '确认条件并检索' }).click()
  expect(requests[2]).toMatchObject({ intent: 'journal_latest', query: null, container_title: 'IEEE Robotics and Automation Letters', issn: '2377-3766' })

  await page.getByText('标题或 DOI 精确查找', { exact: true }).click()
  await page.getByLabel('完整标题或 DOI').fill('10.1109/LRA.2026.3681187')
  await expect(page.getByText(/最多返回 1 条/).first()).toBeVisible()
  await page.getByRole('button', { name: '确认条件并检索' }).click()
  expect(requests[3]).toMatchObject({ intent: 'exact', query: '10.1109/LRA.2026.3681187', date_from: null, date_to: null, limit: 1 })

  await page.getByText('主题搜索', { exact: true }).click()
  await page.getByText('IEEE Robotics and Automation Letters', { exact: true }).first().click()
  await page.getByText('IEEE Access', { exact: true }).click()
  await expect(page.getByLabel('期刊/会议（可选）')).toHaveValue('IEEE Access')
  await expect(page.getByLabel('ISSN（可选）')).toHaveValue('2169-3536')
  const requestCountBeforePreset = requests.length
  await page.getByRole('button', { name: '最近 7 天' }).click()
  expect(requests).toHaveLength(requestCountBeforePreset)
  const expectedTo = new Date().toISOString().slice(0, 10)
  const expectedFromDate = new Date(`${expectedTo}T00:00:00Z`); expectedFromDate.setUTCDate(expectedFromDate.getUTCDate() - 6)
  await expect(page.getByLabel('开始日期')).toHaveValue(expectedFromDate.toISOString().slice(0, 10))
  await expect(page.getByLabel('结束日期')).toHaveValue(expectedTo)
  await page.getByLabel('主题关键词').fill('no fixture results')
  await page.getByRole('button', { name: '确认条件并检索' }).click()
  await expect(page.getByText('当前主题和筛选条件没有结果，可扩大日期或移除期刊限制。')).toBeVisible()
  const requestCountBeforeSuggestion = requests.length
  await page.getByRole('button', { name: '移除期刊限制' }).click()
  expect(requests).toHaveLength(requestCountBeforeSuggestion)
  await expect(page.getByLabel('期刊/会议（可选）')).toHaveValue('')
  await expect(page.getByLabel('ISSN（可选）')).toHaveValue('')
  await page.getByText('精确查找：10.1109/LRA.2026.3681187').locator('xpath=..').getByRole('button', { name: '载入并修改' }).click()
  await expect(page.getByLabel('完整标题或 DOI')).toHaveValue('10.1109/LRA.2026.3681187')
  expect(requests).toHaveLength(requestCountBeforeSuggestion)

  await page.reload()
  await expect(page.getByRole('heading', { name: 'MIGHTY Fixture' })).toBeVisible()
  await page.getByRole('button', { name: '切换' }).click(); await page.getByText('Radar B', { exact: true }).click()
  await expect(page.getByText('当前没有待审核候选')).toBeVisible()
  await page.getByRole('button', { name: '切换' }).click(); await page.getByText('Radar A', { exact: true }).click()
  await page.getByRole('heading', { name: 'MIGHTY Fixture' }).locator('xpath=../..').getByRole('button', { name: '拒绝' }).click()
  await expect(page.getByRole('heading', { name: 'MIGHTY Fixture' })).not.toBeVisible()
  await page.getByRole('button', { name: '删除' }).click()
  await expect(page.getByText('尚未保存规则')).toBeVisible()
})
