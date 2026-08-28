# 当前路线图

本文只保存新会话必须知道的当前事实、仍有效债务和下一最小切片。已完成里程碑的详细过程由 `CHANGELOG.md` 与 Git 历史保存，不在这里重复。

## 已验证基线

| 里程碑 | 已完成能力 |
| --- | --- |
| M1 | 通用文字资料导入、规范化、精确去重、搜索筛选和持久状态 |
| M2 | 显式范围的单资料 AI 与 2–20 条比较，结构校验和运行审计 |
| M3 | 用户图片资产、隔离存储和可审计本地 Tesseract OCR |
| M4 | 受控单个公开 URL 读取、候选审核和 SSRF/robots/大小边界 |
| M5 | 兼容论文幂等映射到通用资料核心，不覆盖用户字段 |
| M6 | Debug 模板、确定性提取/用户确认分层和本地近似检索 |
| M7 | 受限 arXiv API 发现、持久任务和多候选审核 |
| M8 | OCR 结果显式接受、可选搜索/AI 范围和离线浏览器验收 |
| M9 | 求职模板、确认优先字段与组合筛选，共享最小模板注册层 |
| M10 | DeepSeek 生产契约、脱敏错误、显式连接测试、用量审计和受控真实烟测 |
| M12 | PNG/JPEG/WebP 完整解码、字节/尺寸/像素/解压炸弹限制、资产完整性复核和本机中英文 OCR 验收 |
| M13 | 单公开 URL 与 arXiv 的受控真实响应、完整浏览器候选审核和采集任务中断恢复 |
| M14 / M3-I2 | 包含一致数据库与图片资产的可移植归档，以及清空/删除资产隔离清理 |
| M14 / OCR | 用户显式触发且不复用成功结果的图片 OCR 重新处理，追加审计并保持接受层独立 |
| M14 / recovery | 采集、聊天、通用处理和论文 AI 的完整启动中断恢复 |
| M15 | 1 万/5 万条多语言临时 SQLite 对比 LIKE 与 FTS5，基于延迟、语义和体积证据暂不迁移 |
| M16 | 当前工作区内从 1–20 条明确选择的资料建立行动专题，持久保存目标、用户笔记、下一步、状态和有序证据 |

最新已验证基线（Windows + WSL 与原生 Linux source-backed 桌面，2026-08-28）：后端/桌面 142 项通过（受限沙箱内 1 项 Unix socket skip，沙箱外同项单独通过），`compileall`、Ruff、前端 lint/生产构建、Windows Debug/Release 构建、宿主离线契约及 PowerShell 5.1 语法通过。Windows + WSL 的真实生命周期、可见 fixture、自包含发布、透明计划安装和无参数快捷方式保持通过。Linux 的全依赖检查、JSON 计划、临时 XDG 安装/配置/完整卸载、用户级真实安装、单实例 socket、WSLg/X11 fixture 退出、端口释放及无进程/socket 残留通过；fixture 页面内容仍待用户目视确认。两端均未在陌生纯净目标机从零验收，不能写成一键正式发行版。桌面探针只使用临时假后端和本机健康检查，不读取 `src/data/`，不调用真实 AI、真实来源或真实 Key。M16 的 Playwright 16 项基线与 M13 经授权的四次受控公开请求事实保持不变。生产构建仍有 M8-P1 的大 chunk 和第三方 PURE 注释提示。

## 已完成：M11 统一论文 AI、资料 AI 与聊天

M11 不合并不同生命周期的数据表。通用资料 AI 使用 `extraction_runs`，持久聊天使用 `chat_sessions/chat_turns`，论文分析与后续综述使用 schema v10 的 `paper_ai_runs` 并以 `run_kind` 区分。

### 已完成并验证：持久多轮论文聊天

- [x] 会话和轮次属于当前工作区，刷新、重启和切换工作区后不丢失、不串库。
- [x] 每轮调用前保存 `running`，记录消息、明确附加论文、实际历史范围、提示词版本和配置模型。
- [x] 成功保存回复、返回模型、token、耗时和请求 ID；失败保存脱敏错误。
- [x] 单轮最多附加 12 篇，每篇摘要最多 1,200 字符；只取最近 10 个成功轮次且历史总计最多 12,000 字符。
- [x] storage/service/API/UI 和 Playwright 全部使用离线 fixture 验证。

### 已完成并验证：购物车单篇/批量论文分析

