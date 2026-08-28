# 开发与验证

[返回项目首页](../README.md) · [Windows + WSL 安装](INSTALL_WINDOWS_WSL.md) · [原生 Linux 安装](INSTALL_LINUX.md)

## 环境

开发依赖 Python 3.11、Node.js 18+ 和 npm。后端依赖声明在
`src/backend/requirements.txt`，前端依赖由 `src/frontend/package-lock.json` 固定。桌面平台依赖和
安装方式分别见 [Windows + WSL](INSTALL_WINDOWS_WSL.md) 与 [原生 Linux](INSTALL_LINUX.md)。

开发模式（前端热更新）：

```bash
cd src/backend
python run.py --dev --no-browser
```

若端口确由旧进程占用，`python run.py --kill --no-browser` 会精确查找并终止 Linux listener；WSL 中
由 Windows 进程占用时会转用 PowerShell 查找 Windows listener。启动器会重新验证端口，权限不足时
给出诊断和 `RESEARCHMATE_PORT` 换端口方式。

## Codex 会话

从仓库根目录开启 Codex。根目录 [AGENTS.md](../AGENTS.md) 规定每次会话必须先完整阅读：

- [产品规格](PRODUCT.md)；
- [架构约束](ARCHITECTURE.md)；
- [当前路线图](ROADMAP.md)。

路线图只记录验证过的当前事实，完成历史进入 [CHANGELOG](../CHANGELOG.md)。不要使用聊天记忆、
忽略草稿或旧辅助文件代替这些项目事实。

## 完整验证

使用现有环境，不在测试中调用真实 AI、真实来源、真实 Key 或 `src/data`：

```bash
PYTHONDONTWRITEBYTECODE=1 conda run -n researchmate python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 conda run -n researchmate python -m compileall -q src/backend
conda run -n researchmate ruff check src/backend tests
cd src/frontend && npm run lint && npm run build && npm run test:e2e
git diff --check
```

桌面平台还有各自安装文档与 `packaging/<platform>/README.md` 中的离线/真实生命周期验证。生产构建
成功本身不能证明用户工作流可用。

## 公开前安全检查

只检查文件名和 Git 索引，不为审计打印本地配置、数据库或 Key 内容：

```bash
git status --short
git status --short --ignored
git diff --check
git ls-files | rg '(^|/)(\.env|config\.yaml)$|\.(db|sqlite|sqlite3|pem|key|p12|pfx)$'
```

最后一条正常应无输出。`.gitignore` 已排除运行时配置、环境变量文件、凭证、数据库、用户数据、
导出、依赖、构建与测试产物；脱敏模板仍可提交。已经进入 Git 历史的敏感文件不会因后来加入
`.gitignore` 自动消失，公开前仍需单独检查历史。
