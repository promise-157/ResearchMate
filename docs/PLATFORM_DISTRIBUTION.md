# ResearchMate 多平台交付设计

本文记录 ResearchMate 的桌面启动、安装与多平台发布方向。它是按需读取的交付设计，不替代
`PRODUCT.md`、`ARCHITECTURE.md` 或 `ROADMAP.md`。当前内容是已确认的方向与分阶段验收条件，
不表示相应安装包已经完成。

## 目标与边界

ResearchMate 保持一个仓库、一个主干和一套产品核心，逐步提供三个独立交付目标：

1. Windows + WSL：Windows 桌面宿主管理 WSL 中的共享 Linux 后端。
2. 原生 Linux：共享 Python 后端、Vue 前端和 Linux 桌面入口。
3. 原生 Windows：Windows 桌面宿主管理 Windows 原生后端。

三个目标共享 API、service、repository、SQLite schema/migration、Vue UI、AI 审计、安全边界、
工作区归档和测试契约。平台差异只包含安装、数据目录、进程生命周期、桌面窗口、系统集成、
OCR 可执行文件发现及少量文件系统行为。

本方向明确不做：

- 不维护 `windows`、`linux`、`wsl` 三条长期 Git 分支。
- 不复制三份后端、前端或数据库迁移。
- 不提供一次安装全部平台依赖的“全家桶”。
- 不把活动 SQLite/WAL 放入同步盘供多端并发写入。
- 不把跨平台安装误称为多设备同步；真正的同步需要独立设计变更日志、冲突和安全协议。
- 不因桌面化放宽本地监听、Key、外部 AI、来源访问或用户确认边界。

功能开发可使用短期 feature branch，验证后合并回同一主干。平台不是不同产品版本。

## 推荐代码与交付边界

平台目录保存适配和发布材料，不复制业务代码。目录按真实用例逐步创建，不预建空框架：

```text
src/
  backend/
    platform/                 # 出现真实差异后收口运行时适配
packaging/
  windows-wsl/                # Windows 宿主、WSL 启动适配、安装器
  windows-native/             # 原生 Windows 后端适配与安装器
  linux/                      # desktop/service/安装器
  common/                     # 第二个真实使用方出现后才提取的构建共享物
docs/install/
  WINDOWS_WSL.md
  WINDOWS_NATIVE.md
  LINUX.md
  DEVELOPMENT.md
```

`src/backend/platform/` 只允许承载真实的平台差异，例如：

- data/config/cache/log 目录解析；
- 单实例、进程启动、健康检查、优雅停止和异常清理；
- Windows process event 与 Unix signal 差异；
- Tesseract 程序和语言包发现；
- 文件权限、系统通知和打开桌面窗口。

ActionProjects、M17 行动简报、AI 审计、导入规则、工作区隔离、SQLite schema 和 API 模型不得
按平台复制或分叉。共享代码中也不应散布大量操作系统判断；第二个真实适配器出现后，再从
已验证实现中提取最小接口。

## 安装依赖与发布物

单仓库不等于用户安装全部依赖。每个平台单独构建、下载和安装：

| 用户环境 | 发布物 | 不应安装的内容 |
| --- | --- | --- |
| Windows，使用 WSL | `ResearchMate-WSL-...` | Windows 原生 Python 后端、Linux 桌面组件 |
| Windows，不使用 WSL | `ResearchMate-Windows-...` | WSL、Linux 桌面组件 |
| Linux | Linux 安装包或便携包 | WebView2、Windows 组件 |

Vue 源码只维护一份。Node.js 属于开发/发布构建依赖；正式发布应携带预构建静态文件，普通用户
不应为了运行安装 Node.js。Python/OCR 等运行依赖按目标平台打包或在对应安装文档中声明，不能
因仓库支持多个平台就由单个平台安装器全部安装。

只有出现真实依赖差异后才拆分 `base`、`windows`、`linux`、`development` 依赖集合。构建与测试
也按共享验证和各平台发布任务分开，某个平台任务只准备自身工具链。

## 首个切片：Windows + WSL 桌面宿主

首个交付切片不是完整跨平台安装包，而是 Windows + WSL 桌面宿主的最小技术验证和随后加固。
目标体验类似桌面上位机，但完整复用现有 Vue 页面：

```text
双击一个 ResearchMate 图标
  -> Windows 宿主启动 WSL 内 ResearchMate 后端
  -> 等待 /api/health
  -> 单个 WebView2 窗口显示现有页面
  -> 关闭窗口
  -> 优雅停止本次宿主拥有的后端
```

优先评估 C# + WebView2。它使用 Windows 浏览器内核，不需要用 Qt 重写 UI，也避免 Electron 自带
Chromium 的体积。Qt/PySide、Tauri 或其他壳只有在真实发布约束证明更合适时再选择。

### 技术原型结果（2026-08-28）

