# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

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

### 代理与网络限制

用户的 `~/.gitconfig` 配置了 `http.proxy = http://127.0.0.1:7890`（Clash/v2ray）。**Claude Code 的 Bash 工具运行在 VS Code 扩展的非交互式子进程中，可能无法访问该代理**，表现为 `git push`/`git pull`/`curl` 失败并报 `No such device or address`。

- **git push/pull 等网络操作尽量让用户在终端里手动执行**，不要在 Bash 工具中执行
- 用户在终端里 `git push` 可以正常走代理，无需额外认证
- 如果需要在工具中验证网络，先确认代理可达，或使用 `--noproxy '*'` 绕过代理尝试直连

---

## 关键安全规则

### 1. 绝对不要随意回退版本

**如果没有 commit，回退（`git reset --hard`、`git checkout --`、删除文件等）会导致修改永久丢失，无法恢复。**

- 做任何破坏性操作前，先 `git stash` 或 `git commit` 保存当前状态
- 如果要回退已 commit 的版本，先确认用户知道后果
- 不要使用 `git push --force` 除非用户明确要求

### 2. 敏感操作必须确认

以下操作**必须经过用户明确确认**才能执行：
- `git push --force` / `git push --force-with-lease`
- `rm -rf` 删除非临时文件/目录
- 修改 `.gitignore` 外的 `.git` 相关配置
- 修改 `~/.bashrc`、`~/.profile` 等系统配置文件
- 操作 `/home/promise/` 下非本项目目录的文件
- `conda install`、`pip install` 安装大型包（>100MB）

### 3. 数据安全

- `src/data/` 目录存放爬取的数据，已加入 `.gitignore`，不要手动删除
- `src/temp/` 目录存放设计文档和临时笔记，可以修改但不要删除整个目录

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
