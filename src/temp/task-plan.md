# ResearchMate 实现任务清单

> 每完成一步打 ✅，附 commit message。后续 Claude 实例读这个文件就知道做到哪了。

---

## 阶段零：环境确认

- [ ] **T0.1** 确认 conda 环境 `researchmate` 可用
- [ ] **T0.2** 确认 Node.js 可用（nvm）
- [ ] **T0.3** 确认网络可通 GitHub（下载依赖）

---

## 阶段一：前端骨架初始化

**产出**：`npm run dev` 能看到 Vue 页面在浏览器打开，3 个路由能跳转。

- [ ] **T1.1** Vite + Vue3 项目初始化
  - 创建 `src/frontend` 下的 Vite 项目
  - 文件：`package.json`, `vite.config.js`, `index.html`
- [ ] **T1.2** 安装依赖
  - `vue@3`, `vue-router@4`, `pinia`, `element-plus`, `axios`, `@element-plus/icons-vue`
- [ ] **T1.3** 配置 Vite
  - 代理 `/api` 到 `localhost:8000`
  - 配置 Element Plus 按需引入（unplugin-vue-components）
- [ ] **T1.4** 创建入口文件
  - `src/main.js` — 挂载 App，注册 Router + Pinia + ElementPlus
  - `src/App.vue` — `<router-view>` + 顶栏 + 购物车面板
- [ ] **T1.5** 创建路由骨架（3 个空页面）
  - `src/router/index.js`
  - `src/views/Home.vue` — 占位文字
  - `src/views/Papers.vue` — 占位文字
  - `src/views/Settings.vue` — 占位文字

**完成后效果**：浏览器打开 → 看到顶栏 + 空首页 → 点击跳转到Papers/Settings → 都是空页占位

---

## 阶段二：CSS 基础设施

**产出**：全局 CSS 变量、主题系统就位，后续所有组件直接用变量不写硬编码颜色。

- [ ] **T2.1** 创建 CSS 变量文件 `src/styles/variables.css`
  - 颜色（--color-primary, --color-bg, --color-text, --color-border...）
  - 间距（--spacing-xs/sm/md/lg/xl）
  - 圆角（--radius-sm/md/lg）
  - 阴影（--shadow-sm/md/lg）
  - 字体大小
- [ ] **T2.2** 创建全局样式 `src/styles/global.css`
  - body 背景/字体/行高
  - 滚动条美化
  - 通用的 card-hover 动画
- [ ] **T2.3** 在 `main.js` 中引入全局样式

---

## 阶段三：共享基础设施

**产出**：API 层、Store、共享组件就位，后续页面只写业务逻辑。

- [ ] **T3.1** API 层 `src/api/index.js`
  - 封装 axios 实例（baseURL, 超时, 错误拦截）
  - 导出各模块 API 函数（先写空函数签名，标注 TODO）
  - 函数签名清单：
    ```
    fetchJournals() → GET /api/journals
    addJournal(url, label) → POST /api/journals
    deleteJournal(id) → DELETE /api/journals/:id
    startCrawl(sourceIds, mode) → POST /api/crawl
    getCrawlStatus() → GET /api/crawl/status
    fetchPapers(params) → GET /api/papers
    fetchPaperDetail(id) → GET /api/papers/:id
    updatePaper(id, data) → PATCH /api/papers/:id
    fetchCart() → GET /api/cart
    exportCart(format) → GET /api/cart/export
    fetchSettings() → GET /api/settings
    updateSettings(data) → PUT /api/settings
    fetchStats() → GET /api/stats
    ```
- [ ] **T3.2** Pinia Store
  - `src/stores/cart.js` — `items[]`, `addItem()`, `removeItem()`, `isInCart()`, `count`
  - `src/stores/settings.js` — `theme`, `aiConfig`, `crawlConfig`, `loadSettings()`, `saveSettings()`
  - store 里的数据先 mock，等后端有了再换成真实 API
- [ ] **T3.3** 共享组件 — `NavBar.vue`
  - 顶部导航栏：Logo + 页面链接 + 购物车图标(角标数字) + 设置图标
  - Props: 无（直接从 cartStore 读 count）
  - 点击购物车图标 → emit `toggle-cart`
- [ ] **T3.4** 共享组件 — `CartDrawer.vue`
  - 右侧滑出面板（ElDrawer）
  - Props: `visible` (Boolean)
  - 从 cartStore 读数据
  - 每条：标题、出处、移除按钮
  - 底部：复制标题列表、导出 CSV 按钮（先只有 UI，功能 TODO 到后端阶段）
  - Emit: `update:visible`

---

## 阶段四：首页

**产出**：精美的导航首页，卡片网格 + 底部状态。

