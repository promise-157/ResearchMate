# ResearchMate 工程设计文档

> 最后更新: 2026-07-24
> 本文件记录项目整体设计思路，开发过程中随时参考，避免遗忘。

---

## 一、项目目标

一个论文爬取、分析、展示的自动化工具，支持扩展为多类型学术资源的综合管理平台。

核心功能：
1. 从 arXiv 等学术平台爬取论文元数据和 PDF
2. 本地存储并进行 NLP 分析（关键词提取、聚类、相似度推荐）
3. 通过 Web 前端美观展示和交互

---

## 二、技术栈选择

### 后端 (Python 3.10+)

| 组件 | 选型 | 说明 |
|------|------|------|
| HTTP 客户端 | httpx | 轻量异步 |
| 网页解析 | BeautifulSoup4 + lxml | 经典组合 |
| Web 框架 | FastAPI | 极轻量，自动 API 文档 |
| 数据库 | SQLite (内置) | 零配置，单文件 |
| 论文 API | arxiv (Python 包) | arXiv 官方 API 封装 |
| 分词 | jieba | 中文分词 |
| 文本分析 | scikit-learn | TF-IDF、聚类 |
| 任务调度 | APScheduler | 定时爬取 |

### 前端 (Web)

| 组件 | 选型 | 说明 |
|------|------|------|
| 构建工具 | Vite | 秒级热更新 |
| 框架 | Vue 3 | 渐进式，按需使用 |
| UI 库 | Element Plus | 组件丰富，tree-shakeable |
| 可视化 | ECharts | 图表美观 |
| HTTP 客户端 | axios | 请求后端 API |

---

## 三、项目目录结构

```
ResearchMate/
├── src/                              # 所有源码
│   ├── backend/                      # Python 后端
│   │   ├── crawlers/                 # 爬虫模块（可插拔）
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # 抽象基类 BaseCrawler
│   │   │   ├── arxiv_crawler.py      # arXiv 爬虫实现
│   │   │   └── registry.py           # 爬虫注册表
│   │   ├── processors/               # 数据处理/分析
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # 处理器基类 BaseProcessor
│   │   │   ├── paper_analyzer.py     # 论文分析（关键词、聚类）
│   │   │   └── registry.py
│   │   ├── storage/                  # 数据持久层
│   │   │   ├── __init__.py
│   │   │   ├── database.py           # SQLite 连接管理
│   │   │   └── models.py             # 数据模型定义
│   │   ├── api/                      # REST API
│   │   │   ├── __init__.py
│   │   │   ├── server.py             # FastAPI 应用入口
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── papers.py         # /api/papers 论文 CRUD
│   │   │       └── stats.py          # /api/stats  统计分析
│   │   ├── config.py                 # 全局配置
│   │   ├── requirements.txt          # Python 依赖
│   │   └── run.py                    # 一键启动
│   ├── frontend/                     # Vue 3 前端
│   │   ├── src/
│   │   │   ├── views/                # 页面组件
│   │   │   │   ├── Home.vue          # 首页概览/仪表盘
│   │   │   │   ├── Papers.vue        # 论文列表 + 搜索筛选
│   │   │   │   └── Analysis.vue      # 分析可视化
│   │   │   ├── components/           # 可复用组件
│   │   │   │   ├── PaperCard.vue     # 论文字卡
│   │   │   │   ├── SearchBar.vue     # 搜索栏
│   │   │   │   └── NavLayout.vue     # 导航布局
│   │   │   ├── api/                  # 后端 API 调用封装
│   │   │   │   └── index.js
│   │   │   ├── router/               # 前端路由
│   │   │   │   └── index.js
│   │   │   ├── App.vue
│   │   │   └── main.js
│   │   ├── index.html
│   │   ├── vite.config.js
│   │   └── package.json
│   ├── data/                         # 爬取数据存放 (.gitignore)
│   ├── scripts/                      # 一次性工具脚本
│   ├── config/                       # 用户配置
│   │   └── settings.yaml
│   └── temp/                         # 设计文档/临时笔记
├── CLAUDE.md                         # AI 助手指令
├── README.md
├── CHANGELOG.md
└── LICENSE.txt
```

---

## 四、扩展性设计

### 爬虫扩展

所有爬虫继承 `BaseCrawler`，在 `registry.py` 注册即可：

```python
class BaseCrawler(ABC):
    @abstractmethod
    def name(self) -> str: ...
    
    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[dict]: ...
    
    @abstractmethod
    async def fetch_detail(self, paper_id: str) -> dict: ...
```

以后要加 IEEE / 知网 / Google Scholar / Semantic Scholar 爬虫：
1. 继承 BaseCrawler，实现一个新类
2. 在 registry 里注册
3. 前端完全不用动

### 处理器扩展

所有分析器继承 `BaseProcessor`：

```python
class BaseProcessor(ABC):
    @abstractmethod
    def process(self, papers: list[dict]) -> list[dict]: ...
```

未来可扩展：翻译、自动摘要、引用图谱分析等。

---

## 五、参考的开源项目

| 项目 | 可借鉴内容 |
|------|-----------|
| [arxiv-sanity-lite](https://github.com/karpathy/arxiv-sanity-lite) | 论文爬取、去重、TF-IDF 相似推荐的极简实现 |
| [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) | 文档管理的目录结构设计 |
| [scholar.py](https://github.com/ckreibich/scholar.py) | Google Scholar 轻量爬虫 |

---

## 六、推荐开发顺序

1. **后端骨架** — arxiv_crawler.py 能跑通，把论文存进 SQLite
2. **分析模块** — 关键词提取、论文聚类，结果写回数据库
3. **REST API** — FastAPI 起接口，Swagger 文档直接浏览器调试
4. **前端页面** — Vite 初始化 Vue 项目，调 API 展示数据
5. **美化打磨** — Element Plus 组件 + ECharts 图表

---

## 七、API 接口规划 (初步)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/papers` | 论文列表（支持分页、搜索、排序） |
| GET | `/api/papers/:id` | 论文详情 |
| POST | `/api/crawl/arxiv` | 触发 arXiv 爬取任务 |
| GET | `/api/stats/overview` | 统计概览（总数、趋势、关键词云） |
| GET | `/api/stats/keywords` | 关键词排名 |
| GET | `/api/papers/:id/similar` | 相似论文推荐 |

---

## 八、数据库表设计 (初步)

```sql
-- 论文表
CREATE TABLE papers (
    id TEXT PRIMARY KEY,         -- arxiv_id 或自定义 ID
    title TEXT NOT NULL,
    authors TEXT,                -- JSON 数组
    abstract TEXT,
    published_date DATE,
    url TEXT,
    pdf_path TEXT,               -- 本地 PDF 路径
    categories TEXT,             -- JSON 数组，如 ["cs.AI", "cs.CL"]
    keywords TEXT,               -- JSON 数组，分析后提取的关键词
    embedding BLOB,              -- 文本向量 (可选，用于相似度)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 分析结果表
CREATE TABLE analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT REFERENCES papers(id),
    analysis_type TEXT,          -- 'keywords', 'summary', 'clustering'
    result TEXT,                 -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 九、待决策事项

- [ ] 是否需要用户系统/登录？（初期不需要，先做单用户本地工具）
- [ ] PDF 全文下载还是只爬元数据？（先只爬元数据，后续加全文分析）
- [ ] Docker 部署是否是必需？（初期不需要，脚本直接跑）
- [ ] 前端用 Vue 3 Options API 还是 Composition API？（推荐 Composition API，更现代）
