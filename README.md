<a id="readme-top"></a>

<div align="center">
  <a href="https://github.com/promise-157/ResearchMate">
    <img src="assets/branding/promise-157-logo.jpg" alt="promise-157 rabbit logo" width="112" height="112">
  </a>

  <h1>ResearchMate</h1>

  <p>
    本地优先、证据可追溯的个人资料工作空间
    <br />
    从导入与发现，到整理、显式 AI 分析，再到行动专题。
  </p>

  <p>
    <a href="docs/INSTALL_WINDOWS_WSL_FROM_SCRATCH.md"><strong>从零安装 »</strong></a>
    ·
    <a href="docs/MANUAL.md">使用手册</a>
    ·
    <a href="docs/ROADMAP.md">路线图</a>
    ·
    <a href="https://github.com/promise-157/ResearchMate/issues">反馈问题</a>
  </p>

  <p>
    <img alt="Development branch" src="https://img.shields.io/badge/status-development-f59e0b?style=flat-square">
    <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white">
    <img alt="Vue 3" src="https://img.shields.io/badge/Vue-3-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white">
    <img alt="License: Unlicense" src="https://img.shields.io/badge/license-Unlicense-blue?style=flat-square">
  </p>
</div>

> [!IMPORTANT]
> 当前可用桌面版位于 `development` 分支，尚未提供面向陌生电脑的一键二进制发行包。
> 安装过程透明展示依赖、路径、计划与卸载边界。

<details>
  <summary>目录</summary>

- [为什么是 ResearchMate](#为什么是-researchmate)
- [核心能力](#核心能力)
- [运行方式](#运行方式)
- [快速开始](#快速开始)
- [数据与 AI 边界](#数据与-ai-边界)
- [技术栈](#技术栈)
- [项目状态](#项目状态)
- [文档](#文档)
- [参与与许可](#参与与许可)

</details>

## 为什么是 ResearchMate

ResearchMate 不是只面向论文的聊天壳，也不是自动把整个工作区发送给模型的采集器。它把文字、图片、
公开 URL 候选、论文、Debug 记录和求职资料统一为可追溯资料，同时保留各领域自己的结构化视图。

```text
导入 / 发现 → 候选确认 → 最小提取 → 整理关联 → 显式 AI → 行动专题
```

确定性本地处理不依赖 AI；外部 AI 只在用户主动触发并确认发送范围后调用。来源事实、提取结果、AI
建议和用户确认分别保存，不用一次生成覆盖原始资料。

## 核心能力

- 统一管理文本、图片、公开网页候选、论文、Debug 与求职资料。
- 工作区隔离、完整归档往返、图片资产校验和本地中英文 OCR。
- 论文聊天、单篇/批量分析、工作区综述与通用资料分析均保留持久审计运行。
- 显式选择 1–20 条有序证据建立行动专题，保存目标、笔记、下一步和状态。
- AI 成功与失败历史可见；结构化结果受输入 ID 和字段范围约束。
- Windows + WSL 桌面窗口关闭时结束其启动的后端，可立即重新打开。

## 运行方式

| 方式 | 适合谁 | 启动体验 | 完整说明 |
| --- | --- | --- | --- |
| Windows + WSL 桌面 | 主要推荐路径 | 双击一个快捷方式，关窗即停 | [纯净机从零安装](docs/INSTALL_WINDOWS_WSL_FROM_SCRATCH.md) |
| WSL / Linux 浏览器 | 不需要桌面宿主 | 终端启动，浏览器访问 `127.0.0.1:8000` | [快速上手](docs/QUICKSTART.md) |
| 原生 Linux 桌面 | GTK/WebKitGTK 环境 | 应用菜单或 `researchmate` 命令 | [原生 Linux 安装](docs/INSTALL_LINUX.md) |

原生 Windows 后端当前没有发布；Windows 桌面版仍由 WSL 承载源码、Python 环境和工作区。

## 快速开始

已有 WSL、Git 和 Conda 时，先取得当前开发分支：

```bash
git clone --branch development --single-branch https://github.com/promise-157/ResearchMate.git
cd ResearchMate
```

如果是纯净 WSL，或不确定 Miniconda、Python、Node、Vue、.NET、WebView2 应该如何安装，请不要猜：
[Windows + WSL 从零安装](docs/INSTALL_WINDOWS_WSL_FROM_SCRATCH.md) 保留了逐条可复制的完整命令、
Conda ToS 规避、PowerShell PATH 排障、安装位置、更新和彻底卸载说明。

只使用浏览器且依赖已经准备完成时：

```bash
conda run -n researchmate python src/backend/run.py --no-browser
```

然后访问 <http://127.0.0.1:8000>，回到终端按 `Ctrl+C` 关闭。

Windows + WSL 桌面安装完成后，日常只需双击快捷方式。以后路径不变，更新宿主始终复用本机 JSON，
在 **Windows PowerShell** 执行同一条 `-Mode Install -ConfigPath ... -Yes` 命令；准确命令见从零安装
文档。设置页会显示当前机器的实际安装、日志、工作区边界和卸载文档，也可更换桌面快捷方式 ICO。

## 数据与 AI 边界

- 默认本机工作，不自动下载论文 PDF，也不镜像远程站点。
- 前端只访问 `/api/*`；来源与 AI provider 请求留在后端。
- Key 默认仅保存在当前后端进程；持久化便利模式会明确提示明文风险和位置。
- 每次外部 AI 调用都需要明确动作，并展示或限制实际发送范围。
- 卸载桌面宿主不会删除 WSL、Conda、源码、工作区、资产、归档或 Key。

AI 不是安装前提；没有 Key 时，本地导入、整理、模板提取、OCR 和搜索仍可工作。

## 技术栈

- Backend：Python 3.11、FastAPI、SQLite
- Frontend：Vue 3、Vite、Element Plus
- Windows desktop：.NET、WinForms、WebView2、WSL 2
- Linux desktop：GTK 3、WebKitGTK
- Verification：unittest、Ruff、Playwright、离线 fake provider

## 项目状态

当前是持续开发中的 source-backed 版本。M11–M16 与 M6-I1 已完成；下一产品切片是行动专题内显式、
可审计的行动简报。旧工作区迁移和真实招聘描述覆盖仍等待脱敏样本，不使用合成数据伪装完成。

已知限制包括：尚未在陌生纯净机器完成正式发行验收、原生 Windows 后端延期、前端主 chunk 仍偏大。
详见 [ROADMAP](docs/ROADMAP.md) 与 [CHANGELOG](CHANGELOG.md)。

## 文档

- [Windows + WSL 从零安装](docs/INSTALL_WINDOWS_WSL_FROM_SCRATCH.md)
- [Windows + WSL 安装/卸载边界](docs/INSTALL_WINDOWS_WSL.md)
- [原生 Linux 安装](docs/INSTALL_LINUX.md)
- [快速上手](docs/QUICKSTART.md) · [使用手册](docs/MANUAL.md)
- [开发与验证](docs/DEVELOPMENT.md)
- [产品规格](docs/PRODUCT.md) · [架构说明](docs/ARCHITECTURE.md) · [路线图](docs/ROADMAP.md)

## 参与与许可

欢迎通过 [Issues](https://github.com/promise-157/ResearchMate/issues) 报告可复现问题或讨论需求。提交改动
前请先阅读 [开发与验证](docs/DEVELOPMENT.md)，不要在 fixture、日志或提交中包含真实 Key 和私人工作区。

本项目使用 [The Unlicense](LICENSE.txt)。

<p align="right"><a href="#readme-top">回到顶部</a></p>