- [x] schema v10 幂等新增独立 `paper_ai_runs`，清空路径包含新运行；旧论文、通用 AI、聊天和兼容字段不迁写。
- [x] 单篇/批量只接受当前工作区购物车中的 1–20 篇不重复论文，并为每篇先保存 `running`。
- [x] 每篇保存论文 ID、`title + abstract` 范围、输入哈希、处理器/提示词版本、provider 和配置模型；标题最多 300 字符，摘要最多 3,000 字符。
- [x] 成功保存严格结构校验后的建议及模型元数据；失败保存脱敏错误并继续其余论文。
- [x] 新分析只写运行记录，不更新 `papers` 的任何字段。旧 `ai_innovation/ai_technologies/ai_code_url/ai_analyzed/cart_ai_analyzed` 仅作明确标注的兼容只读展示。
- [x] API 返回逐篇运行与整体 `succeeded/partial/failed`；只有零失败才 `ok=true`，部分失败不得显示整批成功。
- [x] UI 冷启动、刷新、分析后和工作区切换均从当前工作区恢复购物车与历史，显示逐篇状态、范围、模型、用量和错误。
- [x] 临时 SQLite、假 provider 和离线 Playwright 覆盖迁移、边界、来源字段不变、部分失败、刷新和工作区隔离。

实现路径：

```text
CartDrawer.vue -> src/frontend/src/api/index.js -> /api/cart/analyze*
  -> services/paper_analysis.py -> processors/paper_ai.py
  -> storage/paper_ai_runs.py -> workspace SQLite paper_ai_runs
```

旧 `CartDrawer -> route 内业务逻辑 -> LLMAnalyzer -> UPDATE papers.ai_*` 路径已退出购物车分析；工作区综述迁移后 `LLMAnalyzer.review_with_prompt` 也不再有现役调用路径。

购物车切片及随后稳定性加固曾以 97 项后端测试和 7 项 Playwright 验证；M11 完整基线以本页顶部最新记录为准。

### 已完成并验证：工作区与 AI 运行稳定性加固

- [x] 请求连接固定到开始时的工作区；切换期间完成的聊天/论文分析不会写入新工作区。
- [x] 连接租约阻止清空或删除仍在使用的工作区，数据库与资产清空目标保持一致。
- [x] 启动恢复遗留的聊天和论文 AI `running` 状态；终态记录不会被迟到响应再次覆盖。
- [x] 前端统一协调切换/新建/导入，购物车和聊天以 generation 丢弃旧响应，短写操作与切换有确定顺序。
- [x] 论文查询收口到 repository，AI 未知异常统一脱敏，前后端数量限制由各自单一常量派生。

### 已完成并验证：工作区综述

- [x] 追踪旧综述路径。当前没有现役 UI 调用 `/api/workspace/review`；`triggerWorkspaceReview()`、`fetchLatestSession()` 和 `AIReviewCard.vue` 均未被组件使用，论文页“综述报告”实际走持久聊天。旧 route 隐式读取全工作区关键词和无显式排序的最多 20 个标题，只保存成功结果且 `task_ids=[]`。
- [x] 建立真实显式入口：用户从当前工作区选择 2–20 篇论文，调用前查看并确认有序 ID、标题每篇 300 字符和摘要每篇 2,000 字符的精确边界。
- [x] `paper_ai_runs` 以独立 `run_kind=workspace_review` 保存一次多论文综述的范围、哈希、处理器/提示词版本和模型配置，不合并聊天或 `extraction_runs`。
- [x] 调用前保存 `running`；成功保存经 schema 校验且只引用输入 ID 的结构结果与模型元数据，失败保存脱敏错误。
- [x] 新 route 只做 HTTP 边界，流程、provider 和 SQL 分别属于 service、processor、repository；全量 ID 在外部调用前验证，且不修改 `papers`。
- [x] `workspace_reviews` 冻结为只读兼容历史；新综述不写旧表，UI 不把旧结果伪装为完整审计运行。
- [x] 第二个真实论文运行展示用例出现后提取 `PaperAIRunHistory.vue`，购物车与综述共享状态、范围、模型、用量、结果和失败展示。
- [x] 临时 SQLite、假 provider 与离线 Playwright 覆盖字符边界、来源事实不变、失败、刷新、工作区隔离和旧表零写入。

M11 判定完成。

## 已完成并验证：M12 M3-I1 图片解码与 OCR/资产完整性

