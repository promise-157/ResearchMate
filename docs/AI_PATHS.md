# AI 全链路与迁移边界

本文记录当前实际存在的 AI 路径。M11 已完成论文聊天、购物车论文分析和工作区综述迁移。

## 通用资料（当前可审计主路径）

```text
Materials.vue
  -> /api/items/{id}/analysis-runs 或 /api/items/analysis-comparisons
  -> services/material_analysis.py
  -> processors/material_ai.py
  -> processors/ai_provider.py
  -> workspace SQLite extraction_runs
```

用户必须先选择分析类型、资料清单和字段范围。service 在后端读取这些字段并执行单条 12,000 字符、比较每条 3,000 字符的边界，创建 `running` 记录后才调用 provider。DeepSeek 结构化任务使用 OpenAI-compatible `POST /chat/completions` 和 `response_format={"type":"json_object"}`，结果仍须通过本地 Pydantic schema；空内容、截断、非法 JSON 或 schema 不符均写为失败。

成功运行保存配置服务商/模型、服务商返回模型、输入/输出 token、耗时、可用请求 ID、输入哈希、资料 ID、字段范围、处理器/提示词版本和建议结果。失败只保存稳定的脱敏错误，不保存完整输入、原始模型响应或 Key。AI 建议不会改写来源事实、本地提取或用户确认值。

## 设置页连接测试

```text
AIConfig.vue -> POST /api/settings/ai/test
  -> services/ai_settings.py -> processors/ai_provider.py
```

页面不会自动探测。用户点击后会先看到“一次外部请求、可能产生少量费用、不会发送工作区资料”的确认，再由后端发送固定的最小测试提示。DeepSeek 连接测试显式关闭思考并提供 64 token 的有界输出额度，避免默认思考占满过小额度而把已连通误报为截断；其他兼容服务商不会收到 DeepSeek 私有参数。返回只包含服务商、配置/返回模型、token、耗时和请求 ID，不返回生成正文或 Key。普通自动测试注入内存 HTTP fixture，不访问服务商。

设置页 Key 默认只保留在进程内；用户明确切换便利模式后才写入已忽略的 `src/backend/config.yaml`。该模式在 UI 显示明文风险和绝对路径，后端以 `0600` 原子写入；切回安全模式或清除会移除磁盘副本。设置 API 只返回 `has_key`、来源和保存模式，不回传 Key。

## 论文聊天（M11 已迁移第一纵向切片）

```text
ChatPanel.vue -> src/frontend/src/api/index.js
  -> /api/chat/sessions/{id}/turns
  -> services/chat_service.py
  -> processors/ai_provider.py
  -> workspace SQLite chat_sessions/chat_turns
```

会话与轮次属于当前工作区。每轮在外部调用前写为 `running`，保存用户消息、本轮明确附加的论文 ID、实际历史轮次 ID、输入范围、provider、配置模型和提示词版本；成功补充回复、服务商返回模型、token、耗时和请求标识，失败写入脱敏错误。UI 可新建/选择会话，刷新和切换工作区后从 API 恢复，不再依赖浏览器数组制造“聊天历史”。

本轮最多附加 12 篇论文，每篇只读取标题、作者、来源、URL 和最多 1,200 字符摘要；未附加时不会读取任何论文或工作区正文。多轮上下文只选最近最多 10 个成功轮次，用户/助手历史合计限制 12,000 字符，并记录实际轮次 ID。聊天系统提示明确模型无实时网页访问，并把论文元数据视为不可信证据而非指令。

## 购物车论文分析（M11 已迁移第二纵向切片）

```text
CartDrawer.vue -> src/frontend/src/api/index.js
  -> /api/cart/analyze 或 /api/cart/analyze/all
  -> services/paper_analysis.py
  -> processors/paper_ai.py -> processors/ai_provider.py
  -> storage/paper_ai_runs.py -> workspace SQLite paper_ai_runs
```

请求只接受当前工作区购物车中的 1–20 篇论文；单篇和批量走同一 service。批量按论文逐次执行，每篇调用前先建立独立 `running` 记录，只读取并发送最多 300 字符标题和 3,000 字符摘要。运行保存论文 ID、`["title", "abstract"]` 输入范围、输入哈希、处理器及版本、提示词版本、provider 和配置模型。成功响应须通过严格本地结构校验，随后保存 AI 对代码线索、创新点和技术关键词的建议，以及返回模型、token、耗时和可用请求 ID；失败只保存脱敏错误。