最小技术原型已经完成，代码位于 `packaging/windows-wsl/`，WSL supervisor 位于
`src/backend/desktop_runtime.py`。原型锁定 .NET 10 与 `Microsoft.Web.WebView2` 1.0.4191.47，
WinForms 只引用 Core/WinForms 资产，不引入冲突的 WPF 程序集；Debug 与 Release 构建均为零警告。

已用离线 fixture 在真实 Windows + WSL 上验证：

- WebView2 加载本机健康页面，窗口关闭后假后端收到 SIGTERM 且端口释放。
- 同配置第二实例通过用户 mutex/named pipe 激活原窗口并退出，不启动第二后端。
- 明确 shutdown 控制帧和宿主 stdin EOF 都能透传到 supervisor。
- 后端拒绝 SIGTERM 时只对已验证 process group 执行有界 SIGKILL。
- 第二 supervisor 遇到已有 listener 时失败，原 listener 继续健康且不被终止。
- supervisor 被 SIGKILL 后，正常后端通过 Linux parent-death signal 退出。
- 非交互 WSL 不加载日常终端的 Conda PATH；最终契约改为显式传入经验证的 Conda 可执行绝对路径，
  不硬编码用户目录。

测试未导入 `config.py`、未读取 `src/data`，没有真实 AI、真实来源、真实 Key 或用户工作区。Debug-only
fixture/自动关闭参数不会进入 Release 参数解析。

随后已完成当前机器的 source-backed 交付：生成约 119 MiB 的 self-contained win-x64 宿主，安装到
`D:\Apps\ResearchMate`，创建唯一桌面快捷方式与当前用户卸载项，并提供分阶段替换、失败回滚和
保留 WSL/Conda/源码/工作区的彻底卸载说明。安装前会校验发行版、项目、supervisor、Conda 可执行
文件和环境。随后加入透明的 `Check -> Plan -> Apply` 源码配置向导：按桌面宿主真实的非交互边界
检查 Windows/WSL/Conda/Python/Node/Vue/WebView2/.NET 及可选 Tesseract，生成包含全部写入和外部
所有权的 JSON 计划，应用时严格重检该计划；快捷方式不再携带个人参数。它仍不是面向陌生机器的
独立正式发布：品牌图标、预编译 GitHub Release、基础依赖官方入口整合及纯净虚拟机验收尚未完成；
为遵守数据边界，本次自动验证没有启动生产后端或读取 `src/data`。

### 当前环境盘点（2026-08-28）

本机只读盘点已确认：

- 当前是 WSL2，发行版名为 `Ubuntu20.04`，WSL 包版本为 2.7.3.0。
- `/etc/wsl.conf` 已启用 systemd、Windows 互操作和 Windows PATH 追加；系统 systemd 为 running。
- 用户 systemd 的 degraded 只来自既有 PulseAudio service/socket，与 ResearchMate 生命周期无关。
- WSL 可以定位 Windows PowerShell 5.1。
- Windows 已安装 WebView2 Evergreen Runtime 149.0.4022.80，可以运行 WebView2 桌面窗口。
- 初次盘点时 Windows 没有可发现的 `dotnet` SDK/runtime、`csc`、MSBuild 或 Visual Studio Build
  Tools，Linux 侧也没有可发现的 `dotnet`。
- 经用户明确批准，现已使用微软官方 `dotnet-install.ps1` 把单一 Windows x64 .NET SDK 10.0.400
  便携安装到 `D:\Apps\dotnet`；实测 SDK 占用 769.7 MiB，没有安装完整 Visual Studio 或其他
  workload。
- 当前用户的 `DOTNET_ROOT`/Path 指向该 SDK，`DOTNET_CLI_HOME`、`NUGET_PACKAGES` 和
  `NUGET_HTTP_CACHE_PATH` 分别指向 D 盘的受控目录；缓存初始为空。
- 官方安装脚本保留在 `D:\installpacakage\ResearchMate`，完整卸载步骤保存在
  `D:\Apps\dotnet\彻底卸载干净教程.txt`。

因此本机已经具备 .NET CLI 与 WebView2 Runtime。WebView2 managed SDK 等项目级编译包仍须在原型
项目中锁定版本并按用户已授权的交付切片受控还原；不能自动扩张到 Visual Studio 或额外 workload。
普通最终用户不应为了运行安装 SDK。

systemd 可用于未来 Linux 服务或故障诊断，但桌面模式不能把常驻 user service 当作默认所有者：
窗口关闭或宿主崩溃时，服务可能继续存活，不符合“关闭窗口即全部关闭”的产品契约。

### 已选生命周期结构

首个原型采用宿主拥有的私有进程树，而不是公开的 HTTP shutdown API：