- [x] 图片导入在任何资产目录、文件或数据库记录创建前由 Pillow 完整解码，只接受实际 PNG/JPEG/WebP；文件名、MIME 或文件头不能替代解码事实。
- [x] API 与 service 统一限制 10 MiB、最长边 12,000 像素、总计 4,000 万像素，并把 Pillow 解压炸弹警告/错误转换为可见拒绝。
- [x] schema v11 幂等保存可信宽高；预览和 OCR 前复核工作区路径、字节数、SHA-256、格式及已有宽高，落盘篡改不会继续使用。
- [x] 损坏、伪装、截断和超限 fixture 均返回可见错误，测试断言 `items/assets/extraction_runs/accepted_extractions` 零新增且没有资产目录或孤立文件。
- [x] 完整 PNG/JPEG/WebP 离线 fixture 覆盖导入、受控预览和 OCR 输入；OCR 成功/失败均按现有 `extraction_runs` 审计，失败不创建接受值，既有 OCR 接受层与用户确认分层未改写。
- [x] 资产目录从请求固定连接的工作区路径派生，临时双工作区验证不能跨库读取资产。
- [x] 本机 Tesseract 5.5.2 使用可用的 `eng+chi_sim` 完成中英文临时图片真实 OCR；无中文包时 processor 保持英文退回，不调用云端。
- [x] UI 显示格式和三类限制，保留后端具体错误；离线 Playwright 覆盖损坏导入、成功导入/预览以及 OCR 失败与成功状态。

M12 的 M3-I1 判定完成；后续 M13 与 M14/M3-I2 进度见下方。

## 已完成并验证：M13 M4-I1 单公开 URL 真实与浏览器验收

- [x] 受控真实烟测验证公开 DNS、TLS、robots、重定向、UTF-8 多语言正文和重定向后非 HTML 拒绝；只访问三个无认证页面，不写工作区。
- [x] robots 规则按来源缓存但对每个当前路径重新执行，同源重定向不能从允许路径绕到禁止路径；跨源仍重新读取规则。
- [x] HTTP charset 优先，其次 BOM 和前 4 KiB HTML meta；未知或错误声明返回可见失败，成功 provenance 保存最终字符集与重定向次数。
- [x] 离线测试覆盖逐跳 DNS、真实 peer 公网复核、最多 3 次重定向、解压后 1 MB、最终 HTML 类型和失败 job 持久化。
- [x] 离线 Playwright 覆盖 URL 对话框、持久失败提示、候选与正式资料分离、明确拒绝及明确接受入库；候选显示最终 URL、字符集和重定向次数。

M4-I1 判定完成。

## 已完成并验证：M13 M7-I1 arXiv 真实、浏览器与中断恢复

- [x] 经用户授权向固定 arXiv 官方 HTTPS API 发出一次 `local retrieval`、`limit=1` 的无敏感查询；真实 Atom 的标题、摘要、规范 URL、作者、分类、发布时间和采集时间符合离线契约，不写工作区、不下载 PDF。
- [x] collector 禁用环境代理与重定向，只接受 Atom/XML 和严格 UTF-8；在流式读取中限制解压后响应为 2 MiB，HTTP、类型、大小、编码和 XML 失败均转为稳定错误。
- [x] `running` collection job 在应用启动时恢复为带明确中断说明的失败；成功/失败终态及候选保持不变，重复恢复幂等。
- [x] 离线 Playwright 覆盖查询与 1–20 条参数、持久失败、两条候选逐条接受/拒绝、provenance 展示、刷新和工作区隔离；接受前不创建正式资料。

M7-I1 与 M13 判定完成；M14 的首个纵向切片见下方。不要重做已经恢复的聊天、论文 AI 或采集 job。

## 已完成并验证：M14 M3-I2 可移植工作区与资产清理

- [x] 导出使用 SQLite online backup 固定一致 snapshot；版本 1 ZIP 只包含 `manifest.json`、`workspace.db` 和 snapshot 引用的用户图片，不包含配置、Key、日志或其他工作区资产。
- [x] 导出前逐项复核工作区路径、字节数、SHA-256、完整解码格式和尺寸；资产缺失或篡改返回可见错误，不生成伪完整备份。
- [x] 导入限制 512 MiB 压缩/解压总量、100 MiB 数据库、1,000 个资产和单图 10 MiB；拒绝路径穿越、符号链接、加密/未知压缩、重复/额外/缺失成员、错误版本、损坏数据库及资产事实不一致。
- [x] 导入在新数据库路径下重建隔离资产目录并重写 `storage_path`；最终数据库再次用 online backup 固化 WAL 中的路径变化。PNG/JPEG/WebP、OCR 运行和接受文本往返后仍可读取，原/导入工作区互不影响。
- [x] 无图片旧 `.db` 保持兼容；含资产记录的裸数据库明确拒绝并要求完整 ZIP，避免制造断链工作区。
- [x] 清空与删除测试同时验证目标数据库和资产目录被清理，另一个工作区数据库/资产保持不变；既有连接租约保护不回退。
- [x] UI 明确区分完整归档与旧数据库，导出错误、导入错误和成功切换均由离线 Playwright 验证。

