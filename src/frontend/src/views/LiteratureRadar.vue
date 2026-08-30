<template>
  <div class="radar-page">
    <div class="page-head">
      <div><h1 class="page-title">论文雷达</h1><p class="text-secondary">明确提交公开元数据检索；候选经审核后才进入资料库。</p></div>
      <el-button :loading="loading" @click="loadData">刷新</el-button>
    </div>
    <WorkspaceManager unit="项" @workspace-changed="reloadWorkspace" />

    <section class="card search-card">
      <el-tabs v-model="source">
        <el-tab-pane label="IEEE 正式论文（Crossref）" name="crossref" />
        <el-tab-pane label="arXiv 预印本" name="arxiv" />
      </el-tabs>
      <el-form v-if="source === 'crossref'" label-position="top">
        <el-form-item label="搜索方式"><el-radio-group v-model="crossref.intent"><el-radio-button value="topic">主题搜索</el-radio-button><el-radio-button value="author">作者搜索</el-radio-button><el-radio-button value="journal_latest">指定期刊最新</el-radio-button><el-radio-button value="exact">标题或 DOI 精确查找</el-radio-button></el-radio-group></el-form-item>
        <el-form-item v-if="crossref.intent !== 'journal_latest'" :label="crossref.intent === 'exact' ? '完整标题或 DOI' : crossref.intent === 'author' ? '作者姓名' : '主题关键词'"><el-input v-model="crossref.query" maxlength="200" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="文献类型"><el-select v-model="crossref.scope"><el-option label="IEEE 期刊" value="journal" /><el-option label="IEEE 期刊 + 会议" value="journal_conference" /></el-select></el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" label="排序"><el-select v-model="crossref.sort"><el-option label="相关度" value="relevance" /><el-option label="发表时间" value="published" /><el-option label="索引时间" value="indexed" /></el-select></el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" label="开始日期"><el-input v-model="crossref.date_from" type="date" /></el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" label="结束日期"><el-input v-model="crossref.date_to" type="date" /></el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" label="日期依据"><el-select v-model="crossref.date_basis"><el-option label="最近进入 Crossref 索引" value="indexed" /><el-option label="正式发表日期" value="published" /></el-select></el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" label="日期快捷范围">
            <el-button-group><el-button @click="applyDatePreset(7)">最近 7 天</el-button><el-button @click="applyDatePreset(30)">最近 30 天</el-button><el-button @click="applyDatePreset('year')">今年</el-button></el-button-group>
          </el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" label="常用 IEEE 期刊（快捷项，非完整目录）"><el-select v-model="journalPreset" @change="applyJournalPreset"><el-option label="自定义期刊/ISSN" value="custom" /><el-option v-for="journal in commonJournals" :key="journal.issn" :label="journal.name" :value="journal.issn" /></el-select></el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" :label="crossref.intent === 'journal_latest' ? '期刊名称' : '期刊/会议（可选）'"><el-input v-model="crossref.container_title" maxlength="200" /></el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" :label="crossref.intent === 'journal_latest' ? 'ISSN' : 'ISSN（可选）'"><el-input v-model="crossref.issn" maxlength="20" /></el-form-item>
          <el-form-item v-if="crossref.intent !== 'exact'" label="本次最大返回数"><el-input-number v-model="crossref.limit" :min="1" :max="50" /></el-form-item>
        </div>
        <el-alert type="info" :closable="false" title="请求确认" :description="confirmation" />
        <el-button :disabled="!canSubmitCrossref" @click="openSaveRule()">保存当前条件</el-button><el-button type="primary" :loading="searching" :disabled="!canSubmitCrossref" @click="submitCrossref">确认条件并检索</el-button>
      </el-form>
      <el-form v-else label-position="top">
        <el-form-item label="搜索词"><el-input v-model="arxiv.query" maxlength="200" /></el-form-item>
        <el-form-item label="结果上限"><el-input-number v-model="arxiv.limit" :min="1" :max="20" /></el-form-item>
        <el-button type="primary" :loading="searching" :disabled="!arxiv.query.trim()" @click="submitArxiv">搜索并加入候选箱</el-button>
      </el-form>
    </section>

    <section class="card">
      <div class="candidate-head"><div><h2>保存的搜索规则</h2><p class="text-secondary">只有明确运行才联网；成功后从上次检查点前 2 天重叠检查，失败不会推进检查点。没有自动调度。</p></div><el-button :disabled="!savedRules.length" :loading="runningAllRules" @click="showRunAllConfirm = true">运行全部</el-button></div>
      <p v-if="!savedRules.length" class="text-secondary">尚未保存规则。</p>
      <div v-for="rule in savedRules" :key="rule.id" class="job-row"><strong>{{ rule.name }}</strong><span>{{ ruleSummary(rule) }}</span><span v-if="rule.last_success_at">上次成功 {{ rule.last_success_at.slice(0, 10) }}</span><span v-if="rule.last_run_status === 'failed'" class="error-text">上次失败：{{ rule.last_error }}</span><el-button size="small" @click="loadRule(rule)">编辑</el-button><el-button size="small" :loading="runningRuleId === rule.id" @click="runRule(rule)">手动运行</el-button><el-button size="small" type="danger" plain @click="removeRule(rule)">删除</el-button></div>
    </section>

    <section class="card">
      <h2>最近任务</h2>
      <p v-if="!jobs.length" class="text-secondary">尚无发现任务。</p>
      <article v-for="job in jobs" :key="job.id" class="job-row">
        <el-tag :type="job.status === 'succeeded' ? 'success' : job.status === 'failed' ? 'danger' : 'warning'">{{ statusLabel(job.status) }}</el-tag>
        <strong>#{{ job.id }} {{ job.collector }}</strong>
        <span>{{ jobSummary(job) }}</span><span>候选 {{ job.candidate_count }}</span>
        <span v-if="job.result?.empty">空结果</span><span v-if="job.result?.truncated">结果已截断</span>
        <span v-if="job.result?.skipped_count">跳过 {{ job.result.skipped_count }} 条</span>
        <span v-if="job.error_message" class="error-text">{{ job.error_message }}</span>
        <el-button v-if="job.collector === 'crossref_ieee'" size="small" @click="loadJobQuery(job)">载入并修改</el-button>
        <div v-if="job.result?.empty" class="job-guidance">
          <span>{{ emptyGuidance(job) }}</span>
          <template v-if="job.query?.intent !== 'exact'">
            <el-button size="small" @click="expandJobToYear(job)">扩大到今年</el-button>
            <el-button v-if="job.query?.intent === 'topic' && (job.query?.container_title || job.query?.issn)" size="small" @click="removeJobJournal(job)">移除期刊限制</el-button>
            <el-button v-if="job.query?.intent === 'journal_latest' && job.query?.date_basis !== 'indexed'" size="small" @click="useIndexedDate(job)">改用索引日期</el-button>
          </template>
        </div>
        <div v-if="job.result?.truncated" class="job-guidance">已达到本次范围上限；可载入条件后收窄搜索，或在 50 条服务端上限内提高返回数。</div>
      </article>
    </section>

    <section class="card">
      <div class="candidate-head"><div><h2>待审核候选</h2><p class="text-secondary">选择候选后可本地解释排序；最多 5 篇查源码、10 篇生成明确范围的 AI 简报。</p><el-checkbox v-if="seenCandidateCount" v-model="showSeen">显示以前见过的结果（{{ seenCandidateCount }}）</el-checkbox></div><div><el-button :disabled="!selectedEnrichmentIds.length" :loading="rankingCandidates" @click="rankSelection">本地解释排序（{{ selectedEnrichmentIds.length }}）</el-button><el-button :disabled="selectedEnrichmentIds.length < 2 || selectedEnrichmentIds.length > 10" @click="showBriefConfirm = true">AI 候选简报（{{ selectedEnrichmentIds.length }}）</el-button><el-button :disabled="!selectedEnrichmentIds.length || selectedEnrichmentIds.length > 5" @click="showCodeConfirm = true">查源码（{{ selectedEnrichmentIds.length }}）</el-button><el-button type="primary" :disabled="!canEnrichSelection" @click="showEnrichmentConfirm = true">补全所选（{{ selectedEnrichmentIds.length }}）</el-button></div></div>
      <el-alert class="source-note" type="info" :closable="false" title="版本与日期说明" description="Crossref 表示 DOI 正式记录；arXiv 是独立预印本身份；OpenAlex 的开放链接是可访问版本线索，不等于正式出版页面。在线发表、纸本发表和索引更新时间分别展示，不互相替代。" />
      <p v-if="!visibleCandidates.length" class="text-secondary">{{ candidates.length ? '当前结果都曾经见过，可勾选上方选项恢复查看。' : '当前没有待审核候选。' }}</p>
      <article v-for="candidate in visibleCandidates" :key="candidate.id" class="candidate-row" :class="{ 'seen-candidate': isSeen(candidate) }">
        <div>
          <h3><el-checkbox v-if="isCodeCheckable(candidate)" v-model="selectedEnrichmentIds" :value="candidate.id" :disabled="selectedEnrichmentIds.length >= 20 && !selectedEnrichmentIds.includes(candidate.id)" /> {{ candidate.title }} <el-tag v-if="isSeen(candidate)" size="small" :type="seenTagType(candidate)">{{ seenLabel(candidate) }}</el-tag><el-tag v-else size="small" type="success">新发现</el-tag></h3>
          <p>{{ candidate.summary || '公开索引未提供摘要' }}</p>
          <div v-if="rankingById[candidate.id]" class="enrichment-box"><strong>本地确定性评分 {{ rankingById[candidate.id].score }}</strong><p>{{ rankingById[candidate.id].reasons.join('；') || '当前条件没有加分项' }}</p></div>
          <p class="text-secondary text-small">
            {{ candidate.source_facts?.doi || candidate.source_facts?.arxiv_id }}
            <template v-if="candidate.source_facts?.container_title"> · {{ candidate.source_facts.container_title }}</template>
            <template v-if="candidate.source_facts?.work_type"> · {{ candidate.source_facts.work_type }}</template>
            <template v-if="candidate.source_facts?.published"> · 发表 {{ candidate.source_facts.published }}</template>
            <template v-if="candidate.source_facts?.published_online"> · 在线 {{ candidate.source_facts.published_online }}</template>
            <template v-if="candidate.source_facts?.published_print"> · 纸本 {{ candidate.source_facts.published_print }}</template>
            <template v-if="candidate.source_facts?.indexed"> · 索引更新 {{ candidate.source_facts.indexed.slice(0, 10) }}</template>
            <template v-if="candidate.source_facts?.result_position"> · 第 {{ candidate.source_facts.result_position }} 条</template>
            <template v-if="candidate.source_facts?.authors?.length"> · 作者：{{ candidate.source_facts.authors.join('、') }}</template>
            <template v-if="candidate.source_facts?.categories?.length"> · 分类：{{ candidate.source_facts.categories.join('、') }}</template>
            <template v-if="candidate.source_facts?.existing_item_id"> · 已关联资料 #{{ candidate.source_facts.existing_item_id }}</template>
          </p>
          <div v-if="openAlexRecord(candidate)" class="enrichment-box">
            <template v-if="openAlexRecord(candidate).status === 'succeeded'">
              <strong>OpenAlex 补全</strong>
              <p>{{ openAlexRecord(candidate).facts.abstract || 'OpenAlex 未提供摘要' }}</p>
              <p class="text-secondary text-small"><template v-if="openAlexRecord(candidate).facts.institutions?.length">机构：{{ openAlexRecord(candidate).facts.institutions.join('、') }} · </template><template v-if="openAlexRecord(candidate).facts.topics?.length">主题：{{ openAlexRecord(candidate).facts.topics.join('、') }} · </template><template v-if="openAlexRecord(candidate).facts.cited_by_count !== null && openAlexRecord(candidate).facts.cited_by_count !== undefined">OpenAlex 引用计数：{{ openAlexRecord(candidate).facts.cited_by_count }} · </template>开放获取：{{ openAlexRecord(candidate).facts.is_open_access ? openAlexRecord(candidate).facts.oa_status || '是' : '否' }}<template v-if="openAlexRecord(candidate).facts.primary_source"> · 来源：{{ openAlexRecord(candidate).facts.primary_source }}</template></p>
              <a v-if="safePublicUrl(openAlexRecord(candidate).facts.best_open_url)" :href="openAlexRecord(candidate).facts.best_open_url" target="_blank" rel="noopener noreferrer">查看最佳公开页面</a>
            </template>
            <template v-else><strong>OpenAlex 补全失败</strong><p class="error-text">{{ openAlexRecord(candidate).error_message }}</p></template>
          </div>
          <div v-if="arxivVersionRecord(candidate)" class="enrichment-box version-box">
            <template v-if="arxivVersionRecord(candidate).status === 'succeeded'">
              <strong>严格匹配的 arXiv 预印本</strong>
              <p>{{ arxivVersionRecord(candidate).facts.abstract }}</p>
              <p class="text-secondary text-small">arXiv {{ arxivVersionRecord(candidate).facts.arxiv_id }} · 预印本日期 {{ arxivVersionRecord(candidate).facts.published?.slice(0, 10) || '未知' }} · 匹配证据：标题完全一致，作者 {{ arxivVersionRecord(candidate).facts.matched_authors.join('、') }} 一致</p>
              <a v-if="safePublicUrl(arxivVersionRecord(candidate).facts.source_url)" :href="arxivVersionRecord(candidate).facts.source_url" target="_blank" rel="noopener noreferrer">查看 arXiv 预印本</a>
            </template>
            <template v-else><strong>arXiv 版本核对</strong><p class="text-secondary">{{ arxivVersionRecord(candidate).error_message }}</p></template>
          </div>
          <div v-if="semanticRecord(candidate)" class="enrichment-box semantic-box">
            <template v-if="semanticRecord(candidate).status === 'succeeded'">
              <strong>Semantic Scholar DOI 补全</strong>
              <p>{{ semanticRecord(candidate).facts.abstract || 'Semantic Scholar 未提供摘要' }}</p>
              <p class="text-secondary text-small">按 DOI 精确关联 · 开放状态：{{ semanticRecord(candidate).facts.open_access_status || '未知' }}<template v-if="semanticRecord(candidate).facts.open_access_pdf_url"> · 提供公开 PDF 线索</template></p>
              <a v-if="safePublicUrl(semanticRecord(candidate).facts.source_url)" :href="semanticRecord(candidate).facts.source_url" target="_blank" rel="noopener noreferrer">查看 Semantic Scholar 记录</a>
            </template>
            <template v-else><strong>Semantic Scholar 补全</strong><p class="text-secondary">{{ semanticRecord(candidate).error_message }}</p></template>
          </div>
          <div v-if="codeRecord(candidate)" class="enrichment-box code-box">
            <template v-if="codeRecord(candidate).status === 'succeeded'">
              <strong>GitHub 源码证据</strong>
              <p v-if="!codeRecord(candidate).facts.repositories?.length" class="text-secondary">本次有界检查未发现证据；这不表示代码一定不存在。</p>
              <div v-for="repository in codeRecord(candidate).facts.repositories" :key="repository.repository_url" class="repository-row">
                <a v-if="repository.available !== false" :href="repository.repository_url" target="_blank" rel="noopener noreferrer">{{ repository.full_name }}</a><span v-else>{{ repository.full_name }}</span>
                <el-tag size="small" :type="repository.level === 'paper_declared' || repository.level === 'strong_identifier' ? 'success' : 'warning'">{{ evidenceLabel(repository.level) }}</el-tag>
                <span class="text-secondary text-small">{{ evidenceDescription(repository) }}<template v-if="repository.available === false"> · 仓库当前不可访问</template><template v-if="repository.license_spdx"> · {{ repository.license_spdx }}</template><template v-if="repository.archived"> · 已归档</template><template v-if="repository.stars !== null"> · ★ {{ repository.stars }}</template></span>
              </div>
            </template>
            <template v-else><strong>GitHub 源码检查失败</strong><p class="error-text">{{ codeRecord(candidate).error_message }}</p></template>
          </div>
        </div>
        <div class="candidate-actions"><el-button v-if="candidate.source_facts?.container_title" size="small" @click="searchSameJournal(candidate)">查同一期刊</el-button><el-button v-if="candidate.source_facts?.authors?.length" size="small" @click="searchAuthor(candidate.source_facts.authors[0])">查首位作者</el-button><el-button size="small" @click="searchRelated(candidate)">按标题继续搜</el-button><el-button v-if="isEnrichable(candidate)" size="small" @click="checkVersion(candidate)">核对版本</el-button><el-button @click="reject(candidate)">拒绝</el-button><el-button type="primary" @click="accept(candidate)">接受入库</el-button></div>
      </article>
    </section>
    <section class="card">
      <h2>候选 AI 简报审计</h2><p class="text-secondary">简报是独立推断，不修改来源事实、排序分数或审核状态。</p>
      <p v-if="!candidateBriefs.length" class="text-secondary">尚无候选简报。</p>
      <article v-for="brief in candidateBriefs" :key="brief.id" class="job-row"><el-tag :type="brief.status === 'succeeded' ? 'success' : 'danger'">{{ statusLabel(brief.status) }}</el-tag><strong>#{{ brief.id }} · 候选 {{ brief.candidate_ids.join('、') }}</strong><span v-if="brief.result">{{ brief.result.overview }}</span><span v-if="brief.error_message" class="error-text">{{ brief.error_message }}</span><div v-if="brief.result" class="job-guidance">{{ brief.result.priorities.map((item) => `#${item.candidate_id} ${item.reason}`).join('；') }} · 限制：{{ brief.result.caveats }}</div></article>
    </section>
    <el-dialog v-model="showEnrichmentConfirm" title="确认公开元数据补全范围" width="min(680px, 92vw)">
      <p>只会把以下 {{ selectedCandidates.length }} 条 DOI 一次发送给 OpenAlex；若公开摘要缺失，再以标题小批量查询 arXiv，并仅自动采用标题完全一致且至少一位作者一致的预印本。结果作为独立来源事实保存，不会覆盖 Crossref 标题、摘要或候选状态。</p>
      <ul><li v-for="candidate in selectedCandidates" :key="candidate.id">#{{ candidate.id }} · {{ candidate.source_facts.doi }} · {{ candidate.title }}</li></ul>
      <template #footer><el-button @click="showEnrichmentConfirm = false">取消</el-button><el-button type="primary" :loading="enriching" @click="confirmEnrichment">确认并补全</el-button></template>
    </el-dialog>
    <el-dialog v-model="showCodeConfirm" title="确认 GitHub 源码检查范围" width="min(680px, 92vw)">
      <p>只检查以下 {{ selectedCandidates.length }} 篇。论文元数据若明确给出 GitHub 地址会优先核验；否则每篇最多执行一次公开仓库搜索并查看前三个 README。不会克隆仓库、下载代码或保存 README；标题相同只会标为实现候选，不会自动称为官方源码。</p>
      <ul><li v-for="candidate in selectedCandidates" :key="candidate.id">#{{ candidate.id }} · {{ candidate.source_facts.doi || candidate.source_facts.arxiv_id }} · {{ candidate.title }}</li></ul>
      <template #footer><el-button @click="showCodeConfirm = false">取消</el-button><el-button type="primary" :loading="checkingCode" @click="confirmCodeCheck">确认并检查</el-button></template>
    </el-dialog>
    <el-dialog v-model="showSaveRule" :title="editingRuleId ? '更新保存的 Crossref 规则' : '保存当前 Crossref 条件'" width="min(640px, 92vw)"><p>{{ confirmation }}</p><el-input v-model="ruleName" maxlength="100" placeholder="规则名称" /><template #footer><el-button @click="showSaveRule = false">取消</el-button><el-button type="primary" :disabled="!ruleName.trim()" @click="confirmSaveRule">{{ editingRuleId ? '更新规则' : '保存规则' }}</el-button></template></el-dialog>
    <el-dialog v-model="showRunAllConfirm" title="确认运行全部保存规则" width="min(640px, 92vw)"><p>将按顺序运行 {{ savedRules.length }} 条规则，每条都会创建独立发现任务并访问 Crossref。某条失败不会阻止后续规则，也不会推进该规则的成功检查点。</p><template #footer><el-button @click="showRunAllConfirm = false">取消</el-button><el-button type="primary" :loading="runningAllRules" @click="confirmRunAllRules">确认并运行全部</el-button></template></el-dialog>
    <el-dialog v-model="showBriefConfirm" title="确认 AI 候选简报范围" width="min(720px, 92vw)"><p>只发送以下 {{ selectedCandidates.length }} 条候选的有界标题、DOI、作者、出版物、日期、最佳可追溯摘要（每篇最多 2000 字）和本地评分理由。不会发送工作区其他资料，不会自动接受候选。</p><ul><li v-for="candidate in selectedCandidates" :key="candidate.id">#{{ candidate.id }} · {{ candidate.source_facts?.doi || candidate.source_facts?.arxiv_id }} · {{ candidate.title }}</li></ul><template #footer><el-button @click="showBriefConfirm = false">取消</el-button><el-button type="primary" :loading="creatingBrief" @click="confirmCandidateBrief">确认并生成简报</el-button></template></el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import WorkspaceManager from '@/components/WorkspaceManager.vue'
