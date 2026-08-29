# Windows + WSL 从零安装 ResearchMate

[返回项目首页](../README.md) · [安装与卸载边界](INSTALL_WINDOWS_WSL.md) · [原生 Linux](INSTALL_LINUX.md)

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

如果在 Windows PowerShell 中提示找不到 `powershell.exe`，先检查命令和 PATH：

```powershell
Get-Command powershell.exe -ErrorAction SilentlyContinue
$env:Path -split ';'
Test-Path "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
```

最后一条为 `True` 时，说明 PowerShell 文件存在但 Windows PATH 缺少其目录。可以先只为当前窗口
临时补回 PATH，再继续安装：

```powershell
$env:Path = "$env:SystemRoot\System32\WindowsPowerShell\v1.0;$env:Path"
powershell.exe -NoProfile -Command '$PSVersionTable.PSVersion'
```

关闭该窗口后临时修改会失效。如需永久修复，在 Windows“编辑当前用户的环境变量”中检查 `Path`，
不要删除原有项目，并加入 `%SystemRoot%\System32\WindowsPowerShell\v1.0`。也可以完全绕过 PATH，
把后续命令开头的 `powershell.exe` 替换为以下绝对路径：

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command '$PSVersionTable.PSVersion'
```

### 11. Windows PowerShell：保存一次配置，以后一条命令安装或更新

先在 **WSL/Ubuntu** 中查询两个 Linux 路径：

```bash
cd "$HOME/ResearchMate"
pwd
conda info --base
```

记下输出。例如本文的默认安装会分别输出 `/home/promise/ResearchMate` 和
`/home/promise/miniconda3`。第二个路径末尾加 `/condabin/conda`，就是脚本需要的 Conda 可执行文件。

然后打开独立的 **Windows PowerShell**，查询发行版名称：

```powershell
wsl --list --quiet
```

需要写入本机配置的三个值如下：

| JSON 字段 | 应填写什么 | 示例 |
| --- | --- | --- |
| `distro` | `wsl --list --quiet` 显示的完整名称 | `Ubuntu20.04` |
| `project_path` | WSL 中执行 `pwd` 得到的项目绝对路径 | `/home/promise/ResearchMate` |
| `conda_executable` | `conda info --base` 的结果加 `/condabin/conda` | `/home/promise/miniconda3/condabin/conda` |

下面以发行版 `Ubuntu20.04`、Linux 用户 `promise` 为例。以下每个代码框都是完整单行，必须在
**Windows PowerShell** 中执行，不要在 WSL 中执行，也不要使用 `sudo` 或修改 `powershell.exe`
权限。

先复制仓库提供的配置模板：

```powershell
Copy-Item "\\wsl.localhost\Ubuntu20.04\home\promise\ResearchMate\researchmate-install.example.json" "\\wsl.localhost\Ubuntu20.04\home\promise\ResearchMate\researchmate-install.local.json"
```

用 Windows 记事本打开本机配置：

```powershell
notepad.exe "\\wsl.localhost\Ubuntu20.04\home\promise\ResearchMate\researchmate-install.local.json"
```

只需把配置中的 `distro`、`project_path`、`conda_executable` 和需要自定义的 Windows
`install_directory` 改成刚才查到的真实值并保存。该文件已被 Git 忽略，不会提交；不要在里面填写
密码、AI Key 或其他秘密。

保存后，执行下面这一条 **Windows PowerShell 单行命令**。它会在一次运行中依次完成 Check、生成并
显示 Plan、Apply 和安装结果验证；任何必需检查失败都会在修改安装前停止：

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force; & "\\wsl.localhost\Ubuntu20.04\home\promise\ResearchMate\packaging\windows-wsl\setup\Setup-ResearchMate.ps1" -Mode Install -ConfigPath "\\wsl.localhost\Ubuntu20.04\home\promise\ResearchMate\researchmate-install.local.json" -Yes
```

`-Yes` 表示显示计划后自动应用，仍然不会跳过 Check 或 Plan。如果希望在每次修改前人工确认，删掉
命令末尾的 `-Yes`，看到计划后输入大写 `YES`。计划同时保存在仓库根目录的
`researchmate-install-plan.json`。

以后 `git pull` 后更新桌面宿主，仍然执行上面同一条 `-Mode Install ... -Yes` 命令，无需重新填写
配置，也不会重新安装 WSL、Miniconda、Node 或 .NET。只有路径发生变化时才修改本机 JSON。