M3-I2 判定完成；其后的最小切片选择了图片 OCR 显式重新处理，完成事实见下方。

## 已完成并验证：M14 图片 OCR 显式重新处理

- [x] 追踪现有 `Materials.vue -> /api/items/{id}/ocr-runs -> image_materials.run_local_ocr -> LocalOCRProcessor -> extraction_runs/accepted_extractions` 路径，确认旧 service 会按相同输入静默复用成功运行。
- [x] 每次用户明确运行或重新运行 OCR 都先追加新的审计记录；相同资产哈希和处理器版本不再复用既有成功结果，成功与失败历史均保留。
- [x] 重新处理继续复核当前工作区资产完整性，不修改图片来源字段、资产记录、原始正文或现有已接受 OCR；只有再次明确接受新的成功运行才更新接受层。
- [x] UI 明示每次点击会新建审计运行，已有历史时显示“重新运行本地 OCR”；成功提示接受层未改变，失败后刷新并展示失败运行。
- [x] 临时双工作区与离线 fixture 覆盖连续成功、API 成功/失败、来源和资产事实不变、成功/失败历史、接受层保持及再次接受、同 ID 工作区隔离。
- [x] 离线 Playwright 覆盖已有接受值时重新处理成功与失败，验证三条历史均可见且新结果不会自动接受。

图片 OCR 显式重新处理最小纵向切片判定完成。

## 已完成并验证：M14 完整启动中断恢复

- [x] 盘点所有现役持久 `running` 生命周期：`collection_jobs`、`chat_turns`、`extraction_runs` 和 `paper_ai_runs`；前三类既有采集、聊天和论文 AI 恢复保持不变，确认唯一缺口是通用处理运行。
- [x] repository 为遗留 `extraction_runs.status=running` 提供统一失败恢复，错误只说明上次退出导致中断并提示重新执行，不保存或暴露输入正文。
- [x] 应用既有启动遍历对每个合法工作区执行恢复；OCR、模板提取、单资料 AI 和比较共享该通用运行表，因此不再出现永久“运行中”。
- [x] 恢复不改写资料、资产、模板、接受层、结果或已有成功/失败终态；多工作区均恢复，重复执行计数为零，损坏数据库继续由既有隔离边界跳过。
- [x] 现有 `/analysis-runs` 与 Materials 历史直接展示恢复后的失败及重新执行提示；离线 Playwright 验证不再显示“运行中”。

M14 的可移植工作区、显式 OCR 重新处理和全部现役持久任务中断恢复均已完成，M14 判定完成。

## 已完成并验证：M15 SQLite FTS 评估

- [x] 可重复离线脚本只在临时目录生成工作区形状的 1 万/5 万条中英文资料、已接受 OCR、类型和状态分布，不读取用户数据。
- [x] 九类查询覆盖中文、英文大小写、字面通配符、接受层显式范围、组合过滤、分页契约及一至两个汉字回退；LIKE 与 FTS5 trigram 完整结果集合一致。
- [x] 5 万条时现有 LIKE 中位数约 6–22 ms；FTS 对三字以上选择性查询降至约 0.02–1.2 ms，但高频/短中文仍需 LIKE。
- [x] FTS 使评估数据库从 26.33 MiB 增至 69.47 MiB（约 +164%），并要求资料与接受层全生命周期事务同步、旧库回填和归档派生索引策略。
- [x] 当前个人工作区规模下没有证据支持迁移；服务端搜索 p95 超过 100 ms、典型工作区超过 5 万条或出现相关度/高亮需求时重新评估。embedding 只在真实查询证明语义召回需求后考虑。

M15 判定完成，评估报告见 [SEARCH_EVALUATION.md](SEARCH_EVALUATION.md)。下一步优先偿还无需外部样本的 M6-I1 Debug 浏览器闭环；M5-I1 与 M9-I1 仍等待用户提供脱敏真实副本/样本。

