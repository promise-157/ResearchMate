# Hexo 博客集成计划

## 目标与用户入口

日常博客操作只从 Windows 快捷方式启动的 ResearchMate 窗口进入：

```text
Windows .lnk -> WebView2 ResearchMate -> /api/blog/*
  -> WSL 后端固定操作 -> /home/promise/myblog 的机器接口
```

PowerShell/Windows Terminal 只用于安装、修复和卸载。`myblog` 是独立成熟的发布工程，ResearchMate
只是它的受控操作台，不接管其构建、主题、文章或 GitHub Pages 所有权。首版不提供任意插件、任意命令、
自动部署、Git 操作、完整 Markdown 编辑器、远程网站强制内嵌或资料自动发布。

## 已调查事实

- `myblog` 是 Hexo 7.3 + Icarus，使用项目内 `package-lock.json` 和可用的本地 Hexo；当前有 31 篇
  Markdown，文章采用分类/标题目录并启用文章资源目录。
- 当前 `create_post.sh/.bat` 是交互式、依赖调用目录和全局 `hexo` 的人用脚本，没有 JSON、统一退出码、
  dry-run、冲突计划或批量导入，不适合直接接网页。
- `scripts/fix-image.js` 在构建时处理部分相对图片；导入器仍必须自己验证、复制和规范化图片，不能把
  构建过滤器当安全边界。
- GitHub Actions 在 `main` push 后构建 Hexo 并更新 `gh-pages`；ResearchMate 的“打开公开博客”只访问
  用户配置的公开 URL，不把 build 冒充发布，也不自动 commit/push。
- ResearchMate 的 Windows 宿主持有一个私有 WSL supervisor；backend 在独立进程组中运行，关闭窗口
  会 SIGTERM 该组并在超时后只 SIGKILL 该组。未脱离该组的 Hexo 子进程会被兜底回收。
- 当前设置 API 只公开脱敏设置；博客路径和公开 URL 应进入相同本机配置边界，不进入任何工作区 SQLite。

## 数据所有权

| 数据 | 唯一事实来源 | ResearchMate 是否复制 |
| --- | --- | --- |
| 文章正文、front matter、图片 | `myblog/source` | 不复制到工作区数据库 |
| scaffold、Hexo/主题规则 | `myblog` | 不复制、不重新解释为第二套规则 |
| 博客路径、公开 URL、启用状态 | ResearchMate 本机忽略配置 | 不写工作区 |
| 待确认导入计划、操作报告 | `myblog/.researchmate/` 原子 JSON/暂存目录，加入忽略 | 不写工作区；应用/取消后清理输入暂存 |
| 构建输出 | `myblog/public` | 不复制 |

`.researchmate/` 只保存计划、哈希、报告和尚未应用的临时上传，不是文章库。`list` 每次从 Hexo 文章
目录读取元数据；应用计划后文章立即以 `myblog/source` 为准。

## 两个仓库分别修改什么

### myblog

新增一个无 shell 拼接、从任意目录可调用的机器接口，例如 `tools/blog-cli.mjs`。stdout 只输出带
`schema_version` 的单个 JSON，诊断写 stderr，退出码统一：`0` 成功、`2` 输入/冲突、`3` 环境、
`4` 文件安全、`5` 构建失败、`10` 内部错误。命令至少包括：

- `check`：解析并固定仓库根目录；检查 Node、本地 Hexo、`source/_posts`、scaffold 和资源目录；不联网。
- `list`：只返回文章 ID、标题、日期、分类、标签、草稿状态、相对路径和资源数量，不返回正文。
- `new`：参数化创建草稿；标题、slug、分类、模板和冲突策略均验证；默认冲突停止。
- `import --dry-run`：扫描已暂存输入，验证 Markdown/front matter/图片，返回新增、跳过、冲突、重命名、
  图片映射和目标相对路径；生成内容哈希和不可猜测 `plan_id`，不写 `source`。
- `import --apply --plan-id ...`：只应用同一份未过期计划；复核输入哈希及目标仍未变化，失败保持原子性。
- `build`：通过项目锁定的本地 Hexo 执行 clean/generate，超时和输出有界；绝不调用 deploy。

现有交互脚本可以继续作为人工入口，但应改为调用机器接口，避免两套创建规则。不得自动 commit、push、
deploy，也不得把部署配置或凭据写入 JSON/日志。

### ResearchMate

- `services/blog_integration.py`：验证配置、固定允许操作、通过 argv 数组调用已配置博客根目录下的固定
  CLI；`shell=False`，不接受 UI 传来的命令、可执行路径、工作目录或环境变量。
- `services/blog_imports.py`：有界接收上传、规范相对路径、调用 dry-run/apply，并映射稳定错误。
- `/api/blog/settings|check|posts|drafts|imports|build`：请求模型和 HTTP 边界。apply 只接收服务端
  生成的 `plan_id`，不能重新提交目标路径或 shell 参数。
- 设置页新增“Hexo 博客”区；博客页使用懒加载路由。未启用或检查失败时导航不显示，直接访问路由只
  显示配置引导，不加载博客 npm 依赖或启动进程。
- 前端通过现有 `/api/*` 边界操作，不直接访问 WSL 文件，也不执行 `wsl.exe`。
- “打开公开博客”由用户明确点击后把配置 URL 交给桌面宿主的新 WebView2 窗口或系统浏览器；不使用
  iframe 强制嵌入，也不由后端抓取远程站点。

只有出现 Hugo 等第二个真实目标后，才从这个具名实现提取 publishing adapter。

## 配置与信任边界