安装完成后，Windows 桌面会出现唯一的 `ResearchMate` 快捷方式。双击打开窗口；关闭窗口会同时停止
它启动的 WSL 后端，不需要再点一次“退出”，也不会关闭整个 WSL。

首次打开后进入 `设置 → 安装与卸载`，可以直接查看这台电脑实际使用的 Windows 宿主目录、配置与
日志目录、快捷方式、WSL 源码、前端构建、工作区数据边界和卸载文档路径。这里的信息来自当前桌面
宿主，而不是 README 中的示例路径；从 Git 克隆到任何用户名或磁盘后都应以设置页显示为准。

### 更换 Windows 快捷方式图标

仓库默认图标位于 `assets/branding/researchmate.ico`。执行第 11 步的安装/更新命令后，Windows 宿主
和新建快捷方式会使用该图标。

在 Windows 桌面快捷方式打开的窗口中进入 `设置 → 安装与卸载 → Windows 快捷方式图标`，点击
“选择 ICO 文件”即可更换，也可以恢复默认图标。只接受有效 `.ico` 文件，最大 5 MiB；建议使用
包含 16、32、48、128、256 像素多种尺寸的方形 ICO，至少应包含清晰的 256×256、32 位图像。

所选文件会复制到 `%LOCALAPPDATA%\ResearchMate\shortcut-icon.ico`，因此原文件随后可以移动或
删除，后续重新运行安装器也会保留自定义图标。普通浏览器模式不会获得修改 Windows 快捷方式的
权限，按钮会明确禁用。Windows 图标缓存有时不会立刻刷新，重新登录或刷新资源管理器后会显示新
图标。

## 以后怎么启动或更新

正常使用只需双击 Windows 桌面的 `ResearchMate`。

只要本机 JSON 中的路径没有变化，以后 `git pull` 后仍然重复执行第 11 步同一条
`-Mode Install ... -Yes` 的 Windows PowerShell 单行命令。它会复用配置并更新宿主，不需要再次填写
参数。

## 只在浏览器使用（WSL 或原生 Linux）

如果不需要 Windows 桌面窗口，也不需要原生 Linux 桌面宿主，就不必运行 PowerShell 安装器，也不
需要安装 .NET 或 WebView2。在 WSL 或原生 Linux 终端执行以下命令：

```bash
cd "$HOME/ResearchMate"
conda run -n researchmate python src/backend/run.py --no-browser
```

保持该终端开启，然后在浏览器访问：

```text
http://127.0.0.1:8000
```

Windows 浏览器可以直接访问 WSL 中的这个地址。使用完毕后回到启动终端按 `Ctrl+C`，后端随即关闭。
这种方式仍需要 README 前面列出的 Python 依赖和已构建的前端 `dist/`，但不包含任何桌面安装文件。

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

已有其他 Conda 安装位置时，不要使用示例的 Miniconda 路径；把第 11 步本机 JSON 中
`conda_executable` 的值替换成实际 Conda/Mamba 可执行文件绝对路径。

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

如果前端或 Windows 宿主有更新，再执行第 11 步同一条 `-Mode Install ... -Yes` 命令。它会自动检查、
写出并显示计划后应用；只执行 `git pull` 不会自动更新已经安装到 Windows 的 EXE。

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
[Windows + WSL 安装与卸载](INSTALL_WINDOWS_WSL.md)。

## 原生 Linux

原生 Linux 先执行上面的第 2–9 步，再安装 GTK 3、PyGObject 和 WebKitGTK。Ubuntu 20.04 实测命令：

```bash
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

然后按照 [原生 Linux 桌面安装](INSTALL_LINUX.md) 创建应用菜单入口和 `researchmate` 命令。
较新 Linux 发行版可能使用 WebKitGTK 4.1。原生 Windows 后端目前尚未发布。

## AI 与数据安全

AI 不是安装前提。页面不会自动连接服务商，每次外部调用必须由用户主动触发并确认发送范围。
来源事实、AI 建议和用户确认分层保存；Key 默认只保留在当前进程。

## 更多文档

- [快速上手](QUICKSTART.md)
- [使用手册](MANUAL.md)
- [Windows + WSL 安装与卸载](INSTALL_WINDOWS_WSL.md)
- [原生 Linux 安装](INSTALL_LINUX.md)
- [开发与验证](DEVELOPMENT.md)
- [产品规格](PRODUCT.md)
- [架构说明](ARCHITECTURE.md)
- [路线图](ROADMAP.md)

## License

[The Unlicense](../LICENSE.txt)