## 已完成并验证：M6-I1 Debug 浏览器闭环

- [x] 从空工作区显式导入 Debug 文字资料，验证类型、标签和五字段本地提取入口。
- [x] 用户确认错误与根因后重新本地提取，新的确定性事实可见且确认值保持优先；两次 `template_extract` 审计历史均显示为可读的“本地模板提取”。
- [x] 错误字段筛选读取确认优先的有效值；可解释近似结果显示分数及共同 token，不调用外部服务。
- [x] 刷新和双工作区切换后确认值、历史和筛选结果不丢失、不串库。
- [x] 完整流程由离线 Playwright 覆盖，不依赖真实 Debug 内容或网络。

M6-I1 判定完成。

## 已完成并验证：M16 证据到行动工作台

实现路径：

```text
Materials.vue 资料选择 -> src/frontend/src/api/index.js -> /api/action-projects
  -> services/action_projects.py -> storage/action_projects.py
  -> workspace SQLite action_projects/action_project_items
```

- [x] 用户从当前工作区明确选择 1–20 条资料创建行动专题；标题、目标、用户笔记/当前结论、明确下一步和进行中/已完成/已归档状态均持久保存。
- [x] 专题证据只引用通用资料并保存明确顺序；创建或整体替换前一次验证全部 ID、重复项、数量和当前工作区归属，失败不留下部分清单。
- [x] 新建、编辑、状态切换、证据追加/移除/上下调整和返回资料详情均有真实 UI/API/storage 路径；API 失败可见，刷新与工作区切换后状态恢复且不串库。
- [x] 专题操作不修改资料来源事实、正文、资产、提取运行或已接受层；用户笔记和状态与后续机器建议保持独立。
- [x] schema v12 迁移幂等；清空工作区会清理专题，完整工作区归档往返保留专题文字和有序证据。
- [x] 临时 SQLite 离线单元测试覆盖来源不变、原子性、隔离、迁移、清空与归档；Playwright 覆盖完整成功/失败、编辑、排序、刷新、隔离及返回来源闭环。

M16 的首个证据到行动纵向切片判定完成。它不是通用任务管理器；下一步应在这个明确证据边界上增加可审计的辅助产物，而不是扩张项目管理字段。

## 仍有效的跨里程碑债务

| ID | 后续处理 |
| --- | --- |
| M5-I1 | 等待用户提供脱敏真实旧工作区副本；验证论文/资料映射，并为来源刷新设计显式差异预览与接受。合成迁移测试不能替代该验收。 |
| M8-P1 | 前端主 chunk 仍超过 500 kB；需以首屏收益为依据做路由/组件拆分。 |
| M9-I1 | 等待用户提供脱敏招聘描述；验证字段覆盖，自由叙述、薪资和年限规范化只按真实缺口扩展。 |

## 已完成技术验证与本机 source-backed 安装：Windows + WSL 桌面宿主

ResearchMate 将保持单仓库、单主干和一套共享产品核心，不建立 Windows、Linux、WSL 三条长期
平台分支，也不让单个平台安装器引入其他平台依赖。发布目标分为 Windows + WSL 桌面宿主、原生
Linux 和原生 Windows；安装、进程、用户目录及系统集成留在平台适配/打包边界，API、service、
storage、Vue UI、schema/migration、审计和归档契约不得复制分叉。

Windows + WSL 最小技术原型已经实现：C#/.NET 10 WinForms WebView2 宿主持有私有 WSL supervisor，
等待本机 `/api/health` 后显示既有 Vue 页面；用户范围 mutex/named pipe 保证第二次启动只激活原窗，
关闭窗口通过实例绑定控制帧/EOF 优雅停止确切 Linux process group，超时才强制结束该组。端口已有
listener 时明确失败，不自动复用或终止。完整决策、数据可移植性和未来 README/Release 结构见
[PLATFORM_DISTRIBUTION.md](PLATFORM_DISTRIBUTION.md)。

