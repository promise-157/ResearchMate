# ResearchMate

ResearchMate 是一个本地优先的个人资料工作空间，可导入文字、图片、公开网页候选和论文摘要，完成
审核、提取、搜索、组织、可审计 AI 分析与行动专题。AI 是可选能力；没有 Key 也能使用本地功能。

本文首先给出 **Windows + WSL 2 从零安装**的完整步骤。每项依赖都先检查，已经存在且版本合适就
跳过对应安装命令。ResearchMate 不会替你安装 WSL、Conda、Node、.NET 或系统软件。

## 一、Windows + WSL 2 从零安装

### 0. 你将安装什么

| 位置 | 内容 | 是否日常运行必需 |
| --- | --- | --- |
| Windows | WSL 2、WebView2 Runtime、ResearchMate 窗口和快捷方式 | 是 |
| Windows | .NET 10 SDK | 只在首次构建或更新桌面窗口时需要 |
| WSL | Git、Miniconda、Python 3.11 环境、ResearchMate 源码 | 是 |
| WSL Conda 环境 | 后端 Python 包、Node.js 20、npm、Vue 项目依赖 | Node/npm 只在构建前端时需要 |
| WSL（可选） | Tesseract 与中英文语言包 | 只在本机图片 OCR 时需要 |

命令块标有运行位置：`Windows PowerShell` 或 `WSL`。不要把两种终端的命令混在一起执行。

### 1. 检查或安装 WSL 2

在 **Windows PowerShell** 中检查：

```powershell
wsl --status
wsl --list --verbose
```

如果已经能看到一个 `VERSION` 为 `2` 的 Ubuntu 发行版，跳到第 2 步。否则以管理员身份打开
PowerShell，执行：

```powershell
wsl --install -d Ubuntu-24.04
```

按提示重启，首次打开 Ubuntu 时创建 Linux 用户名和密码，然后再次执行 `wsl --list --verbose`。
如果已有发行版但版本是 1，把下面占位符替换成列表中的实际名称：

```powershell
wsl --set-version <发行版名称> 2
```

### 2. 检查或安装 WSL 基础工具

进入 Ubuntu/WSL，以下命令均在 **WSL** 中运行：

```bash
git --version
curl --version
```

两条都成功就跳过安装。缺少任意一项时执行：

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
```

再次运行 `git --version` 和 `curl --version` 验证。

### 3. 检查或安装 Miniconda

```bash
conda --version
```

如果成功且你知道安装位置，跳到第 4 步。若提示找不到命令，下面会安装到 `$HOME/miniconda3`；
如需其他磁盘或目录，先修改命令中的目标路径：

```bash
uname -m
```

输出为 `x86_64` 时执行：

```bash
curl -fsSLo /tmp/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash /tmp/miniconda.sh -b -p "$HOME/miniconda3"
"$HOME/miniconda3/bin/conda" init bash
source "$HOME/.bashrc"
```

输出为 `aarch64` 时，把下载文件名中的 `Linux-x86_64` 改成 `Linux-aarch64`。最后验证并记录 Conda
根目录，后面安装快捷方式时会用到：

```bash
conda --version
conda info --base
```

### 4. 获取源码

以下示例把源码放到 WSL 用户目录。仓库已经存在时直接进入它，跳过 `git clone`：

```bash
cd "$HOME"
git clone https://github.com/promise-157/ResearchMate.git
cd ResearchMate
git status --short
```

最后一条无输出表示新克隆的工作树干净。后续 WSL 命令默认从仓库根目录执行。

### 5. 创建或复用 ResearchMate 环境

先检查：

```bash
conda env list
```

列表中已有 `researchmate` 时不要重复创建，验证其版本：

```bash
conda run -n researchmate python --version
conda run -n researchmate node --version
conda run -n researchmate npm --version
```

要求 Python 3.11、Node.js 18 或更高版本。环境不存在时执行；Node 放在同一 Conda 环境里，不必再用
`apt` 或 `nvm` 安装一份：

```bash
conda create -n researchmate -c conda-forge python=3.11 nodejs=20 pip -y
```

如果环境已存在但缺少 Node/npm，只补装它：

```bash
conda install -n researchmate -c conda-forge nodejs=20 -y
```

### 6. 安装后端依赖

先检查核心包：

```bash
conda run -n researchmate python -c "import fastapi, uvicorn, httpx, PIL; print('backend dependencies: OK')"
```

成功就跳过。失败时执行：

```bash
conda run -n researchmate python -m pip install -r src/backend/requirements.txt
```

开发和运行后端测试时才需要额外安装：

```bash
conda run -n researchmate python -m pip install -r src/backend/requirements-dev.txt
```

### 7. 安装并构建前端

Vue、Element Plus、Vite 等由 `package-lock.json` 固定，不需要全局安装 Vue。先检查：

```bash
test -f src/frontend/dist/index.html && echo "frontend build: OK" || echo "frontend build: missing"
```

显示 `OK` 就跳过。否则执行：

```bash
conda run -n researchmate npm --prefix src/frontend ci
conda run -n researchmate npm --prefix src/frontend run build
test -f src/frontend/dist/index.html && echo "frontend build: OK"
```

`npm ci` 只写入仓库内被 Git 忽略的 `src/frontend/node_modules`，不会全局安装 Vue。

### 8. 可选：安装本地 OCR

不使用图片 OCR 可以跳过。先检查：

```bash
tesseract --version
tesseract --list-langs
```

Ubuntu 中缺少时执行：

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim
```

