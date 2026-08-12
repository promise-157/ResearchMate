# ResearchMate

ResearchMate 是本地优先的个人资料助手：把文字、图片、公开网页和公共数据源中的必要信息整理为可追溯、可检索的资料，并在用户明确选择范围后使用 AI 做提取、比较和归纳。

当前已经可用的通用闭环是：导入文字、图片、单个公开 URL，或从 arXiv 公开 API 发现候选 → 候选审核/本地去重/类型建议/可选 OCR → 预览并接受确定性提取 → 搜索筛选与状态管理 → 显式 AI 分析。接受的 OCR 文本独立于原始正文和运行历史，只有明确勾选时才进入搜索或 AI 输入。Debug 与求职资料都支持版本化本地字段提取和用户确认分层；求职详情可管理公司、岗位、地区、薪资、技能、经验年限和投递状态，并按确认优先的公司/岗位/投递状态筛选。Debug 还支持可解释的本地近似检索。用户可对单条资料选择发送字段，也可选择 2–20 条资料比较归纳；所有运行均保留审计历史。arXiv 摘要会映射到同一通用资料核心，同时保留论文筛选、购物车和专用视图。

项目不默认下载论文 PDF、镜像网站或绕过登录、付费墙、CAPTCHA、robots 和限流。任意网页抓取默认关闭。

## 安装与启动

要求 Python 3.11+、Node.js 18+ 和 npm。

```bash
conda create -n researchmate python=3.11 -y
conda activate researchmate
pip install -r src/backend/requirements.txt
cd src/frontend
npm install
cd ../backend
python run.py
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
