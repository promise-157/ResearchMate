# ResearchMate

ResearchMate 是一个运行在本机的个人资料工作空间，支持文字、图片、公开网页候选、论文、Debug、
求职资料、本地 OCR、可审计 AI 分析、行动专题和完整工作区归档。

下面是 **Windows + WSL 2 新电脑从零安装**的完整流程。按顺序复制执行即可。命令标题会明确说明
是在 Windows PowerShell 还是 WSL/Ubuntu 中执行。

> 当前可用桌面版在 `development` 分支。克隆时必须指定该分支。

## 从零安装 Windows + WSL 桌面版

### 1. Windows PowerShell：安装 WSL 2 和 Ubuntu

以管理员身份打开 Windows PowerShell：

```powershell
wsl --install -d Ubuntu-24.04
```

如果提示 WSL 或 Ubuntu 已安装，可以直接继续。新安装后按提示重启 Windows，打开 Ubuntu，创建
Linux 用户名和密码。然后在 PowerShell 确认 Ubuntu 的 `VERSION` 是 `2`：

```powershell
wsl --list --verbose
```

### 2. WSL/Ubuntu：安装 Git、curl 和证书

打开 Ubuntu 终端：

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
```

### 3. WSL/Ubuntu：安装 Miniconda

下面把 Miniconda 安装到当前 Linux 用户的 `~/miniconda3`，不会装到 Windows C 盘目录：

```bash
cd /tmp
curl -fsSLo miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash miniconda.sh -b -p "$HOME/miniconda3"
"$HOME/miniconda3/bin/conda" init bash
source "$HOME/.bashrc"
conda --version
```

最后一条能显示 Conda 版本即可。ARM64 电脑需要把下载地址中的 `Linux-x86_64` 换成
`Linux-aarch64`。

### 4. WSL/Ubuntu：克隆 development 分支

```bash
cd "$HOME"
git clone --branch development --single-branch https://github.com/promise-157/ResearchMate.git
cd ResearchMate
git branch --show-current
```

最后一条必须输出：

```text
development
```

### 5. WSL/Ubuntu：创建 Python、Node 和 npm 环境

这一条会创建名为 `researchmate` 的独立环境，并安装 Python 3.11、Node.js 20 和 npm：

```bash
conda create -n researchmate --override-channels -c conda-forge python=3.11 nodejs=20 pip -y
```

这里必须保留 `--override-channels`。新版 Miniconda 的默认 Anaconda channels 可能要求先接受 ToS；
ResearchMate 创建环境只使用 `conda-forge`，因此不需要接受或使用 `pkgs/main`、`pkgs/r`。

确认版本：

```bash
conda run -n researchmate python --version
conda run -n researchmate node --version
conda run -n researchmate npm --version
```

### 6. WSL/Ubuntu：安装 ResearchMate 后端依赖

确保当前目录仍是 `~/ResearchMate`：

```bash
cd "$HOME/ResearchMate"
conda run -n researchmate python -m pip install -r src/backend/requirements.txt
```

### 7. WSL/Ubuntu：安装 Vue 等前端依赖并构建页面

不需要单独或全局安装 Vue。`npm ci` 会按照仓库的锁文件安装 Vue、Vite、Element Plus 等全部前端
依赖，随后生成生产页面：

```bash
cd "$HOME/ResearchMate"
conda run -n researchmate npm --prefix src/frontend ci
conda run -n researchmate npm --prefix src/frontend run build
```

确认构建文件存在：

```bash
test -f src/frontend/dist/index.html && echo "frontend build: OK"
```

### 8. WSL/Ubuntu：启动一次，确认核心程序可用

```bash
cd "$HOME/ResearchMate"
conda run -n researchmate python src/backend/run.py --no-browser
```

在 Windows 浏览器打开：

```text
http://127.0.0.1:8000
```

看到 ResearchMate 页面后，回到 Ubuntu 终端按 `Ctrl+C` 关闭。

### 9. 可选：WSL/Ubuntu 安装中英文 OCR

不需要识别图片文字可以跳过这一节。需要 OCR 时执行：

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim
tesseract --list-langs
```

输出中应包含 `eng` 和 `chi_sim`。

### 10. Windows PowerShell：安装桌面窗口构建依赖

普通权限打开 Windows PowerShell，安装 .NET 10 SDK 和 WebView2 Runtime：

```powershell
winget install --exact --id Microsoft.DotNet.SDK.10
winget install --exact --id Microsoft.EdgeWebView2Runtime
```

如果提示已经安装，直接继续。关闭并重新打开 PowerShell，确认 .NET：

```powershell
dotnet --version
```

版本应以 `10.` 开头。Windows 11 通常已经带有 WebView2 Runtime，重复执行上面的 `winget install`
只会提示已安装。

### 11. WSL/Ubuntu：构建 Windows 窗口并创建桌面快捷方式

回到 Ubuntu 终端，先确认当前环境确实是 Microsoft WSL，且 Windows C 盘已挂载：

```bash
uname -r
test -d /mnt/c && echo "Windows drive: OK"
test -x /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe && echo "Windows PowerShell interop: OK"
```

第一条应包含 `microsoft` 或 `WSL`，后两条应输出 `OK`。README 不依赖 `powershell.exe` 是否被加入
WSL 的 `PATH`，后续始终使用它的 Windows 标准绝对路径。

如果 `/mnt/c` 或 PowerShell 文件不存在，先在独立的 **Windows PowerShell** 窗口执行：

```powershell
wsl --shutdown
```