2026-08-28 只读盘点确认本机 WSL2/systemd/Windows 互操作和 WebView2 Runtime 可用。经用户明确
批准，微软官方 .NET SDK 10.0.400 x64 已便携安装到 `D:\Apps\dotnet`（实测 769.7 MiB），相关
CLI/NuGet 缓存固定到 D 盘，完整卸载教程保存在 SDK 根目录；没有安装 Visual Studio 或额外 workload。
WebView2 SDK 1.0.4191.47 已锁定，Windows Debug/Release 均 0 warning / 0 error。离线测试及真实
Windows -> WSL fixture 验证覆盖明确 shutdown、宿主 EOF、SIGTERM、拒绝 SIGTERM 后的精确组强杀、
端口冲突不误杀、supervisor 崩溃 parent-death 清理、WebView2 加载、单实例激活和窗口关闭释放端口。
非交互 WSL 不保证发现 `conda`，因此宿主要求安装/配置层显式提供已验证的 Conda 可执行绝对路径。

当前机器已生成约 119 MiB 的 self-contained win-x64 宿主并安装到 `D:\Apps\ResearchMate`。透明
源码向导以 `Check -> Plan -> Apply` 分离只读依赖检查、可审计 JSON 计划与显式安装，覆盖 WSL、
源码、supervisor、Conda/Python、Node/npm、Vue 构建、WebView2、.NET 构建边界及可选 Tesseract；
Apply 严格按已审查计划重检。安装器分阶段切换并回滚宿主与配置，只创建一个不含个人路径参数的
桌面快捷方式、独立 `desktop-config.json` 和当前用户卸载项；所有权清单及卸载器永不删除 WSL、
工具链、源码、工作区、资产或归档。用户已亲自确认 fixture 窗口显示并关闭后端；为遵守禁止读取
`src/data` 的边界，没有自动启动正式工作区。它仍是依赖用户自行准备 WSL checkout/工具链的
source-backed 安装，不是陌生机器的一键正式发行版；品牌图标、预编译 GitHub Release、基础依赖
官方入口整合和纯净虚拟机验收仍待后续。

## M11 之后的建议顺序

1. M5-I1/M9-I1：取得脱敏旧工作区与招聘描述样本后验证，不用合成数据伪装完成。
2. M17 候选：在行动专题内由用户明确选择有序证据并确认发送范围，生成一次新的可审计“行动简报”；结果必须逐条引用输入资料 ID，成功与失败保留历史，不覆盖用户笔记、下一步或来源事实，只有用户明确采纳后才进入独立确认层。
3. Windows + WSL 正式交付：在 M17 后基于透明源码向导补品牌图标、预编译 GitHub Release、基础依赖官方入口整合和纯净虚拟机验收，不扩张到三端全家桶。
4. M8-P1：先测首屏与路由加载，再决定是否拆包；不为消除构建警告而重构。
5. 新具名来源只在出现明确用户价值后立项，每个来源单独完成限制、provenance 和离线 fixture。

## 原生 Linux source-backed 桌面

2026-08-28 已实现第二个平台最小切片：系统 Python GTK 3/WebKitGTK 宿主显示同一 Vue/FastAPI 应用，
直接复用私有 supervisor 和确切进程组关闭契约；用户 Unix socket 保证第二次启动激活已有窗口。
透明 Python 向导检查源码、Conda/Python、后端依赖、前端 production build、GTK/WebKitGTK 和可选
Tesseract，生成 JSON 计划后才把宿主、`researchmate` 命令、`.desktop` 与配置安装到 XDG 用户目录。
临时 XDG HOME 中的计划、安装、配置校验和完整卸载往返通过，卸载不触碰系统包、工具链、源码、
环境、工作区、资产、归档或 Key。当前 WSL 已补充 WebKitGTK introspection（新增两个包约 775 KiB）
用于 WSLg/X11 fixture 验证；原生发行版的应用菜单及 Wayland/X11 差异仍需要目标机验收，不能称为
通用 Linux 正式安装包。

## 新会话交接

先看上方已完成事实与下一最小切片，不要从头重做已完成代码。开始前完整阅读 `PRODUCT.md`、`ARCHITECTURE.md` 和本文件，运行 `git status --short` 并保留全部未提交修改。禁止读取 `src/backend/config.yaml`、真实 Key 或调用真实模型/网络；自动测试只用临时工作区和假 provider。

M16 与之前的 M11–M15、M6-I1 均已完成。M5-I1/M9-I1 需要脱敏真实输入，未取得前不要伪造完成。Windows + WSL 单窗口宿主的有界技术验证和本机 source-backed 安装均已完成；不要重复原型，也不要把它误写成陌生机器的一键正式发布。下一产品切片回到 M17 的显式、可审计行动简报；开始时仍须先追踪 action project 与通用/论文 AI 审计边界，避免另造不兼容生命周期。不要重做 M11–M16 或既有浏览器闭环。