```text
Windows ResearchMate host
  |-- Windows user mutex + activation channel
  `-- redirected stdin/stdout -> wsl.exe
        `-- WSL runtime supervisor
              `-- dedicated process group -> production ResearchMate backend
```

Windows 宿主通过 `wsl.exe -d <configured distro> --cd <validated project dir>` 进入 WSL。发行版和项目
目录属于安装期/首次启动配置，不能在共享业务代码中硬编码。WSL bootstrap 在 `researchmate` 环境中
启动 supervisor；具体 Conda 调用和标准输入透传必须由技术原型验证，不能只假设 `conda run` 会正确
转发 EOF 和 signal。

supervisor 是桌面模式唯一的后端进程所有者：

- 在启动后端前验证目标端口可绑定；端口已有服务时报告冲突，不连接、复用或终止未知实例。
- 为后端创建独立 Linux process group，以覆盖启动期间的前端构建子进程和正式 Uvicorn 进程。
- 控制命令只通过宿主拥有的 stdin 管道接收；状态事件通过单独的受控输出协议返回。
- 后端日志与控制协议分离，日志不得包含 Key、请求正文或未经脱敏的 provider 响应。
- WebView 只加载 `http://127.0.0.1:<port>`；健康检查成功且对应子进程仍存活后才显示正常页面。
- 不新增无鉴权 `/api/shutdown`，普通网页不能停止本机后端。

### 单实例与身份

- Windows 宿主使用当前 Windows 用户范围的 mutex；标识由产品、WSL 发行版和安装实例派生。
- 第二次启动通过用户范围 activation channel 唤醒既有窗口，然后立即退出。
- mutex 只解决桌面宿主重复启动，不证明 8000 端口上的进程属于 ResearchMate。
- 每次启动生成内存中的随机 instance ID，宿主与 supervisor 通过私有管道核对；不得写入 SQLite、
  日志或前端 storage。
- 如果 mutex 不存在但端口已占用，显示端口冲突及安全排错方式；不能调用现有 `--kill` 自动清理。

### 正常关闭协议

1. 用户关闭唯一桌面窗口，宿主立即禁止新页面交互并显示“正在安全退出”。
2. 宿主向 supervisor stdin 写入带当前 instance ID 的 `shutdown` 控制帧。
3. supervisor 向自己创建的后端 process group 发送 SIGTERM。
4. Uvicorn 停止接收请求并进行优雅关闭；现有请求固定工作区连接及 SQLite 事务按正常路径结束。
5. supervisor 等待后端退出、返回退出事件，然后自己退出；宿主等待 `wsl.exe` 子进程退出后关闭窗口。
6. 达到有界超时仍未退出时，UI 明示将强制结束，并只向已验证的本次 process group 发送 SIGKILL。
7. 强制结束留下的持久 `running` 记录在下一次启动时由现有统一恢复逻辑转为脱敏失败。

首个原型需要用假长请求测定合理超时。在取得证据前不把具体秒数写成产品常量，也不能无限等待导致
窗口永远无法退出。

### 异常关闭协议

- Windows 宿主正常退出、崩溃或被任务管理器结束都会关闭它拥有的管道；supervisor 将 EOF 视为
  shutdown，并执行与正常关闭相同的 SIGTERM/有界强制结束流程。
- 技术原型必须在真实 WSL 上证明 Windows 进程异常结束确实会把 EOF 传到 supervisor；若不能可靠
  证明，再增加仅存在于私有进程通道的心跳，不能退化成公开 HTTP 控制端点。
- supervisor 自身异常时，宿主显示明确失败；原型必须验证其 Linux process group 是否会遗留后端，
  并据结果增加 parent-death/心跳清理，而不是假设父进程退出会自动杀死子进程。
- 后端启动前退出、健康检查超时或运行中退出都会切换到本机错误页；不能继续显示陈旧 WebView 成功页。
- Windows 关机/注销属于异常退出路径；SQLite 依赖事务/WAL 保持一致，审计运行依赖下次启动恢复。

### 与现有后端的衔接事实

当前生产 `src/backend/run.py` 在前端准备和数据库初始化后，以 `reload=False` 在同一 Python 进程调用
`uvicorn.run()`；生产模式没有常驻 Vite 子进程。Uvicorn 接收 SIGTERM 后可走正常关闭，`finally` 仍
保留已有 Vite 清理兼容。桌面 supervisor 不应复制 API/server 初始化逻辑，而应启动这个生产入口或
从它提取第二个真实调用方需要的最小可测试入口。

应用启动会遍历合法工作区并恢复遗留的 `collection_jobs`、`chat_turns`、`extraction_runs` 和
`paper_ai_runs` running 状态，成功/失败终态不变且恢复幂等。因此桌面关闭不应逐表修改审计记录；
正常完成由原 workflow 写终态，真正被强制中断的记录由下次启动统一恢复。

### 生命周期契约

