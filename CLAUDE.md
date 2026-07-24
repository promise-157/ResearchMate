# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

**⚠️ 每次新会话开始，先读 `src/temp/task-plan.md` 了解当前进度。不要重复已完成的任务。**

---

## Python 环境 (Miniconda)

**必须使用 miniconda 环境，不要使用系统 Python。**

- 项目专用环境名：`researchmate`（Python 3.11）
- 激活方式：
  ```bash
  source /home/promise/miniconda3/etc/profile.d/conda.sh
  conda activate researchmate
  ```
- 或者简化为：
  ```bash
  conda activate researchmate
  ```

### ROS PYTHONPATH 冲突注意事项

用户的 `.bashrc` 中 ROS noetic 会设置 `PYTHONPATH`，与 conda 冲突。用户提供了两个别名：
- `start_conda` — 备份并清空 PYTHONPATH，然后 `conda activate base`
- `stop_conda` — conda deactivate 并恢复 PYTHONPATH

当需要激活本项目 conda 环境时，**在 `researchmate` 环境激活前确保 PYTHONPATH 已 unset**：
```bash
unset PYTHONPATH
conda activate researchmate
```

安装新 Python 包时使用 `conda install` 或 `pip install`（在 researchmate 环境内）。

---

## 环境上下文（来自 ~/.bashrc）

在执行任何可能依赖系统环境的命令之前，**必须先读取 `/home/promise/.bashrc`** 了解当前环境配置。关键信息：

| 项目 | 路径/值 |
|------|---------|
| Miniconda | `/home/promise/miniconda3/` |
| ROS | `/opt/ros/noetic/` |
| CUDA | `/usr/local/cuda-12.8/` |
| NVM (Node) | `$NVM_DIR` (`~/.nvm/`) |
| HTTP 代理 | `http://127.0.0.1:7890` |
| Gazebo/PX4 | 多个相关环境变量 |

### 代理与终端限制

用户的 `~/.gitconfig` 配置了 `http.proxy = http://127.0.0.1:7890`（Clash/v2ray），Bash 工具环境也能访问。但 **Claude Code 的 Bash 工具没有 TTY（交互式终端）**，任何需要交互输入的命令（如 `git push` 弹出认证提示）都会失败。

- **`git push`/`git pull` 由用户在终端手动执行**，Bash 工具不要尝试
- 如果 Bash 命令因 TTY 失败，直接告诉用户去终端执行，**禁止绕道/折腾**
- 网络验证用 `curl`/`timeout bash` 等非交互方式确认即可

---

## 铁律（违反这些比写 bug 更严重）

### 1. 永远不要碰凭证和认证配置
- **禁止写入、修改、创建任何包含 token、密码、密钥的文件**（包括 `/tmp/`、项目内、任何位置）
- **禁止修改 `git remote`、`~/.gitconfig`、`~/.ssh/`、git credential 相关配置**
- **禁止使用 `$GITHUB_TOKEN` 或其他凭证环境变量** — 那是敏感信息
- 如果 git push/pull 失败，一句话告诉用户：**"终端里跑 `git push`，别让我碰。"**

### 2. 不要无谓折腾已确认的环境问题
- 用户已经说了他的终端能正常 work → **信他，别修**
- Bash 工具有本质限制（非交互式），承认限制，不要找 workaround
- 不要在同一个问题上尝试超过 2 次命令

### 3. 危险操作必须确认
- `git push --force` / `git push --force-with-lease`
- `rm -rf` 删除非临时文件/目录
- 修改 `~/.bashrc`、`~/.profile` 等系统配置文件
- 操作本项目外的文件

### 4. 绝对不要随意回退版本
- 没有 commit 的修改，回退（`git reset --hard`、`git checkout --`、删除）**永久丢失**
- 破坏性操作前先 `git stash` 或让用户 commit

### 5. 数据安全
- `src/data/` 已 gitignored，勿删
- `src/temp/` 可修改但勿删目录

---

## 项目结构

```
ResearchMate/
├── src/
│   ├── backend/            # Python 后端（FastAPI + SQLite）
│   │   ├── api/routes/     # REST API 路由
│   │   ├── crawlers/       # 爬虫插件（基类在 base.py）
│   │   ├── processors/     # 数据分析处理器
│   │   └── storage/        # 数据库层
│   ├── frontend/           # Vue 3 + Vite 前端
│   │   └── src/
│   │       ├── api/        # 后端 API 调用封装
│   │       ├── components/ # 可复用组件
│   │       ├── router/     # 前端路由
│   │       └── views/      # 页面
│   ├── config/             # 用户配置文件
│   ├── data/               # 爬取数据（gitignored）
│   ├── scripts/            # 一次性工具脚本
│   └── temp/               # 设计文档和临时笔记
├── CLAUDE.md               # 本文件
├── README.md
├── CHANGELOG.md
└── LICENSE.txt
```

---

## 技术栈速查

| 层级 | 技术 |
|------|------|
| 后端语言 | Python 3.11 (miniconda) |
| Web 框架 | FastAPI |
| 数据库 | SQLite (内置) |
| 爬虫 | httpx + BeautifulSoup4 + arxiv |
| 任务调度 | APScheduler |
| NLP 分析 | jieba + scikit-learn |
| 前端框架 | Vue 3 + Vite |
| UI 组件库 | Element Plus |
| 可视化 | ECharts |

---

## 扩展性设计

所有爬虫继承 `BaseCrawler`，所有处理器继承 `BaseProcessor`。添加新功能只需：
1. 在对应目录创建新文件
2. 继承基类实现接口
3. 在 registry 中注册

详见 `src/temp/design-plan.md`。
