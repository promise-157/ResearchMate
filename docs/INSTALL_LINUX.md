# 原生 Linux 桌面安装

[返回项目首页](../README.md) · [Windows + WSL 安装](INSTALL_WINDOWS_WSL.md) · [开发与验证](DEVELOPMENT.md)

原生 Linux 版不是 WSL 包装：GTK 3/WebKitGTK 窗口、FastAPI 后端、配置和进程都在同一个 Linux 用户
会话中运行。它复用现有 Vue 页面和私有 supervisor；关闭唯一窗口只停止该窗口拥有的后端进程组，
不会关机、注销或结束其他服务。第二次运行 `researchmate` 会通过用户私有 Unix socket 激活已有窗口。

## 用户自行准备的依赖

- 带图形会话的 Linux；X11、Wayland 均由 GTK 处理。
- `/usr/bin/python3`、PyGObject、GTK 3。
- WebKitGTK 4.1 或 4.0 的 introspection 包。
- Git、用户选择的 Conda/Mamba/Micromamba 兼容工具和 Python 3.11 环境。
- Node/npm，仅用于安装 Vue 依赖和生成 `src/frontend/dist`。
- 可选 Tesseract 与所需 OCR 语言包。

不同发行版包名不同，ResearchMate 不自动调用 apt/dnf/pacman，也不会在卸载时删除系统包。以 Ubuntu
20.04 为例，当前实测窗口依赖是 `python3-gi`、`gir1.2-gtk-3.0` 和
`gir1.2-webkit2-4.0`；较新发行版通常提供 WebKitGTK 4.1 对应包。应以发行版官方仓库为准。

后端和前端准备与 README 相同。完成后运行：

```bash
python3 packaging/linux/setup_researchmate.py --mode check \
  --conda /home/alice/miniforge3/condabin/conda
python3 packaging/linux/setup_researchmate.py --mode plan \
  --conda /home/alice/miniforge3/condabin/conda
```

审查被 Git 忽略的 `researchmate-linux-install-plan.json`，确认项目、环境、端口和所有权边界，再运行：

```bash
python3 packaging/linux/setup_researchmate.py --mode apply
```

安装后可执行 `~/.local/bin/researchmate`，若 `~/.local/bin` 已在 PATH 中则直接执行 `researchmate`；也可
从桌面应用菜单选择 ResearchMate。

## 安装所有权

| 内容 | 默认位置 | 卸载行为 |
| --- | --- | --- |
| Linux GTK/WebKit 宿主 | `$XDG_DATA_HOME/researchmate-desktop` | 删除 |
| 命令入口 | `~/.local/bin/researchmate` | 删除 |
| 应用菜单入口 | `$XDG_DATA_HOME/applications/researchmate.desktop` | 删除 |
| 连接配置 | `$XDG_CONFIG_HOME/researchmate/desktop-config.json` | 删除 |
| 日志 | `$XDG_STATE_HOME/researchmate` | 仅显式选择时删除 |
| 运行锁/socket | `$XDG_RUNTIME_DIR/researchmate` 或缓存回退 | 仅显式选择时删除 |
| 系统图形包、工具链、源码、环境和工作区 | 用户所有 | 永不删除 |

安装采用 staging/previous 切换，并在后半段失败时恢复旧宿主、配置、命令和应用入口。安装清单位于
宿主目录。卸载前先关闭窗口，再运行安装目录中的：

```bash
python3 uninstall_researchmate.py
```

加 `--remove-local-state` 才会清除日志和运行缓存。卸载不会执行包管理器删除、环境删除、Git 删除或
工作区清理。
