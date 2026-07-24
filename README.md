# ResearchMate

一个轻量级的论文学术资源爬取、分析与展示平台。支持从 arXiv 等学术平台自动爬取论文元数据，进行关键词提取、聚类分析，并通过 Web 前端美观展示。

## 特性

- **论文爬取** — 从 arXiv 等平台自动获取论文信息，支持定时任务
- **智能分析** — 关键词提取、论文聚类、相似度推荐
- **美观展示** — Vue 3 + Element Plus 构建的现代化 Web 界面
- **可扩展** — 爬虫和分析模块均采用插件式设计，方便添加新数据源

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端语言 | Python 3.10+ |
| Web 框架 | FastAPI |
| 数据库 | SQLite |
| 爬虫 | httpx + BeautifulSoup4 + arxiv |
| NLP 分析 | jieba + scikit-learn |
| 前端框架 | Vue 3 + Vite |
| UI 组件 | Element Plus |
| 数据可视化 | ECharts |

## 项目结构

```
ResearchMate/
├── backend/          # Python 后端（爬虫、分析、API）
├── frontend/         # Vue 3 前端
├── data/             # 爬取数据存放
├── scripts/          # 工具脚本
├── config/           # 配置文件
└── temp/             # 设计文档
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 pnpm

### 后端安装

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

### 前端安装

```bash
cd frontend
npm install
npm run dev
```

## 开发计划

- [ ] 后端骨架 — arXiv 爬虫 + SQLite 存储
- [ ] 分析模块 — 关键词提取、论文聚类
- [ ] REST API — FastAPI 接口
- [ ] 前端页面 — 论文列表、搜索、分析可视化
- [ ] 定时爬取 — APScheduler 自动更新

## 参考

本项目设计参考了以下优秀开源项目：
- [arxiv-sanity-lite](https://github.com/karpathy/arxiv-sanity-lite) — Andrej Karpathy 的论文推荐系统
- [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) — 文档管理系统

## License

Distributed under the Unlicense License. See `LICENSE.txt` for more information.