- [ ] **T4.1** `src/views/Home.vue`
  - 居中卡片网格（CSS Grid，2-3 列自适应）
  - 3 张导航卡片：论文中心、全局设置、关于
  - 每张卡片：图标 + 标题 + 描述 + hover 上浮动画
  - 底部状态栏：论文总数 + 购物车数量 + 上次爬取时间
- [ ] **T4.2** `src/components/NavCard.vue`
  - Props: `icon`, `title`, `description`, `to` (路由路径)
  - hover 上浮 4px + 阴影加深，transition 0.3s

---

## 阶段五：论文中心 — 静态 UI（先不接后端）

**产出**：论文中心完整布局用 mock 数据渲染出来，能看到效果。

- [ ] **T5.1** 爬取控制区 — `CrawlControl.vue`
  - Props: `sources` (Array, mock 数据)
  - 期刊源列表渲染（复选框 + 名称 + 上次爬取时间 + 上次新增）
  - 模式选择（仅新论文 / 全部重新爬）
  - 「添加期刊源」按钮 + 弹窗（`AddSourceDialog.vue`，暂不接 API，只 console.log）
  - 「开始爬取已选的 N 个源」按钮（暂不接 API，只 console.log）
  - Emit: `crawl-start(sourceIds, mode)`
- [ ] **T5.2** 添加期刊源弹窗 — `AddSourceDialog.vue`
  - 两个输入框：URL（必填）、备注名（可选）
  - Props: `visible`
  - Emit: `update:visible`, `add(url, label)`
- [ ] **T5.3** AI 点评卡片 — `AIReviewCard.vue`
  - Props: `review` (Object, mock 数据)
  - 可折叠，默认展开
  - 显示：统计、热门方向、推荐关注列表、技术趋势
  - 若无数据（还没爬取）则显示占位提示"暂无数据，请先爬取论文"
- [ ] **T5.4** 论文卡片 — `PaperCard.vue`
  - Props: `paper` (Object)
  - 按 v3 设计方案渲染完整卡片
  - ⭐ 收藏按钮逻辑：
    - 不在购物车 → 空心星 + 点击 addToCart
    - 在购物车 → 实心星(蓝色) + 点击 removeFromCart
  - AI 分析块默认折叠前 2 行，点击展开
  - 技术标签用 `el-tag` 渲染，最多 3 个
  - Emit: `view-detail(paper)`, `toggle-cart(paper)`
- [ ] **T5.5** 论文详情弹窗 — `PaperDetailModal.vue`
  - Props: `paper`, `visible`
  - 显示：完整标题、全部作者、期刊年份、原始摘要全文、AI 完整分析
  - 底部操作：访问原文链接、复制引用信息
  - Emit: `update:visible`
- [ ] **T5.6** 筛选栏 — `PaperFilterBar.vue`
  - 搜索输入框
  - 三个快速筛选：有代码开关 / 已保存开关 / 排序下拉
  - Emit: `filter-change(filters)`
- [ ] **T5.7** 爬取进度 — `CrawlProgress.vue`
  - Props: `status` (idle/crawling/analyzing/done/error)
  - 根据状态显示不同 UI：进度条 / 完成提示 / 错误信息
- [ ] **T5.8** 组装 `src/views/Papers.vue`
  - 引入以上 7 个子组件
  - 用 mock 数据填充（至少 5 篇 mock 论文，覆盖有代码/无代码/已收藏等状态）
  - 所有交互 console.log，确保组件通信正常

---

## 阶段六：全局设置

**产出**：设置页能改主题、配置 AI、配置爬取参数（先不接后端）。

- [ ] **T6.1** `src/views/Settings.vue`
  - 左侧导航 + 右侧内容区布局（ElMenu + RouterView 或手动 Tabs）
  - 分组：外观 / AI 配置 / 爬取设置 / 数据管理
- [ ] **T6.2** 外观设置 — `ThemeSwitch.vue`
  - 3 个单选：浅色 / 深色 / 跟随系统
  - 选择后立即生效（通过 settingsStore 切换 CSS 变量或 `document.documentElement` class）
- [ ] **T6.3** AI 配置 — `AIConfig.vue`
  - API 类型下拉（OpenAI / Claude / Ollama / 自定义）
  - API Key 密码框（不展示已有值）
  - API Base URL 输入框
  - 模型名称输入框
  - 「测试连接」按钮（先只有 UI，功能 TODO）
  - Prompt 模板编辑区（textarea，有默认值，可恢复默认）
- [ ] **T6.4** 爬取配置 — `CrawlConfig.vue`
  - 每次最大论文数（数字输入）
  - 请求间隔秒数（数字输入）
  - 超时时间（数字输入）