`GET /api/cart` 会把当前工作区每篇购物车论文最近的运行历史一并返回，界面因此可在冷启动、刷新和工作区切换后恢复隔离的逐篇结果。批量响应明确区分 `succeeded`、`partial` 和 `failed`，一个成功结果不会把部分失败冒充为整批成功。

新运行只写 `paper_ai_runs`，不会更新 `papers` 的任何字段，包括来源事实 `title/abstract/authors/paper_url/has_code/code_url`，也不会更新旧 `ai_innovation/ai_technologies/ai_code_url/ai_analyzed/cart_ai_analyzed`。购物车仍把这些旧字段明确标为“旧兼容结果（只读）”；它们不代表统一审计运行。

`paper_ai_runs` 是独立于 `chat_sessions/chat_turns` 和 `extraction_runs` 的 schema v10 表。购物车分析和工作区综述两个真实用例以不同 `run_kind` 复用其通用运行元数据，不合并三种生命周期不同的运行模型。

`paper_ai_runs` repository 已按 `run_kind` 提供通用历史查询，并只允许 `running` 记录完成一次。应用启动会把上次进程退出遗留的论文 AI 与聊天 `running` 记录转成可见的脱敏失败；在途请求的 SQLite 连接固定到开始时的工作区，切换不会把结果写进新工作区。购物车批量当前仍是最多 20 篇的有界同步逐篇调用，前端超时按数量对齐；若真实使用证明需要后台执行，再以批次 ID 和可轮询状态完成独立纵向切片，不用浏览器状态伪造后台任务。

## 工作区综述（M11 已迁移第三纵向切片）

```text
WorkspaceReviewPanel.vue -> src/frontend/src/api/index.js
  -> /api/workspace/reviews
  -> services/workspace_review.py
  -> processors/workspace_review.py -> processors/ai_provider.py
  -> storage/paper_ai_runs.py -> workspace SQLite paper_ai_runs
```

用户从当前论文页明确选择当前工作区的 2–20 篇不重复论文。调用按钮只有在界面展示有序论文 ID、发送字段及边界，并由用户勾选确认后才可用；每篇只发送最多 300 字符标题和 2,000 字符摘要，不发送作者、来源链接、关键词或全文。service 在 provider 调用前一次性验证全部 ID 归属，任一无效时不创建运行也不调用 provider。

一次请求先建立一条 `paper_ai_runs/run_kind=workspace_review` 的 `running` 记录，保存有序 ID、`title:300/abstract:2000` 范围、输入哈希、处理器/提示词版本、provider 与配置模型。成功结果必须通过本地 schema，推荐项只能引用输入 ID；随后保存热门方向、推荐理由、技术趋势以及返回模型、token、耗时和请求 ID。失败只保存脱敏错误。新综述不写 `papers` 或 `workspace_reviews`。

GET 历史只从当前工作区读取，刷新和切换后可恢复。`PaperAIRunHistory.vue` 是购物车分析与工作区综述出现两个真实审计展示用例后提取的共享组件；负责状态、范围、论文 ID、提示词、模型、用量、请求 ID、结果和错误的共同展示。旧 `workspace_reviews` 通过 repository 单独返回，并明确标为缺少完整范围/模型元数据的“迁移前综述（只读兼容）”。旧 `/api/workspace/review` 写入 route 和未使用的前端 helper 已移除；`LLMAnalyzer.review_with_prompt` 不再有现役调用路径。

论文聊天调用的是设置中的远程或本地模型，但当前没有实时网页搜索工具。模型只收到有界历史、用户消息和明确附加的论文元数据；界面会直接展示该边界。现阶段不把任意网页访问交给聊天模型：需要网络资料时继续使用具名 arXiv 发现或“导入公开 URL”，先保存来源、经过候选审核，再由用户明确选择是否交给 AI。若以后出现必须在对话中检索的真实用例，应新增具名搜索适配器、域名/数量/超时限制、引用和运行审计，而不是给予模型无边界浏览权限。

## M10 离线验收与真实验收

离线验收覆盖：请求形状、JSON Output、响应元数据、401/402/模型不存在/429/超时/5xx/解析/空响应/截断映射、结构校验、迁移、API 错误以及浏览器中的单条失败/成功、刷新、20 条比较和工作区隔离。

真实 DeepSeek 烟测已在用户明确授权后完成：独立测试工作区中的两条无敏感 fixture 分别完成分类、结构化提取和比较，共三次受控请求；返回模型、用量、耗时和请求标识均成功持久化，刷新读取正常。验收未读取或输出 Key，真实调用不加入 CI；响应形状与现有脱敏 fixture 一致，未发现额外服务商差异。