再次检查，应至少看到 `eng`；需要中文 OCR 时还应看到 `chi_sim`。

### 9. 先用浏览器模式验证应用

在仓库根目录的 **WSL** 终端运行：

```bash
conda run -n researchmate python src/backend/run.py --no-browser
```

在 Windows 浏览器打开 `http://127.0.0.1:8000`。看到页面后，在 WSL 终端按 `Ctrl+C` 关闭。若
8000 端口确实被旧 ResearchMate 占用，可先看诊断，再谨慎使用：

```bash
conda run -n researchmate python src/backend/run.py --kill --no-browser
```

### 10. 检查或安装 Windows 桌面构建依赖

回到 **Windows PowerShell**：

```powershell
winget --version
dotnet --version
```

`.NET` 显示 `10.x` 时跳过 SDK 安装，否则执行：

```powershell
winget install --exact --id Microsoft.DotNet.SDK.10
```

关闭并重新打开 PowerShell，再检查 `dotnet --version`。然后检查 WebView2 Runtime：

```powershell
Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\*' -ErrorAction SilentlyContinue |
  Where-Object { $_.name -like '*WebView2*' } |
  Select-Object name, pv
```

有输出就跳过；没有输出时执行：

```powershell
winget install --exact --id Microsoft.EdgeWebView2Runtime
```

### 11. 生成 Windows 窗口和唯一桌面快捷方式

回到仓库根目录的 **WSL** 终端，记录三个真实值：

```bash
wsl.exe --list --quiet
pwd
conda info --base
```

- 第一条给出发行版名称，例如 `Ubuntu-24.04`。
- 第二条是仓库绝对路径，例如 `/home/alice/ResearchMate`。
- 第三条若输出 `/home/alice/miniconda3`，Conda 可执行文件就是
  `/home/alice/miniconda3/condabin/conda`。

下面的项目脚本**不会下载或安装上述依赖**。它只检查环境、从源码构建约 119 MiB 的 Windows
宿主、写入连接配置、创建一个桌面快捷方式和当前用户卸载项。

先只读检查：

```bash
setup_win="$(wslpath -w packaging/windows-wsl/setup/Setup-ResearchMate.ps1)"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$setup_win" -Mode Check
```

若自动识别错误，明确传入自己的实际值（不要原样照抄示例用户和路径）：

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$setup_win" -Mode Check \
  -Distro 'Ubuntu-24.04' \
  -ProjectPath '/home/alice/ResearchMate' \
  -CondaExecutable '/home/alice/miniconda3/condabin/conda'
```

全部必需检查通过后生成计划：

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$setup_win" -Mode Plan \
  -Distro 'Ubuntu-24.04' \
  -ProjectPath '/home/alice/ResearchMate' \
  -CondaExecutable '/home/alice/miniconda3/condabin/conda'
```

查看计划，确认路径、端口和安装位置：

```bash
sed -n '1,240p' researchmate-install-plan.json
```

