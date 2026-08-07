# AI 全链路与迁移边界

本文记录 M10 开始时实际存在的 AI 路径。它描述当前代码，不把 M11 的统一工作误记为已完成。

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

## 论文、工作区综述和聊天（兼容路径，待 M11 迁移）

| 功能 | UI -> API | 当前 provider | 当前持久化 | 与通用主路径的差异 |
| --- | --- | --- | --- | --- |
| 购物车论文分析 | `CartDrawer.vue -> /api/cart/analyze*` | `LLMAnalyzer -> ai_provider`（DeepSeek/兼容接口） | 直接更新 `papers.ai_*` | 无独立运行记录、用量或失败历史 |
| 工作区综述 | 论文页操作 -> `/api/workspace/review` | `LLMAnalyzer -> ai_provider` | `workspace_reviews.ai_review` | 只保存成功结果，输入范围/失败审计不完整 |
| 论文聊天 | `ChatPanel.vue -> /api/chat` | `LLMAnalyzer -> ai_provider` | 消息只在浏览器内 | 最多附加 12 篇论文且摘要截断，但无持久会话/运行审计 |

M10 让这些兼容路径在选择 DeepSeek 时复用同一个安全的 OpenAI-compatible HTTP 契约、JSON Output（结构化论文任务）和脱敏错误底座，但没有改变其旧存储语义。M11 才负责把它们迁移到统一 service/provider/audit 边界，并保证聊天只读取明确附加的资料。

论文聊天调用的是设置中的远程或本地模型，但当前没有实时网页搜索工具。模型只收到用户消息和明确附加的论文元数据；界面会直接展示该边界。现阶段不把任意网页访问交给聊天模型：需要网络资料时继续使用具名 arXiv 发现或“导入公开 URL”，先保存来源、经过候选审核，再由用户明确选择是否交给 AI。若以后出现必须在对话中检索的真实用例，应新增具名搜索适配器、域名/数量/超时限制、引用和运行审计，而不是给予模型无边界浏览权限。

## M10 离线验收与真实验收

离线验收覆盖：请求形状、JSON Output、响应元数据、401/402/模型不存在/429/超时/5xx/解析/空响应/截断映射、结构校验、迁移、API 错误以及浏览器中的单条失败/成功、刷新、20 条比较和工作区隔离。

真实 DeepSeek 烟测已在用户明确授权后完成：独立测试工作区中的两条无敏感 fixture 分别完成分类、结构化提取和比较，共三次受控请求；返回模型、用量、耗时和请求标识均成功持久化，刷新读取正常。验收未读取或输出 Key，真实调用不加入 CI；响应形状与现有脱敏 fixture 一致，未发现额外服务商差异。
