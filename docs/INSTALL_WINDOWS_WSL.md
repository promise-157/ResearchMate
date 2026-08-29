# Windows + WSL 安装与卸载

[返回项目首页](../README.md) · [原生 Linux 安装](INSTALL_LINUX.md) · [开发与验证](DEVELOPMENT.md)

本文是 README 快速流程的完整边界说明。当前交付是 source-backed Windows + WSL 桌面版：Windows
宿主显示已有 Vue 页面并管理一次 WSL 后端生命周期，源码、Python 环境和工作区仍位于用户选择的
WSL 发行版中。它不是原生 Windows 后端。

## 配置驱动的一条命令流程

仓库提供 `researchmate-install.example.json`。复制为已被 Git 忽略的
`researchmate-install.local.json`，填写一次 WSL 发行版、源码、Conda 和安装位置后，Windows
PowerShell 可用 `-Mode Install -ConfigPath <文件> -Yes` 在一次运行中完成检查、写出并显示计划、
应用和验证。去掉 `-Yes` 会要求输入一次大写 `YES`；它不接受密码或 Key。README 提供了不换行、
可直接复制的完整命令。

## 底层三阶段模式

`packaging/windows-wsl/setup/Setup-ResearchMate.ps1` 保留三种底层模式：

- `Check`：只读检查，不写文件、不下载、不创建快捷方式。
- `Plan`：检查并写出 `researchmate-install-plan.json`，不安装。
- `Apply`：只接受已经存在且通过检查的版本 1 计划，再构建/安装。

`Install` 是上述三阶段的安全编排，不会绕过检查。底层模式保留给排障和逐阶段审查。

向导不会安装 WSL、发行版、Git、.NET、WebView2、Node、npm、Conda/Mamba/Micromamba、Python 或
Tesseract。这些可能由多个项目共享，安装位置、发行渠道、升级和卸载均由用户控制。缺失时向导给出
明确补救方向并以非零状态退出。

检查使用与桌面宿主相同的非交互 WSL/Conda 边界。某个命令只在日常交互终端中可见、但宿主无法
发现时，不算通过。Vue 不单独安装；`npm ci` 根据锁文件安装它和其他前端包。前端 `dist` 已生成后，
Node/npm 只是重建和更新依赖，不是日常启动依赖。.NET SDK 同理，只用于从源码发布 self-contained
Windows 宿主。

## 自定义位置

所有关键选择都可以在 `Check`/`Plan` 时显式传入：

```powershell
-Distro Ubuntu `
-ProjectPath /home/alice/ResearchMate `
-CondaExecutable /home/alice/miniforge3/condabin/conda `
-CondaEnvironment researchmate `
-InstallDirectory E:\Apps\ResearchMate `
-DotNetExecutable E:\Apps\dotnet\dotnet.exe
```

如果 `D:\Apps` 存在，默认 Windows 安装目录是 `D:\Apps\ResearchMate`；否则是
`%LOCALAPPDATA%\Programs\ResearchMate`。项目和环境路径必须是所选 WSL 发行版中的绝对路径。

## 安装后文件

| 内容 | 默认位置 | 卸载所有权 |
| --- | --- | --- |
| 自包含 Windows 宿主 | `D:\Apps\ResearchMate` 或用户选择 | ResearchMate 删除 |
| 桌面快捷方式 | 当前用户桌面 `ResearchMate.lnk` | ResearchMate 删除 |
| 连接配置 | `%LOCALAPPDATA%\ResearchMate\desktop-config.json` | ResearchMate 删除 |
| 卸载注册项 | 当前用户 Installed Apps | ResearchMate 删除 |
| 日志/WebView 状态 | `%LOCALAPPDATA%\ResearchMate` | 仅明确选择时删除 |
| 自定义快捷方式图标 | `%LOCALAPPDATA%\ResearchMate\shortcut-icon.ico` | 彻底清理本地状态时删除 |
| WSL、发行版、工具链和源码 | 用户选择 | 永不删除 |
| 工作区、资产、归档和 Key | 用户数据边界 | 永不删除 |

安装目录中的 `installation-manifest.json` 是实际安装清单，`uninstall-guide-zh-CN.txt` 是离线中文
卸载说明。配置不含 AI Key 或工作区内容，快捷方式不含个人 WSL 参数。

## 快捷方式图标

默认品牌 ICO 在 `assets/branding/researchmate.ico`，构建时嵌入 Windows 宿主。Windows 桌面宿主内
的设置页通过受限 WebView 消息打开系统文件选择器；宿主只接受最大 5 MiB、具有 ICO 文件头的
`.ico`，复制为 `%LOCALAPPDATA%\ResearchMate\shortcut-icon.ico` 后更新自身拥有的桌面快捷方式。
普通浏览器没有此能力。恢复默认会让快捷方式重新使用宿主 EXE 的嵌入图标并删除自定义副本；常规
重新安装保留自定义副本，完整清理本地状态时才删除。

运行后可在 `设置 -> 安装与卸载` 查看当前机器的真实宿主、LocalAppData、快捷方式、WSL 源码、
前端构建、用户数据边界和卸载文档路径；这里显示的是宿主传入的当前值，不是文档示例。

## 重新配置和更新

仓库移动、发行版或环境变化时重新运行 `Check` 和 `Plan`，检查 JSON 差异后再 `Apply`。安装器使用
临时 staging 和 previous 目录切换；失败时恢复旧安装和旧配置。成功后清理临时目录。

更新源码前应先阅读版本说明。ResearchMate 不会替用户执行 `git pull`、升级基础工具或在未确认时
修改 Python/Node 依赖。

宿主更新后必须重新执行配置驱动的 `Install` 命令（内部仍执行 Check、Plan、Apply）；只拉取 WSL
源码不会替换 Windows 安装目录中的 EXE。
当前宿主在旧实例退出期间会重试激活并接管刚释放的单实例 mutex，关闭窗口后可再次双击启动。

## 卸载

先关闭 ResearchMate，再从 Windows“设置 -> 应用 -> 已安装的应用”运行当前用户卸载项，或执行安装
目录中的 `Uninstall-ResearchMate.ps1`。默认删除 Windows 宿主、快捷方式、卸载项和连接配置，保留
日志/WebView 状态；传入 `-RemoveLocalState` 才删除整个 Windows 本地状态目录。

卸载器不运行 `wsl --unregister`、`wsl --shutdown`、Conda 删除、Git 删除或工作区清理。WSL、Linux
发行版、环境管理器、Python 环境、Node、.NET SDK、Tesseract、源码、资料、资产和归档均由用户自行
管理。
