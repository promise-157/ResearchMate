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

最新已验证基线（M11 完整纵向切片及工作区稳定性加固，2026-08-12）：在排除真实配置与数据的临时副本中后端 103 项、`compileall`、Ruff 通过；前端 lint、生产构建、Playwright 8 项和 `git diff --check` 通过。测试只使用假 provider 与本地拦截 fixture，没有调用真实模型或真实网络。生产构建仍有 M8-P1 的大 chunk 和第三方 PURE 注释提示。

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

M11 判定完成。下一最小切片为 M12 的完整图片解码与 OCR/资产完整性验证，范围以 M3-I1 为准。

## 仍有效的跨里程碑债务

| ID | 后续处理 |
| --- | --- |
| M3-I1 | 用完整 PNG/JPEG/WebP 与本机中英文 Tesseract 验证；增加完整解码、像素和解压炸弹防护。 |
| M3-I2 | 测试删除/清空工作区后的资产隔离清理；定义包含 DB 与资产的可移植归档。 |
| M4-I1 | 用户授权后验证公网 DNS/TLS/robots/重定向/字符集；补 URL 浏览器流程。 |
| M5-I1 | 在真实旧工作区副本验证论文/资料映射；来源刷新需要显式差异预览与接受。 |
| M6-I1 | 补 Debug 浏览器流程；真实样本证明需要后再扩展规则或本地语义检索。 |
| M7-I1 | 用户授权后验证真实 arXiv；补浏览器流程和采集任务中断恢复。聊天与论文 AI 的中断恢复已完成。 |
| M8-P1 | 前端主 chunk 仍超过 500 kB；需以首屏收益为依据做路由/组件拆分。 |
| M9-I1 | 用脱敏招聘描述验证字段覆盖；自由叙述、薪资和年限规范化需真实需求驱动。 |

## M11 之后的建议顺序

1. M12：OCR 质量、完整图片解码和资产完整性。
2. M13：受控真实公开网络与剩余浏览器验收。
3. M14：可移植工作区、显式重新处理和中断任务恢复。
4. M15：以真实数据评估 SQLite FTS，再考虑可选本地 embedding。
5. 新具名来源只在出现明确用户价值后立项，每个来源单独完成限制、provenance 和离线 fixture。

## 新会话交接

先看上方已完成事实与下一最小切片，不要从头重做已完成代码。开始前完整阅读 `PRODUCT.md`、`ARCHITECTURE.md` 和本文件，运行 `git status --short` 并保留全部未提交修改。禁止读取 `src/backend/config.yaml`、真实 Key 或调用真实模型/网络；自动测试只用临时工作区和假 provider。

M11 已完成；新会话从 M12 的 M3-I1 最小纵向切片开始，不再重做聊天、购物车分析、工作区综述或稳定性加固。