import { acceptCandidate, checkCodeEvidence, createCandidateBrief, deleteDiscoveryRule, discoverArxiv, discoverCrossref, enrichOpenAlex, fetchCandidateBriefs, fetchCandidates, fetchCollectionJobs, fetchDiscoveryRules, rankDiscoveryCandidates, rejectCandidate, runAllDiscoveryRules, runDiscoveryRule, saveDiscoveryRule, updateDiscoveryRule } from '@/api'

const today = new Date().toISOString().slice(0, 10)
const source = ref('crossref'); const loading = ref(false); const searching = ref(false)
const jobs = ref([]); const candidates = ref([])
const savedRules = ref([]); const showSaveRule = ref(false); const ruleName = ref(''); const editingRuleId = ref(null); const runningRuleId = ref(null)
const showRunAllConfirm = ref(false); const runningAllRules = ref(false)
const selectedEnrichmentIds = ref([]); const showEnrichmentConfirm = ref(false); const enriching = ref(false)
const showCodeConfirm = ref(false); const checkingCode = ref(false)
const showSeen = ref(false)
const rankingCandidates = ref(false); const rankingById = reactive({})
const candidateBriefs = ref([]); const showBriefConfirm = ref(false); const creatingBrief = ref(false)
let dataGeneration = 0
const journalPreset = ref('custom')
const commonJournals = [
  { name: 'IEEE Robotics and Automation Letters', issn: '2377-3766' },
  { name: 'IEEE Access', issn: '2169-3536' },
  { name: 'IEEE Transactions on Robotics', issn: '1552-3098' },
  { name: 'IEEE Transactions on Pattern Analysis and Machine Intelligence', issn: '0162-8828' },
  { name: 'IEEE Transactions on Automation Science and Engineering', issn: '1545-5955' },
  { name: 'IEEE Sensors Journal', issn: '1530-437X' },
]
const crossref = reactive({ intent: 'topic', query: '', scope: 'journal', date_from: `${new Date().getUTCFullYear()}-01-01`, date_to: today, date_basis: 'indexed', container_title: '', issn: '', sort: 'relevance', limit: 20 })
const arxiv = reactive({ query: '', limit: 10 })
const canSubmitCrossref = computed(() => {
  if (crossref.intent === 'exact') return Boolean(crossref.query.trim())
  if (!crossref.date_from || !crossref.date_to || crossref.date_from > crossref.date_to) return false
  if (crossref.intent === 'journal_latest') return Boolean(crossref.container_title.trim() || crossref.issn.trim())
  return Boolean(crossref.query.trim())
})
const confirmation = computed(() => {
  const type = crossref.scope === 'journal' ? 'IEEE 期刊' : 'IEEE 期刊 + 会议'
  if (crossref.intent === 'exact') return `精确查找“${crossref.query || '（待填写完整标题或 DOI）'}”；只核对 ${type}，最多返回 1 条。`
  const intent = crossref.intent === 'journal_latest' ? `查看 ${crossref.container_title || crossref.issn || '（待填写期刊）'} 的最新论文` : crossref.intent === 'author' ? `搜索作者“${crossref.query || '（待填写作者）'}”` : `搜索主题“${crossref.query || '（待填写关键词）'}”`
  return `${intent}；${type}；按${crossref.date_basis === 'indexed' ? '进入 Crossref 索引日期' : '正式发表日期'}查 ${crossref.date_from} 至 ${crossref.date_to}；${crossref.container_title || '不限出版物'}；${crossref.issn || '不限 ISSN'}；最多 ${crossref.limit} 条。`
})
const selectedCandidates = computed(() => candidates.value.filter((candidate) => selectedEnrichmentIds.value.includes(candidate.id)))
const canEnrichSelection = computed(() => selectedCandidates.value.length > 0 && selectedCandidates.value.every(isEnrichable))
const seenCandidateCount = computed(() => candidates.value.filter(isSeen).length)
const visibleCandidates = computed(() => { const values = showSeen.value ? candidates.value : candidates.value.filter((candidate) => !isSeen(candidate)); return Object.keys(rankingById).length ? [...values].sort((a, b) => (rankingById[b.id]?.score || 0) - (rankingById[a.id]?.score || 0) || a.id - b.id) : values })
function statusLabel(value) { return { running: '运行中', succeeded: '成功', failed: '失败' }[value] || value }
function dateDaysAgo(days) { const value = new Date(`${today}T00:00:00Z`); value.setUTCDate(value.getUTCDate() - days); return value.toISOString().slice(0, 10) }
function applyDatePreset(value) { crossref.date_from = value === 'year' ? `${today.slice(0, 4)}-01-01` : dateDaysAgo(value - 1); crossref.date_to = today }
function applyJournalPreset(value) { const journal = commonJournals.find((entry) => entry.issn === value); if (journal) { crossref.container_title = journal.name; crossref.issn = journal.issn } }
function syncJournalPreset() { journalPreset.value = commonJournals.find((entry) => entry.name === crossref.container_title && entry.issn.replace('-', '') === crossref.issn.replace('-', ''))?.issn || 'custom' }
function jobSummary(job) { const query = job.query || {}; if (job.collector === 'openalex_enrichment') return `公开元数据补全 ${query.candidates?.length || 0} 条：OpenAlex ${job.result?.succeeded_count || 0}，arXiv ${job.result?.arxiv_succeeded_count || 0}，Semantic Scholar ${job.result?.semantic_succeeded_count || 0}`; if (job.collector === 'github_code_evidence') return `源码检查 ${query.candidates?.length || 0} 条：发现 ${job.result?.found_count || 0}，未发现 ${job.result?.not_found_count || 0}，失败 ${job.result?.failed_count || 0}`; if (job.collector !== 'crossref_ieee') return query.query || query.url || '公开来源任务'; if (query.intent === 'journal_latest') return `期刊最新：${query.container_title || query.issn}`; if (query.intent === 'author') return `作者：${query.query}`; if (query.intent === 'exact') return `精确查找：${query.query}`; return `主题：${query.query || '—'}` }
function ruleSummary(rule) { const query = rule.query || {}; return `${query.intent === 'author' ? '作者' : query.intent === 'journal_latest' ? '期刊最新' : query.intent === 'exact' ? '精确' : '主题'}：${query.query || query.container_title || query.issn} · ${query.date_from || '不限'} 至 ${query.date_to || '不限'} · 最多 ${query.limit}` }
function emptyGuidance(job) { if (job.query?.intent === 'exact') return '没有找到精确记录，请检查 DOI 或使用更完整的标题。'; if (job.query?.intent === 'journal_latest') return '该期刊在当前日期依据和范围内没有结果，可扩大日期或改用索引日期。'; return '当前主题和筛选条件没有结果，可扩大日期或移除期刊限制。' }
function loadJobQuery(job) { const query = job.query || {}; source.value = 'crossref'; Object.assign(crossref, { intent: query.intent || 'topic', query: query.query || '', scope: query.scope || 'journal', date_from: query.date_from || `${today.slice(0, 4)}-01-01`, date_to: query.date_to || today, date_basis: query.date_basis || 'indexed', container_title: query.container_title || '', issn: query.issn || '', sort: query.sort || 'relevance', limit: query.limit || 20 }); syncJournalPreset() }
function expandJobToYear(job) { loadJobQuery(job); applyDatePreset('year') }
function removeJobJournal(job) { loadJobQuery(job); crossref.container_title = ''; crossref.issn = ''; journalPreset.value = 'custom' }
function useIndexedDate(job) { loadJobQuery(job); crossref.date_basis = 'indexed' }
function isEnrichable(candidate) { return candidate.source_kind === 'crossref_ieee' && Boolean(candidate.source_facts?.doi) }
function isCodeCheckable(candidate) { return Boolean(candidate.source_facts?.doi || candidate.source_facts?.arxiv_id) }
function isSeen(candidate) { return Boolean(candidate.source_facts?.existing_candidate_id || candidate.source_facts?.existing_item_id) }
function seenLabel(candidate) { if (candidate.source_facts?.existing_item_id || candidate.source_facts?.existing_candidate_status === 'accepted') return '已入库'; if (candidate.source_facts?.existing_candidate_status === 'rejected') return '以前拒绝'; return '以前见过' }
function seenTagType(candidate) { return seenLabel(candidate) === '已入库' ? 'success' : seenLabel(candidate) === '以前拒绝' ? 'danger' : 'info' }
function openAlexRecord(candidate) { return candidate.source_records?.find((record) => record.source_kind === 'openalex') }
function arxivVersionRecord(candidate) { return candidate.source_records?.find((record) => record.source_kind === 'arxiv_version') }
function semanticRecord(candidate) { return candidate.source_records?.find((record) => record.source_kind === 'semantic_scholar') }
function codeRecord(candidate) { return candidate.source_records?.find((record) => record.source_kind === 'github_code') }
function evidenceLabel(level) { return { paper_declared: '论文声明', strong_identifier: '强身份关联', title_author_match: '标题与作者匹配', title_match: '标题匹配候选' }[level] || '证据不足' }
function evidenceDescription(repository) { const fields = { source_link: '来源元数据明确给出', doi: 'README 含同一 DOI', arxiv_id: 'README 含同一 arXiv ID', title: 'README 含完整标题', author: 'README 含论文作者' }; return (repository.matched_fields || []).map((field) => fields[field] || field).join('、') }
function safePublicUrl(value) { try { const parsed = new URL(value); return parsed.protocol === 'https:' ? parsed.href : '' } catch { return '' } }
async function loadData() { const generation = dataGeneration; loading.value = true; try { const [jobsResult, candidatesResult, rulesResult, briefsResult] = await Promise.allSettled([fetchCollectionJobs(), fetchCandidates({ status: 'pending' }), fetchDiscoveryRules(), fetchCandidateBriefs()]); if (generation !== dataGeneration) return; if (jobsResult.status === 'fulfilled') jobs.value = jobsResult.value.jobs || []; if (candidatesResult.status === 'fulfilled') candidates.value = candidatesResult.value.candidates || []; if (rulesResult.status === 'fulfilled') savedRules.value = rulesResult.value.rules || []; if (briefsResult.status === 'fulfilled') candidateBriefs.value = briefsResult.value.runs || []; const failures = [jobsResult, candidatesResult, rulesResult, briefsResult].filter((result) => result.status === 'rejected'); if (failures.length) ElMessage.error(failures[0].reason?.response?.data?.detail || '论文雷达部分数据加载失败'); const visible = new Set(candidates.value.map((candidate) => candidate.id)); selectedEnrichmentIds.value = selectedEnrichmentIds.value.filter((id) => visible.has(id)) } finally { if (generation === dataGeneration) loading.value = false } }
async function reloadWorkspace() { dataGeneration += 1; selectedEnrichmentIds.value = []; showEnrichmentConfirm.value = false; showCodeConfirm.value = false; showBriefConfirm.value = false; showSeen.value = false; jobs.value = []; candidates.value = []; savedRules.value = []; candidateBriefs.value = []; Object.keys(rankingById).forEach((key) => delete rankingById[key]); await loadData() }
function searchSameJournal(candidate) { source.value = 'crossref'; Object.assign(crossref, { intent: 'journal_latest', query: '', container_title: candidate.source_facts.container_title || '', issn: candidate.source_facts.issn?.[0] || '' }); syncJournalPreset(); window.scrollTo({ top: 0, behavior: 'smooth' }) }
function searchAuthor(author) { source.value = 'crossref'; Object.assign(crossref, { intent: 'author', query: author, container_title: '', issn: '' }); journalPreset.value = 'custom'; window.scrollTo({ top: 0, behavior: 'smooth' }) }
function searchRelated(candidate) { source.value = 'crossref'; Object.assign(crossref, { intent: 'topic', query: candidate.title, container_title: '', issn: '' }); journalPreset.value = 'custom'; window.scrollTo({ top: 0, behavior: 'smooth' }) }
function checkVersion(candidate) { selectedEnrichmentIds.value = [candidate.id]; showEnrichmentConfirm.value = true }
async function confirmEnrichment() { enriching.value = true; try { const result = await enrichOpenAlex(selectedEnrichmentIds.value); showEnrichmentConfirm.value = false; selectedEnrichmentIds.value = []; await loadData(); ElMessage.success(`补全完成：OpenAlex ${result.job.result.succeeded_count}，arXiv ${result.job.result.arxiv_succeeded_count || 0}，Semantic Scholar ${result.job.result.semantic_succeeded_count || 0}`) } catch (error) { await loadData(); ElMessage.error(error.response?.data?.detail || '公开元数据补全失败') } finally { enriching.value = false } }
async function confirmCodeCheck() { checkingCode.value = true; try { const result = await checkCodeEvidence(selectedEnrichmentIds.value); showCodeConfirm.value = false; selectedEnrichmentIds.value = []; await loadData(); ElMessage.success(`源码检查完成：发现 ${result.job.result.found_count || 0}，未发现 ${result.job.result.not_found_count || 0}`) } catch (error) { await loadData(); ElMessage.error(error.response?.data?.detail || 'GitHub 源码检查失败') } finally { checkingCode.value = false } }
function insightPayload() { return { candidate_ids: [...selectedEnrichmentIds.value], focus: crossref.query.trim(), preferred_journal: crossref.container_title.trim() } }
async function rankSelection() { rankingCandidates.value = true; try { const result = await rankDiscoveryCandidates(insightPayload()); Object.keys(rankingById).forEach((key) => delete rankingById[key]); for (const row of result.ranking || []) rankingById[row.candidate_id] = row; ElMessage.success('已按本地可解释规则排序') } catch (error) { ElMessage.error(error.response?.data?.detail || '本地排序失败') } finally { rankingCandidates.value = false } }
async function confirmCandidateBrief() { creatingBrief.value = true; try { const response = await createCandidateBrief(insightPayload()); showBriefConfirm.value = false; await loadData(); if (response.ok) ElMessage.success('候选简报已生成并记录审计'); else ElMessage.error(response.run?.error_message || '候选简报失败') } catch (error) { await loadData(); ElMessage.error(error.response?.data?.detail || '候选简报失败') } finally { creatingBrief.value = false } }
async function run(action, failure) { searching.value = true; try { const result = await action(); await loadData(); ElMessage.success(result.job?.result?.empty ? '检索完成，没有结果' : `发现 ${result.candidates?.length || 0} 条候选`) } catch (error) { await loadData(); ElMessage.error(error.response?.data?.detail || failure) } finally { searching.value = false } }
function crossrefPayload() { return { ...crossref, query: crossref.intent === 'journal_latest' ? null : crossref.query.trim() || null, date_from: crossref.intent === 'exact' ? null : crossref.date_from, date_to: crossref.intent === 'exact' ? null : crossref.date_to, container_title: crossref.intent === 'exact' ? null : crossref.container_title.trim() || null, issn: crossref.intent === 'exact' ? null : crossref.issn.trim() || null, limit: crossref.intent === 'exact' ? 1 : crossref.limit } }
function submitCrossref() { run(() => discoverCrossref(crossrefPayload()), 'Crossref 检索失败') }
function openSaveRule(rule = null) { editingRuleId.value = rule?.id || null; ruleName.value = rule?.name || ''; showSaveRule.value = true }
async function confirmSaveRule() { try { const payload = { name: ruleName.value.trim(), query: crossrefPayload() }; if (editingRuleId.value) await updateDiscoveryRule(editingRuleId.value, payload); else await saveDiscoveryRule(payload); showSaveRule.value = false; editingRuleId.value = null; ruleName.value = ''; await loadData(); ElMessage.success('搜索规则已保存') } catch (error) { ElMessage.error(error.response?.data?.detail || '保存规则失败') } }
function loadRule(rule) { const query = rule.query || {}; source.value = 'crossref'; Object.assign(crossref, query); syncJournalPreset(); openSaveRule(rule); window.scrollTo({ top: 0, behavior: 'smooth' }) }
async function runRule(rule) { runningRuleId.value = rule.id; try { const result = await runDiscoveryRule(rule.id); await loadData(); ElMessage.success(`规则运行完成，发现 ${result.candidates?.length || 0} 条候选`) } catch (error) { await loadData(); ElMessage.error(error.response?.data?.detail || '规则运行失败') } finally { runningRuleId.value = null } }
async function confirmRunAllRules() { runningAllRules.value = true; try { const result = await runAllDiscoveryRules(); showRunAllConfirm.value = false; await loadData(); const failed = result.results?.filter((item) => item.status === 'failed').length || 0; ElMessage.success(`全部规则运行完成：成功 ${(result.results?.length || 0) - failed}，失败 ${failed}`) } catch (error) { await loadData(); ElMessage.error(error.response?.data?.detail || '运行全部规则失败') } finally { runningAllRules.value = false } }
async function removeRule(rule) { try { await deleteDiscoveryRule(rule.id); await loadData() } catch (error) { ElMessage.error(error.response?.data?.detail || '删除规则失败') } }
function submitArxiv() { run(() => discoverArxiv(arxiv.query.trim(), arxiv.limit), 'arXiv 检索失败') }
async function accept(candidate) { try { const result = await acceptCandidate(candidate.id); await loadData(); ElMessage.success(result.duplicate ? '已关联到已有资料' : '候选已正式入库') } catch (error) { ElMessage.error(error.response?.data?.detail || '候选入库失败') } }
async function reject(candidate) { try { await rejectCandidate(candidate.id); await loadData() } catch (error) { ElMessage.error(error.response?.data?.detail || '候选拒绝失败') } }
onMounted(loadData)
</script>

