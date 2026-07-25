# ResearchMate 快速上手

> 5 分钟从零到爬完第一批论文。

---

## 1. 安装（一次性）

```bash
git clone https://github.com/promise-157/ResearchMate.git
cd ResearchMate

# Python 依赖
conda create -n researchmate python=3.11 -y
conda activate researchmate
cd src/backend && pip install -r requirements.txt && cd ../..

# 前端依赖
cd src/frontend && npm install && cd ../..
```

## 2. 启动（一个命令）

```bash
cd src/backend
conda activate researchmate
python run.py
```

首次运行会自动构建前端。浏览器自动打开 → 看到首页。

开发模式（前端热更新）：
```bash
python run.py --dev
# 浏览器打开 http://127.0.0.1:5173
```

## 4. 添加期刊源

1. 点击首页 **「论文中心」** 卡片
2. 点击 **「+ 添加期刊源」**
3. 填入网址，例如 `https://arxiv.org/list/cs.AI/recent`
4. 备注名写 `arXiv AI`，点添加

## 5. 第一次爬取

1. 勾选刚添加的期刊源
2. 模式选 **「仅新论文」**
3. 点 **「开始爬取已选的 1 个源」**
4. 等待进度条走完（约 10-20 秒爬 50 篇）

## 6. 浏览论文

- 每篇一张卡片：标题、作者、期刊、AI 分析
- 🔗 绿色 = 有开源代码，灰色 = 未发现
- 点 **「保存」** → 加入购物车
- 点 **「查看摘要」** → 弹窗看完整摘要
- 顶部筛选栏：搜索、只看有代码的、仅看已保存的

## 7. 启用 AI 分析（可选）

AI 分析需要配置 API Key。三种方式：

### OpenAI
```bash
export RESEARCHMATE_AI_KEY="sk-your-key"
export RESEARCHMATE_AI_MODEL="gpt-4o-mini"
python run.py
```

### DeepSeek
```bash
export RESEARCHMATE_AI_TYPE="deepseek"
export RESEARCHMATE_AI_KEY="sk-your-deepseek-key"
export RESEARCHMATE_AI_MODEL="deepseek-v4-pro"
python run.py
```

### Ollama（本地免费）
```bash
# 先安装 Ollama: https://ollama.com
ollama pull llama3.1:8b

export RESEARCHMATE_AI_TYPE="ollama"
export RESEARCHMATE_AI_BASE_URL="http://localhost:11434/v1"
export RESEARCHMATE_AI_MODEL="llama3.1:8b"
python run.py
```

### Claude
```bash
export RESEARCHMATE_AI_TYPE="claude"
export RESEARCHMATE_AI_KEY="sk-ant-your-key"
export RESEARCHMATE_AI_MODEL="claude-haiku-4-5-20251001"
python run.py
```

配置后重新爬取或等下次爬取，AI 会自动分析摘要并生成批量点评。

## 8. 导出

1. 浏览论文时把感兴趣的加购物车
2. 点右上角 🛒 图标
3. 点 **「复制标题列表」** 或 **「导出 CSV」**

---

## 下一步

- 完整文档：[使用手册](MANUAL.md)
- 更多期刊源格式、常见问题 → 详见 MANUAL.md 第 7 节
