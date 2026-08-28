# ResearchMate

ResearchMate 是本地优先的个人资料助手：把文字、图片、公开网页和公共数据源中的必要信息整理为可追溯、可检索的资料，并在用户明确选择范围后使用 AI 做提取、比较和归纳。

当前已经可用的通用闭环是：导入文字、图片、单个公开 URL，或从 arXiv 公开 API 发现候选 → 候选审核/本地去重/类型建议/可选 OCR → 预览并接受确定性提取 → 搜索筛选与状态管理 → 显式 AI 分析。接受的 OCR 文本独立于原始正文和运行历史，只有明确勾选时才进入搜索或 AI 输入。Debug 与求职资料都支持版本化本地字段提取和用户确认分层；求职详情可管理公司、岗位、地区、薪资、技能、经验年限和投递状态，并按确认优先的公司/岗位/投递状态筛选。Debug 还支持可解释的本地近似检索。用户可对单条资料选择发送字段，也可选择 2–20 条资料比较归纳；所有运行均保留审计历史。arXiv 摘要会映射到同一通用资料核心，同时保留论文筛选、购物车和专用视图。

项目不默认下载论文 PDF、镜像网站或绕过登录、付费墙、CAPTCHA、robots 和限流。任意网页抓取默认关闭。

## 选择运行方式

| 环境 | 状态 | 入口 |
| --- | --- | --- |
| Windows + WSL 2 桌面窗口 | 当前支持 | 下方透明配置向导 |
| WSL/Linux 源码运行 | 当前支持 | [快速上手](docs/QUICKSTART.md) |
| 原生 Linux 桌面包 | 尚未发布 | 不会安装 Windows 组件 |
| 原生 Windows 后端 | 尚未发布 | 不会伪装为当前 WSL 版本 |

## Windows + WSL：从纯净环境安装

ResearchMate 跨 Windows 和 WSL 运行，因此不存在一个可以安全替用户决定所有路径的通用安装器。
项目提供只读检查、JSON 安装计划和显式应用三步向导；它不会自动安装或卸载下列用户所有的基础工具。

| 位置 | 依赖 | 用途 | 安装后运行是否仍需要 |
| --- | --- | --- | --- |
| Windows | WSL 2 与一个 Linux 发行版 | 承载后端 | 是 |
| Windows | WebView2 Evergreen Runtime | 桌面窗口 | 是 |
| Windows | .NET 10 SDK | 从 Git 构建自包含宿主 | 否；未来使用预编译 Release 可免装 |
| WSL | Git | 克隆和更新源码 | 仅更新时 |
| WSL | Conda/Mamba/Micromamba 兼容环境、Python 3.11 | 隔离后端依赖 | 是 |
| WSL | Node.js 18+ 与 npm | 安装 Vue 依赖并生成前端 `dist` | 构建后启动不需要 |
| WSL | Tesseract 与所需语言包 | 可选的本地图片 OCR | 仅使用 OCR 时 |

Vue、FastAPI 和 Uvicorn 都不是单独的系统安装项：Vue 等前端包由
`src/frontend/package-lock.json` 固定并由 npm 安装；后端包由
`src/backend/requirements.txt` 声明。AI Key 和 Ollama 均不是安装前提。

### 1. 用户自行准备基础工具

按照各工具官方说明安装 WSL 2、一个发行版、WebView2、Git、自己选择的 Conda 兼容发行版和
.NET 10 SDK。安装位置由用户决定。ResearchMate 不会代装或在卸载时删除它们。

如果从 Git 构建，请确保 Windows PowerShell 能运行：

```powershell
wsl --list --verbose
dotnet --version
```

### 2. 在 WSL Linux 文件系统中准备源码

以下命令在 WSL 中运行。建议使用 `/home/<用户>/...`，不要把仓库放进 `/mnt/c` 或 `/mnt/d`：

```bash
git clone https://github.com/promise-157/ResearchMate.git
cd ResearchMate

conda create -n researchmate python=3.11 -y
conda run -n researchmate python -m pip install -r src/backend/requirements.txt
```

