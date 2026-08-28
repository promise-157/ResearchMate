# ResearchMate

ResearchMate 是本地优先的个人资料工作空间：导入文字、图片、公开网页和公共来源候选，完成审核、
提取、组织、关联与行动；只有用户明确确认范围后才把有界内容发送给外部 AI。

当前支持普通资料、论文、Debug 记录和求职资料模板，包括本地 OCR、字段提取、搜索筛选、论文工作流、
可审计 AI 分析、行动专题以及完整工作区归档。来源事实、AI 建议和用户确认分别保存，重新处理不会
覆盖用户确认。项目不默认下载论文 PDF、镜像网站，或绕过登录、付费墙、CAPTCHA、robots 和限流。

## 选择运行方式

| 环境 | 状态 | 安装文档 |
| --- | --- | --- |
| Windows + WSL 2 桌面窗口 | source-backed 安装可用 | [Windows + WSL 安装](docs/INSTALL_WINDOWS_WSL.md) |
| 原生 Linux 桌面窗口 | source-backed 安装可用 | [原生 Linux 安装](docs/INSTALL_LINUX.md) |
| WSL/Linux 浏览器模式 | 可用 | [快速上手](docs/QUICKSTART.md) |
| 原生 Windows 后端 | 尚未发布 | 不会伪装为当前 WSL 版本 |

两种桌面安装都采用 `Check → Plan → Apply`：先只读检查环境，再生成可审查的 JSON 计划，最后才写入
用户目录。ResearchMate 不自动安装或卸载 WSL、Linux 发行版、Git、.NET、Node、Conda、Python、
GTK/WebKitGTK 或 Tesseract；完整依赖、安装位置、磁盘占用和卸载边界均在对应平台文档中列出。

## Windows + WSL 最短入口

完成 [Windows + WSL 前置环境和源码准备](docs/INSTALL_WINDOWS_WSL.md) 后，在仓库根目录的 WSL
终端运行：

```bash
setup_win="$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$setup_win" -Mode Check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$setup_win" -Mode Plan
# 审查 researchmate-install-plan.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$setup_win" -Mode Apply
```

安装后双击 Windows 桌面的 `ResearchMate`。快捷方式不保存个人 WSL 路径；关闭唯一窗口会停止它
启动的后端，不会关闭整个 WSL。配置、更新、排错与彻底卸载见
[Windows + WSL 安装说明](docs/INSTALL_WINDOWS_WSL.md)。

## 原生 Linux 最短入口

完成 [Linux 图形依赖和源码准备](docs/INSTALL_LINUX.md) 后运行：

```bash
python3 packaging/linux/setup_researchmate.py --mode check \
  --conda /absolute/path/to/conda
python3 packaging/linux/setup_researchmate.py --mode plan \
  --conda /absolute/path/to/conda
# 审查 researchmate-linux-install-plan.json
python3 packaging/linux/setup_researchmate.py --mode apply
researchmate
```

也可以从 Linux 应用菜单打开 ResearchMate。关闭 GTK/WebKitGTK 窗口会停止它拥有的后端，重复启动
只激活已有窗口。XDG 安装位置、发行版包提示和卸载方式见
[原生 Linux 安装说明](docs/INSTALL_LINUX.md)。

## 不安装桌面宿主

依赖准备完成后，可以直接运行浏览器模式：

```bash
conda run -n researchmate python src/backend/run.py
```

默认访问 `http://127.0.0.1:8000`。资料导入、OCR、论文、求职、行动专题和工作区操作见
[快速上手](docs/QUICKSTART.md) 与 [使用手册](docs/MANUAL.md)。

## AI 与隐私

AI 是可选增强能力，不是安装前提。页面不会在加载时自动连接服务商；每次分析必须由用户明确触发并
确认发送字段、资料范围和截断上限。运行成功与脱敏失败均保留审计历史，AI 结果不会覆盖来源事实或
用户确认。

Key 推荐通过环境变量或设置页的会话安全模式提供。只有用户明确选择便利模式后，才会在风险提示下
明文保存到已被 Git 忽略的本地配置；Key 不进入 SQLite、日志或审计记录。完整边界见
[使用手册](docs/MANUAL.md)、[产品规格](docs/PRODUCT.md) 和 [架构说明](docs/ARCHITECTURE.md)。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [快速上手](docs/QUICKSTART.md) | 最短源码启动和第一次使用 |
| [使用手册](docs/MANUAL.md) | 资料、OCR、论文、AI、工作区操作 |
| [Windows + WSL 安装](docs/INSTALL_WINDOWS_WSL.md) | 完整依赖、透明计划、路径、更新与卸载 |
| [原生 Linux 安装](docs/INSTALL_LINUX.md) | GTK/WebKitGTK、XDG 路径、启动与卸载 |
| [产品规格](docs/PRODUCT.md) | 产品目标、范围和不做事项 |
| [架构说明](docs/ARCHITECTURE.md) | 数据分层、安全与组件边界 |
| [平台交付设计](docs/PLATFORM_DISTRIBUTION.md) | 单仓库多平台策略与发布边界 |
| [当前路线图](docs/ROADMAP.md) | 已验证事实、活跃债务和下一切片 |
| [开发与验证](docs/DEVELOPMENT.md) | Codex 会话、测试、公开前安全检查 |

## License

[The Unlicense](LICENSE.txt)