重新打开 Ubuntu，再运行上面三条检查。如果仍失败，执行 `cat /etc/wsl.conf` 检查是否人为关闭了
`automount` 或 `interop`；不要继续执行桌面安装。原生 Linux 本来就没有 Windows `powershell.exe`，
应改走本文的“原生 Linux”章节。

检查通过后，在 Ubuntu 中回到仓库：

```bash
cd "$HOME/ResearchMate"
```

先检查刚才安装的所有环境：

```bash
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)" -Mode Check
```

检查全部通过后生成安装计划：

```bash
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)" -Mode Plan
```

查看计划中的 WSL 发行版、项目路径、Conda 路径、端口和 Windows 安装目录：

```bash
sed -n '1,240p' researchmate-install-plan.json
```

确认正确后安装：

```bash
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)" -Mode Apply
```

安装完成后，Windows 桌面会出现唯一的 `ResearchMate` 快捷方式。双击打开窗口；关闭窗口会同时停止
它启动的 WSL 后端，不需要再点一次“退出”，也不会关闭整个 WSL。

## 以后怎么启动

正常使用只需双击 Windows 桌面的 `ResearchMate`。

如果只想用浏览器模式：

```bash
cd "$HOME/ResearchMate"
conda run -n researchmate python src/backend/run.py --no-browser
```

浏览器模式按 `Ctrl+C` 关闭。

## 已经安装过部分依赖

不需要全部重装，按照下面的对应关系跳过即可：

| 已有内容 | 可以跳过 |
| --- | --- |
| 已有 WSL 2 Ubuntu | 第 1 步 |
| 已有 Git 和 curl | 第 2 步 |
| 已有可用的 Conda、Anaconda、Miniforge 或 Mamba | 第 3 步 |
| 已克隆 `development` 分支 | 第 4 步 |
| 已有 Python 3.11 的 `researchmate` 环境 | 不要重新创建；缺 Node 时只执行下面的补装命令 |
| `src/frontend/dist/index.html` 已存在且源码未更新 | 第 7 步 |
| 不使用图片 OCR | 第 9 步 |
| 已有 .NET 10 SDK 或 WebView2 | 第 10 步中对应的命令 |
| 已有正常工作的桌面快捷方式且宿主源码未更新 | 第 11 步 |

已有 `researchmate` 环境但缺少 Node/npm，只补装 Node：

```bash
conda install -n researchmate --override-channels -c conda-forge nodejs=20 -y
```

已有其他 Conda 安装位置时，第 11 步如果没有自动识别，可明确指定。例如：

```bash
cd /你的/ResearchMate/绝对路径
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)" -Mode Check -Distro '你的WSL发行版名称' -ProjectPath '/你的/ResearchMate/绝对路径' -CondaExecutable '/你的/conda/绝对路径/condabin/conda'
```

三个实际值可以这样查看：

```bash
/mnt/c/Windows/System32/wsl.exe --list --quiet
pwd
conda info --base
```

## 更新

关闭 ResearchMate 窗口，在 Ubuntu 的仓库目录执行：

```bash
cd "$HOME/ResearchMate"
git status --short
git pull --ff-only
conda run -n researchmate python -m pip install -r src/backend/requirements.txt
conda run -n researchmate npm --prefix src/frontend ci
conda run -n researchmate npm --prefix src/frontend run build
```

如果前端或 Windows 宿主有更新，再执行第 11 步的 `Check → Plan → Apply`。

## 卸载

先关闭 ResearchMate 窗口，再打开 Windows：

```text
设置 → 应用 → 已安装的应用 → ResearchMate (Windows + WSL) → 卸载
```

陌生电脑完成第 11 步后，实际 Windows 安装目录中也会自动出现：

- `uninstall-guide-zh-CN.txt`：中文彻底卸载说明；
- `Uninstall-ResearchMate.ps1`：卸载器；
- `installation-manifest.json`：本次安装创建的文件和外部依赖边界。

默认安装目录是 `D:\Apps\ResearchMate`（电脑已有 `D:\Apps` 时），否则是
`%LOCALAPPDATA%\Programs\ResearchMate`。卸载 ResearchMate 不会删除 WSL、Ubuntu、Miniconda、
源码、工作区、图片资产或归档；是否继续删除这些用户所有内容由用户自己决定。详细说明见
[Windows + WSL 安装与卸载](docs/INSTALL_WINDOWS_WSL.md)。

## 原生 Linux

原生 Linux 先执行上面的第 2–9 步，再安装 GTK 3、PyGObject 和 WebKitGTK。Ubuntu 20.04 实测命令：

```bash
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

然后按照 [原生 Linux 桌面安装](docs/INSTALL_LINUX.md) 创建应用菜单入口和 `researchmate` 命令。
较新 Linux 发行版可能使用 WebKitGTK 4.1。原生 Windows 后端目前尚未发布。

## AI 与数据安全

AI 不是安装前提。页面不会自动连接服务商，每次外部调用必须由用户主动触发并确认发送范围。
来源事实、AI 建议和用户确认分层保存；Key 默认只保留在当前进程。

## 更多文档

- [快速上手](docs/QUICKSTART.md)
- [使用手册](docs/MANUAL.md)
- [Windows + WSL 安装与卸载](docs/INSTALL_WINDOWS_WSL.md)
- [原生 Linux 安装](docs/INSTALL_LINUX.md)
- [开发与验证](docs/DEVELOPMENT.md)
- [产品规格](docs/PRODUCT.md)
- [架构说明](docs/ARCHITECTURE.md)
- [路线图](docs/ROADMAP.md)

## License

[The Unlicense](LICENSE.txt)