- 设置保存 `enabled`、绝对 WSL 博客路径和公开博客 URL；默认未启用。公开 URL 只校验/显示/打开，
  后端不主动访问。
- 请求不能临时覆盖博客路径。配置路径解析后必须是目录，包含预期版本的机器接口、`package.json`、
  本地 Hexo 和 `source`；检查结果明确提示“构建会执行此受信任博客仓库中的本地代码”。
- API 只能创建草稿、计划/应用导入、构建和读取元数据/报告；没有通用 exec 或脚本名称参数。
- 子进程使用最小环境、固定 cwd、超时、stdout/stderr 字节上限和并发互斥；错误响应不回显环境或配置。
- 一个博客写操作在执行时拒绝第二个写操作；list/check 可只读并发。关闭应用时不接受新操作。

## Windows 上传与归档安全

页面支持三种输入：多个独立 `.md`、带 `webkitRelativePath` 清单的目录、ZIP。浏览器上传文件本身和
相对路径清单，用户不接触 `/mnt/c`。

首版建议边界：最多 100 篇 Markdown、500 个图片、单 Markdown 2 MiB、单图片 10 MiB、上传与解压后
总量各 200 MiB。只接受 UTF-8 `.md` 和 PNG/JPEG/WebP/GIF；其他文件进入“跳过/不支持”报告，不执行。

- 所有路径使用 POSIX 相对路径；拒绝绝对路径、`..`、空段、NUL、盘符、UNC、反斜杠混淆和大小写重复。
- ZIP 拒绝加密、符号链接、未知压缩、重复成员、压缩炸弹和声明/实际大小不符。
- 目录上传不信任浏览器 MIME；按扩展名、文件头和大小复核图片。Markdown 图片只可引用本次输入树内文件。
- 默认同名策略为 `stop`；`skip` 或确定性 `rename` 必须在 dry-run 计划中由用户明确选择并再次确认。
- apply 使用临时同父目录写入、fsync/rename 或带回滚清单的原子安装；不能留下半篇文章或半套图片。

## 后续可选的本地预览

首切片不启动 Hexo server。公开博客已经由 GitHub Pages 托管，本地 `build` 足以先验证内容能否生成；
只有真实使用证明用户需要在推送前查看主题渲染时，才增加本地预览。

届时预览必须由后端以前台子进程启动、继承后端 WSL 进程组、只绑定 `127.0.0.1`，并由显式停止、
FastAPI shutdown 和桌面 supervisor 三层回收。它仍不能与 Git commit/push 或部署混合。

## 首个完整纵向切片验收条件

1. 未配置用户不需要安装博客依赖，导航不显示博客入口，普通 ResearchMate 功能不受影响。
2. 设置页展示、保存并检查博客路径和公开 URL；路径无效、CLI 版本错误或本地依赖缺失均可操作地失败。
3. 博客页列出真实文章元数据且不读取/返回正文；可在窗口内创建一篇草稿，冲突不会覆盖。
4. 多 Markdown、目录和 ZIP 均先上传一次并展示 dry-run：新增、跳过、冲突、图片、重命名和目标路径。
5. 用户再次确认 `plan_id` 后才 apply；输入或目标变化会拒绝旧计划，成功后 list 立即反映新文章。
6. build 只调用本地锁定 Hexo，显示成功/失败、耗时和有界日志，不 deploy/commit/push/联网。
7. 用户可明确点击“打开公开博客”；未配置 URL 时给出设置引导，页面加载不自动访问远程网站。
8. 操作报告由后端/CLI持有，页面刷新后仍可见；工作区切换不改变博客，也不把报告写入工作区数据库。
9. 单元测试使用临时博客 fixture、假 process runner 和离线 ZIP；Playwright 使用离线 API mock，不启动
   Hexo、不访问 GitHub Pages。

## 实施顺序与门禁

1. **R1 一致性收口（不扩展功能）**：清除工作区切换时的排序/部分加载残留；统一 UI/API/文档的排序
   数量上限；补候选 AI 中断恢复、失败历史和跨工作区浏览器断言。通过现有全套门禁后不再改 R1。
2. **B0 myblog 机器契约**：完成 check/list/new/import/build CLI、临时 fixture 和离线测试；人工脚本
   改为薄包装。没有该稳定契约，不接 ResearchMate UI。
3. **B1 ResearchMate 完整首切片**：设置、可选导航、文章/草稿、上传计划/确认应用、构建报告和打开
   公开博客按上述九条一起交付。
4. **真实验收**：先复制一份脱敏临时博客做导入/构建；全部通过后，用户再明确授权对真实
   `/home/promise/myblog` 创建测试草稿。始终不 deploy、commit、push 或联网。

计划确认后，`ROADMAP.md` 只增加一个简短 B0/B1 入口并链接本文，不复制本计划正文。

## R1 针对性复核结论（2026-08-30）

R1 的发现、补全、审核、保存规则、源码、确定性排序和候选简报均存在完整后端路径，182 项后端/桌面
测试（其中 1 项受限沙箱 skip）及 18 项离线 Playwright 在完成时通过；E 的失败不推进检查点、归档/清空
及 F3 的结构/配置失败审计都有代码和单元证据。真实网络验收范围与文档一致，F3 未调用真实 AI。

复核发现的完成证据和隔离偏差已在博客实施前收口：F2 全链路统一为 1–20 条；工作区切换先清空候选、
任务、规则、简报和本地排序；同 ID 候选、局部规则/简报加载失败均不会显示上一工作区数据；
`candidate_ai_runs` 的 running -> failed 恢复、失败历史和跨工作区隔离已有直接离线断言；架构恢复清单
也已同步。以上没有新增 R1 能力。