- [ ] **T6.5** 数据管理
  - 显示数据库大小（mock 先）
  - 「清空论文数据」按钮（红色，有二次确认弹窗）
  - 「重置所有设置」按钮

---

## 阶段七：关于页

**产出**：简洁的关于页。

- [ ] **T7.1** `src/views/About.vue`
  - 项目名称 + 版本号
  - 简短介绍
  - GitHub 链接
  - 技术栈列表

---

## 阶段八：后端骨架

**产出**：`python run.py` 能启动 FastAPI，前端能通过 API 调通。

- [ ] **T8.1** 创建 `src/backend/requirements.txt`
  - fastapi, uvicorn, httpx, beautifulsoup4, lxml, apscheduler, pyyaml, pydantic
- [ ] **T8.2** 创建 `src/backend/config.py`
  - 读取 YAML 配置文件
  - 默认值：数据库路径、API host/port、爬取参数
- [ ] **T8.3** 创建 `src/backend/storage/database.py`
  - SQLite 连接管理
  - `init_db()` — 创建 journal_sources, papers, crawl_sessions 表
- [ ] **T8.4** 创建 `src/backend/storage/models.py`
  - Pydantic 模型：JournalSource, Paper, CrawlSession, Settings
- [ ] **T8.5** 创建 `src/backend/api/server.py`
  - FastAPI 应用初始化，CORS 中间件
  - 挂载路由
- [ ] **T8.6** 创建路由（先只做 CRUD 占位，返回 mock 数据）
  - `src/backend/api/routes/journals.py`
  - `src/backend/api/routes/papers.py`
  - `src/backend/api/routes/crawl.py`
  - `src/backend/api/routes/cart.py`
  - `src/backend/api/routes/settings.py`
  - `src/backend/api/routes/stats.py`
- [ ] **T8.7** 创建 `src/backend/run.py`
  - 启动 uvicorn
  - 自动打开浏览器
  - 生产模式下 serve 前端静态文件（`frontend/dist/`）
- [ ] **T8.8** 前后端联通测试
  - 启动后端
  - 前端 API 层对接真实后端
  - 确认一个 GET 请求能走通

---

## 阶段九：爬虫模块

- [ ] **T9.1** 创建爬虫基类 `src/backend/crawlers/base.py`
- [ ] **T9.2** 创建爬虫注册表 `src/backend/crawlers/registry.py`
- [ ] **T9.3** 实现通用网页爬虫（根据 URL 自适应提取摘要）
  - 尝试从 HTML meta 标签、JSON-LD、正文提取
- [ ] **T9.4** 特殊站点适配（如 arXiv API 专用爬虫）
- [ ] **T9.5** 去重逻辑：按 arxiv_id 或 paper_url 判重
- [ ] **T9.6** 定时任务（APScheduler）

---

## 阶段十：AI 分析模块

- [ ] **T10.1** 创建分析器基类 `src/backend/processors/base.py`
- [ ] **T10.2** 实现 LLM 调用 `src/backend/processors/llm_analyzer.py`
  - 支持 OpenAI / Claude / Ollama 三种后端
  - 单篇分析（prompt 模板：代码/创新/技术）
  - 批量点评（汇总所有摘要，写趋势和推荐）
- [ ] **T10.3** 分析结果结构化为 Pydantic 模型

---

## 阶段十一：联调 + 打磨

- [ ] **T11.1** 设置页保存/读取真实配置
- [ ] **T11.2** 购物车数据持久化
- [ ] **T11.3** 爬取进度实时反馈（WebSocket 或轮询）
- [ ] **T11.4** 前后端完整流程测试
- [ ] **T11.5** UI 细节打磨（动画、响应式、loading 状态、空状态、错误状态）

---

## 每个阶段完成后的 commit 规范

```
feat(frontend): 阶段一 - 前端骨架初始化

- Vite + Vue3 + Router + ElementPlus 项目创建
- 3 个空路由页面可跳转
- 代理配置指向 localhost:8000
```

---

## 进度追踪

| 阶段 | 状态 | 完成日期 |
|------|------|---------|
| 零: 环境确认 | ⬜ | |
| 一: 前端骨架 | ⬜ | |
| 二: CSS 基础 | ⬜ | |
| 三: 共享基础 | ⬜ | |
| 四: 首页 | ⬜ | |
| 五: 论文中心 UI | ⬜ | |
| 六: 设置 | ⬜ | |
| 七: 关于 | ⬜ | |
| 八: 后端骨架 | ⬜ | |
| 九: 爬虫模块 | ⬜ | |
| 十: AI 分析 | ⬜ | |
| 十一: 联调打磨 | ⬜ | |