Node/npm 必须能被桌面宿主启动的非交互 Conda 环境找到。可以自行安装系统 Node.js，也可以明确装进
该环境；下面只是可复现示例，不要求使用 Miniconda：

```bash
conda install -n researchmate -c conda-forge nodejs=20 -y
conda run -n researchmate npm --prefix src/frontend ci
conda run -n researchmate npm --prefix src/frontend run build
```

如果需要本地图片 OCR，再自行安装 Tesseract 及实际需要的语言包；不安装不会影响其他功能。

### 3. 只读检查

仍在仓库根目录，从 WSL 调用 Windows 配置向导：

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
  "$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)" \
  -Mode Check
```

向导会从当前 `\\wsl.localhost\<发行版>\...` 仓库路径推导发行版和 Linux 路径，并只读检查 WSL、
项目、环境、Python 包、Node/npm、Vue 依赖、前端构建、WebView2、.NET 和可选 Tesseract。无法唯一
判断 Conda 可执行文件时才会询问；也可显式传入：

```text
-Distro Ubuntu
-ProjectPath /home/alice/ResearchMate
-CondaExecutable /home/alice/miniforge3/condabin/conda
```

### 4. 生成并审查计划

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
  "$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)" \
  -Mode Plan
```

向导生成被 Git 忽略的 `researchmate-install-plan.json`，列出实际选择和所有写入：

- Windows 宿主安装目录，默认优先 `D:\Apps\ResearchMate`；
- WSL 发行版、项目绝对路径、环境可执行文件和环境名；
- `%LOCALAPPDATA%\ResearchMate\desktop-config.json`；
- 唯一的桌面快捷方式和当前用户卸载项；
- 不归 ResearchMate 所有、卸载时绝不删除的外部依赖和用户数据。

打开 JSON 确认无误后才继续。

### 5. 应用已确认计划

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File \
  "$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)" \
  -Mode Apply
```

首次从 Git 构建会使用 Windows .NET SDK 生成约 120 MiB 的自包含宿主。安装完成后，日常启动不再
需要 .NET SDK、Node 或 npm。桌面只创建一个 `ResearchMate` 快捷方式；快捷方式不保存个人路径，
宿主从 `desktop-config.json` 读取用户确认的 WSL 配置。关闭唯一窗口会停止本窗口拥有的后端，不会
关闭整个 WSL 或影响其他 WSL 进程。

完整安装、重新配置、故障诊断和卸载边界见
[Windows + WSL 安装说明](docs/INSTALL_WINDOWS_WSL.md)。

## 源码启动

完成上面的 WSL 依赖准备后，也可以不安装桌面宿主：

```bash
conda run -n researchmate python src/backend/run.py
```

启动后通常访问 `http://127.0.0.1:8000`。开发模式（前端热更新）使用：

```bash
cd src/backend
python run.py --dev --no-browser
```

若端口确由旧进程占用，`python run.py --kill --no-browser` 会精确查找并终止 Linux listener；WSL 中由 Windows 进程占用时会转用 PowerShell 查找 Windows listener。启动器会在终止后重新验证端口，权限不足时给出明确诊断和 `RESEARCHMATE_PORT` 换端口方式。

打开“资料中心”即可粘贴文字、导入不超过 10 MB 的 PNG/JPEG/WebP 图片，或明确提交一个公开网页。招聘描述可明确保存为“求职”，按“公司、岗位、地区、薪资、技能、经验年限、投递状态”分行书写以使用离线字段提取。手工填写在文字资料上的来源网址只记录出处；只有“导入公开 URL”动作会受控读取页面并放入候选箱，用户接受后才正式入库。图片 OCR 使用本机 Tesseract，不会自动发送给外部服务。OCR 完成后需在详情中检查预览并点击接受，系统不会改写原始图片资料正文。完整操作见 [快速上手](docs/QUICKSTART.md) 和 [使用手册](docs/MANUAL.md)。