<style scoped>
.radar-page { display: grid; gap: 16px; }.page-head,.candidate-head,.candidate-row,.job-row { display:flex; justify-content:space-between; gap:16px; align-items:flex-start }.candidate-head h2 { margin-bottom:4px }.candidate-head p { margin:0 }.source-note { margin:12px 0 }.search-card { max-width: 980px }.form-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:0 16px }.job-row { justify-content:flex-start; flex-wrap:wrap; padding:10px 0; border-bottom:1px solid var(--el-border-color-lighter) }.job-guidance { flex-basis:100%; display:flex; align-items:center; gap:8px; padding-left:44px; color:var(--el-text-color-secondary) }.candidate-row { padding:16px 0; border-bottom:1px solid var(--el-border-color-lighter) }.seen-candidate { opacity:.78 }.candidate-row h3 { margin:0 0 8px }.candidate-actions { display:flex; flex-direction:column; gap:8px; min-width:110px }.candidate-actions .el-button { margin-left:0 }.enrichment-box { margin-top:10px; padding:12px; border-left:3px solid var(--el-color-primary); background:var(--el-fill-color-light) }.version-box { border-left-color:var(--el-color-success) }.semantic-box { border-left-color:var(--el-color-warning) }.code-box { border-left-color:#24292f }.repository-row { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:8px }.enrichment-box p { margin:6px 0 }.error-text { color:var(--el-color-danger) }
</style>