- 桌面只有一个正常入口，不要求用户另点“停止”快捷方式。
- 双击只出现一个 ResearchMate 窗口；不额外打开终端或外部浏览器。
- 重复启动激活既有窗口，不能创建第二个后端。
- 宿主只管理它拥有并验证过的 ResearchMate 实例，不能按端口误杀其他程序。
- 关闭窗口先停止接受新交互，再请求后端优雅结束并等待 SQLite 事务/连接关闭。
- 超时后的强制结束仍只能针对本次已验证实例。
- 不用 `wsl --shutdown` 或日常使用 `wsl --terminate`，避免关闭用户的其他 WSL 任务。
- 后端或环境启动失败时显示持久、可理解的诊断，窗口不能一闪而过。
- 宿主异常、任务管理器结束或 Windows 关机需要有孤儿进程处理策略；下一次启动继续依赖现有
  持久运行中断恢复，不能把未完成 AI/采集伪装成成功。
- 仍只监听本机地址；控制停止能力不能成为任意网页可调用的无鉴权公共接口。
- 原有 Linux/WSL `python run.py` 方式保持可用。

### 首个切片验收条件

- 在真实 Windows + WSL 环境从单一桌面图标完成冷启动。
- `/api/health` 成功后才展示正常应用，启动失败有明确原因。
- 单实例、重复点击、正常关闭、启动失败、后端异常和再次启动均有验证。
- 点击窗口关闭后，确切的本次 ResearchMate 后端退出，其他 WSL 进程保持运行。
- 工作区、图片资产和既有终态不受启动/关闭影响；持久 `running` 记录按现有规则恢复。
- 不读取真实 Key，不调用真实 AI 或真实网络；自动测试只使用临时目录和假依赖。
- 安装、卸载、启动、停止、日志与排错边界有文档。
- 真实验证 `conda run`/bootstrap 的 stdin、EOF 和 signal 透传，不能只依赖模拟测试。
- 真实验证宿主崩溃、supervisor 崩溃和长请求退出，不留下无法识别的孤儿后端。

该技术验证已经通过，下一产品切片回到 ROADMAP 的 M17；不要在一个切片内同时实现三个平台安装器。

## 后续平台演进

推荐顺序：

1. Windows + WSL 最小宿主及生命周期验证。
2. 回到并完成 M17 首个行动简报纵向切片。
3. 将运行数据、配置、缓存和日志从源码布局抽象到稳定用户目录，同时保持现有数据迁移安全。
4. 增加 Linux 桌面入口；此时出现第二个真实用例，再提取共享 runtime 接口。
5. 增加 Windows 原生后端适配，尽量复用 Windows 桌面宿主。
6. 建立共享测试加 Windows/Linux 平台构建矩阵。
7. 有真实需求后再单独评估浏览器保存、剪贴板快速导入、文件“发送到 ResearchMate”、托盘和
   本机通知；这些入口仍须走候选审核、显式范围和安全限制。

不要等待三端全部写完再拆复制代码。第一个实现保持具体，第二个真实平台出现时提取已经证明
共享的最小边界，第三个平台继续复用和校正。

## 数据可移植性

所有平台必须使用同一 schema 版本和幂等迁移。SQLite 内不得依赖旧机器绝对资产路径；工作区
ZIP 继续作为跨机器、跨平台移动的受控边界。导入时验证 manifest、数据库和资产，并在目标平台
重建隔离目录及 `storage_path`。编码、时间、ZIP 成员路径、大小写、Windows 保留名称和路径长度
需要平台测试。

在实现真正同步前，只支持通过完整归档显式导出/导入。不得建议用户让 OneDrive、Dropbox、NAS
或 Windows/Linux 共享目录同时同步并打开活动 SQLite、WAL 和资产目录。

## GitHub README 与 Release 契约

第一个平台入口经过验证后，README 首页应先帮助普通用户选择版本，再介绍源码开发：

1. 一句话产品说明与真实截图。
2. “选择你的版本”表：Windows + WSL、Windows 原生、Linux、源码开发。
3. 每个平台的最短安装/启动入口，并链接独立安装文档。
4. 数据目录、隐私、AI 显式发送、Key 保存和完整归档说明。
5. 已完成的核心功能。
6. 最后才是开发环境、Node/Python/Conda 和验证命令。

未完成的平台必须标记“计划中”或“当前仅支持源码运行”，不能写成已支持。一个 GitHub Release
可以包含相同版本的多个独立资产，用户只下载自己的平台包；源码仓库包含其他平台文本不会让
安装器引入那些依赖。

建议的发布资产形式仅是目标，不是当前承诺：

```text
ResearchMate-WSL-x64-...
ResearchMate-Windows-x64-...
ResearchMate-Linux-x86_64-...
Source code
```

具体安装包格式必须经过目标平台技术验证后确定，不能提前用文件名宣称支持。