确认无误后才执行：

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$setup_win" -Mode Apply
```

现在双击 Windows 桌面的 `ResearchMate`。再次双击只激活已有窗口；关闭唯一窗口会停止它启动的
WSL 后端，但不会关闭整个 WSL 或其他程序。

## 二、以后如何启动、更新和卸载

### 日常启动与关闭

- 启动：双击 Windows 桌面的 `ResearchMate`。
- 关闭：直接关闭 ResearchMate 窗口，不需要再运行停止脚本。
- 浏览器模式：运行 `conda run -n researchmate python src/backend/run.py --no-browser`，按
  `Ctrl+C` 关闭。

### 更新源码与依赖

先关闭窗口，在仓库根目录检查自己的修改；有未提交修改时不要盲目拉取：

```bash
git status --short
git pull --ff-only
conda run -n researchmate python -m pip install -r src/backend/requirements.txt
conda run -n researchmate npm --prefix src/frontend ci
conda run -n researchmate npm --prefix src/frontend run build
```

前端或 Windows 宿主有变化时，重新执行第 11 步的 `Check → Plan → Apply`。

### 卸载边界

先关闭窗口，再从 Windows“设置 → 应用 → 已安装的应用”卸载 ResearchMate。它只删除 Windows
宿主、快捷方式、卸载项和连接配置，不删除 WSL、Conda、源码、工作区、图片资产或归档。完整路径和
可选本地状态清理见 [Windows + WSL 安装与卸载](docs/INSTALL_WINDOWS_WSL.md)。

第 11 步 `Apply` 成功后，即使在陌生电脑上，安装目录中也一定会同时出现：

- `uninstall-guide-zh-CN.txt`：可离线阅读的中文彻底卸载说明；
- `Uninstall-ResearchMate.ps1`：Windows“已安装的应用”实际调用的卸载器；
- `installation-manifest.json`：本次安装创建内容及外部依赖边界。

默认安装目录是 `D:\Apps\ResearchMate`（电脑已有 `D:\Apps` 时），否则是
`%LOCALAPPDATA%\Programs\ResearchMate`；第 11 步生成的 JSON 计划会在写入前显示实际目录。只安装
依赖或只使用浏览器模式时不会出现这些文件，因为那时还没有安装 Windows 桌面宿主。

如果还要删除自己安装的开发环境，请先备份工作区，再分别决定是否删除源码、Conda 环境、Miniconda
和 WSL 发行版；ResearchMate 不会代替你执行这些破坏性操作。

## 三、已有部分依赖时怎么做

按第一部分从上到下执行每个检查命令：

- 版本满足要求：跳过该项安装命令。
- 命令不存在或版本不足：只执行紧随其后的安装或补装命令。
- 已有 Anaconda、Miniforge、Mamba 或 Micromamba：继续使用，不必安装 Miniconda；桌面配置需填写
  它在 WSL 中真实、非交互可执行的绝对路径。
- 已有 Node 18+：可以使用；放进 `researchmate` Conda 环境最容易保证桌面非交互启动也能找到。
- 已有前端 `dist`：日常运行不需要 Node/npm；更新源码后才需重新安装和构建。
- 不需要 OCR：不要安装 Tesseract。

## 四、原生 Linux

原生 Linux 使用同一套源码、Conda 环境和前端构建。先完成第 2–8 步，再安装 GTK 3、PyGObject 和
WebKitGTK introspection。Ubuntu 20.04 当前实测命令为：

```bash
sudo apt update
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0
```

较新发行版可能使用 WebKitGTK 4.1，包名以发行版仓库为准。然后按
[原生 Linux 桌面安装](docs/INSTALL_LINUX.md) 创建应用菜单入口和 `researchmate` 命令。原生 Windows
后端目前没有发布，不能把 WSL 版写成原生 Windows 版。

## 五、AI、数据和文档

AI 是可选增强能力。页面不会自动连接服务商，每次外部调用必须由用户明确触发并确认发送范围。
Key 默认只保留在当前进程；工作区、来源事实、AI 建议和用户确认分层保存。

- [快速上手](docs/QUICKSTART.md)：第一次导入资料和使用功能。
- [使用手册](docs/MANUAL.md)：资料、OCR、论文、AI、工作区和行动专题。
- [Windows + WSL 安装与卸载](docs/INSTALL_WINDOWS_WSL.md)：安装所有权、路径、更新和卸载边界。
- [原生 Linux 安装](docs/INSTALL_LINUX.md)：GTK/WebKitGTK 与 XDG 安装。
- [开发与验证](docs/DEVELOPMENT.md)：测试和公开前检查。
- [产品规格](docs/PRODUCT.md)、[架构说明](docs/ARCHITECTURE.md)、[路线图](docs/ROADMAP.md)。

## License

[The Unlicense](LICENSE.txt)
