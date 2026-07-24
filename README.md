<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/promise-157/ResearchMate">
    <img src="images/userimage.jpg" alt="Logo" width="80" height="80">
  </a>

  <h3 align="center">ResearchMate</h3>

  <p align="center">
    AI 辅助论文筛选工具 — 爬摘要 · AI 分析 · 快速筛选
    <br />
    <a href="https://github.com/promise-157/ResearchMate"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/promise-157/ResearchMate">View Demo</a>
    &middot;
    <a href="https://github.com/promise-157/ResearchMate/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/promise-157/ResearchMate/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>


<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

ResearchMate 是一个 AI 辅助论文筛选工具。导入你感兴趣的期刊网址，自动爬取论文摘要，通过 AI 分析每篇论文的创新点和技术栈，帮你快速找到值得精读的论文。

核心功能：
- **自定义期刊源**：添加你关注的期刊/会议网址，灵活管理
- **摘要爬取**：只爬摘要不下载 PDF，省空间，付费墙也挡不住
- **AI 智能分析**：自动识别论文是否有开源代码、提炼创新点、提取技术关键词
- **批量点评**：每次爬取后 AI 总结这批论文的趋势和亮点
- **购物车**：感兴趣的先收藏，最后导出清单集中处理

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

| 层级 | 技术 |
|------|------|
| 后端语言 | Python 3.11+ |
| Web 框架 | FastAPI |
| 数据库 | SQLite |
| 爬虫 | httpx + BeautifulSoup4 |
| AI 分析 | OpenAI / Claude / Ollama (可配置) |
| 前端框架 | Vue 3 (Composition API) |
| 构建工具 | Vite |
| UI 组件 | Element Plus |
| 数据可视化 | ECharts |

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

- **Python 3.11+** (推荐使用 conda 管理环境)
- **Node.js 18+** (推荐使用 nvm 管理版本)
- **npm**

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/promise-157/ResearchMate.git
   cd ResearchMate
   ```

2. 创建 Python 虚拟环境并安装后端依赖
   ```sh
   conda create -n researchmate python=3.11 -y
   conda activate researchmate
   cd src/backend
   pip install -r requirements.txt
   ```

3. 安装前端依赖
   ```sh
   cd src/frontend
   npm install
   ```

4. 配置 AI API Key
   - 启动程序后在「全局设置 → AI 配置」页面填写 API Key
   - 支持 OpenAI、Claude、Ollama 本地模型

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

启动后端（自动打开浏览器）：
```sh
cd src/backend
python run.py
```

仅启动前端开发服务器（调试 UI 用）：
```sh
cd src/frontend
npm run dev
# 浏览器打开 http://localhost:5173
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- [x] 项目目录结构设计
- [x] 前端骨架搭建 (Vue3 + Vite + Router + Pinia)
- [x] CSS 设计系统 (变量 + 主题切换)
- [x] 首页导航
- [ ] 论文中心页面 (期刊源管理 + 爬取 + AI 分析结果)
- [ ] 全局设置页面 (主题 / AI 配置 / 爬取参数)
- [ ] 后端 API (FastAPI + SQLite)
- [ ] 爬虫模块 (通用网页 + arXiv 专用)
- [ ] AI 分析模块 (单篇分析 + 批量点评)
- [ ] 购物车导出功能
- [ ] 数据分析可视化

See the [open issues](https://github.com/promise-157/ResearchMate/issues) for a full list of proposed features.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the Unlicense License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

promise-157 - [@promise-157](https://github.com/promise-157)

Project Link: [https://github.com/promise-157/ResearchMate](https://github.com/promise-157/ResearchMate)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [arxiv-sanity-lite](https://github.com/karpathy/arxiv-sanity-lite) - Andrej Karpathy 的论文推荐系统
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
* [Element Plus](https://element-plus.org/)
* [Img Shields](https://shields.io)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/promise-157/ResearchMate.svg?style=for-the-badge
[contributors-url]: https://github.com/promise-157/ResearchMate/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/promise-157/ResearchMate.svg?style=for-the-badge
[forks-url]: https://github.com/promise-157/ResearchMate/network/members
[stars-shield]: https://img.shields.io/github/stars/promise-157/ResearchMate.svg?style=for-the-badge
[stars-url]: https://github.com/promise-157/ResearchMate/stargazers
[issues-shield]: https://img.shields.io/github/issues/promise-157/ResearchMate.svg?style=for-the-badge
[issues-url]: https://github.com/promise-157/ResearchMate/issues
[license-shield]: https://img.shields.io/github/license/promise-157/ResearchMate.svg?style=for-the-badge
[license-url]: https://github.com/promise-157/ResearchMate/blob/main/LICENSE.txt