## AI（可选）

外部 API 是默认 AI 增强路径。以 DeepSeek 为例，推荐通过环境变量提供 Key；Key 不经过网页，也不会写入项目配置：

```bash
export RESEARCHMATE_AI_TYPE=deepseek
export RESEARCHMATE_AI_KEY='your-key'
export RESEARCHMATE_AI_URL='https://api.deepseek.com'
export RESEARCHMATE_AI_MODEL='deepseek-v4-pro'
```

也可在设置页输入 Key。默认“安全模式”只保留到当前后端退出；明确选择“便利模式”后，Key 会在风险提示下明文保存到已被 Git 忽略的 `src/backend/config.yaml`（权限 `0600`），从而在重启后继续生效。界面显示实际路径，并提供“清除 Key”；切回安全模式也会删除磁盘副本。设置页的“测试连接”不会自动运行；点击后会再次确认它将产生一次可能计费的最小外部请求，且不会发送工作区资料。DeepSeek 连接测试和结构化 JSON 任务显式关闭思考，避免思考内容耗尽有界输出额度；开放式聊天保留服务商默认。通用资料分析只发送详情页中明确勾选的字段，正文最多发送前 12,000 个字符。成功运行还记录服务商返回模型、token、耗时和可用请求标识；失败只保存脱敏错误。分类、结构化提取和两资料比较已使用独立无敏感工作区完成受控真实 DeepSeek 烟测，真实调用不进入 CI。论文聊天现在按工作区持久保存多轮消息、明确论文范围、模型用量和失败，刷新/重启可恢复且工作区隔离；它没有实时网页搜索，网络资料应先通过具名来源或受控 URL 导入并审核。购物车可对单篇或最多 20 篇论文运行逐篇审计分析，每篇只发送有界标题与摘要；刷新后可查看成功或脱敏失败，部分失败不会显示整批成功。新建议只写运行历史，不改写论文来源事实，旧 `papers.ai_*` 仅作只读兼容展示。AI 结果只是建议，不会改写资料。Ollama 仅是连接用户现有本地服务的可选后端，项目不会安装它或下载模型。不要把真实 Key 发给 AI 编程助手或写入仓库。

## 新 Codex 会话与开发

从仓库根目录开启 Codex。Codex 会自动读取根目录 [AGENTS.md](AGENTS.md)，再按其中协议阅读：

- [产品规格](docs/PRODUCT.md)：要做什么、明确不做什么；
- [架构约束](docs/ARCHITECTURE.md)：数据层次和安全不变量；
- [当前路线图](docs/ROADMAP.md)：已经完成什么、下一步是什么。

`AGENTS.md` 只放长期有效的工作协议，路线图只记录验证过的当前事实。这样新会话不依赖旧聊天记录，也不会从过时的 Claude 辅助文档猜任务。

准备公开到 GitHub 前，只检查文件名和 Git 索引，不要为了审计而打印本地配置、数据库或 Key 内容：

```bash
git status --short
git status --short --ignored
git diff --check
git ls-files | rg '(^|/)(\.env|config\.yaml)$|\.(db|sqlite|sqlite3|pem|key|p12|pfx)$'
```

最后一条正常情况下应无输出。`.gitignore` 已排除运行时配置、环境变量文件、私钥/凭证、SQLite 及旁路文件、用户数据/导出、依赖、构建与测试产物。`src/data/.gitignore` 和 `.env.example` 类脱敏模板仍可提交。已经进入 Git 历史的敏感文件不会因后来加入 `.gitignore` 自动消失，公开前仍需单独检查提交历史。Playwright 下载的浏览器位于 WSL 用户缓存，不在仓库中；工程完成前保留，最终收尾时再卸载。

验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 conda run -n researchmate python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 conda run -n researchmate python -m compileall -q src/backend
conda run -n researchmate ruff check src/backend tests
cd src/frontend && npm run lint && npm run build && npm run test:e2e
git diff --check
```

## License

[The Unlicense](LICENSE.txt)
