"""
关键词自动提取。不使用 AI，纯本地规则 + 词库匹配。
提取技术术语：英文缩写、专有名词、预置词库匹配。
"""
import re
import json
from collections import Counter
from pathlib import Path
from typing import List, Tuple

# === 预置 ML/DL 术语词库 ===
# 补充规则匹配不到但常见的术语
TECH_TERMS = {
    # 模型架构
    "transformer", "attention", "self-attention", "multi-head attention",
    "cnn", "rnn", "lstm", "gru", "gan", "vae", "diffusion model",
    "u-net", "resnet", "vit", "vision transformer", "mlp", "mamba",
    "state space model", "moe", "mixture of experts", "encoder", "decoder",
    "autoencoder", "gan", "graph neural network", "gnn", "reinforcement learning",
    "rlhf", "ppo", "dqn", "actor-critic", "policy gradient",
    # 训练技术
    "fine-tuning", "pre-training", "transfer learning", "few-shot", "zero-shot",
    "in-context learning", "prompt engineering", "chain-of-thought", "cot",
    "lora", "qlora", "adapter", "prefix tuning", "p-tuning",
    "distillation", "knowledge distillation", "pruning", "quantization",
    "mixed precision", "gradient checkpointing", "data augmentation",
    # NLP
    "tokenization", "wordpiece", "bpe", "sentencepiece", "embedding",
    "bert", "gpt", "llama", "t5", "bart", "roberta", "clip",
    "rag", "retrieval-augmented generation", "vector database",
    "semantic search", "text classification", "ner", "named entity recognition",
    "sentiment analysis", "machine translation", "summarization",
    "question answering", "language model", "llm", "large language model",
    # CV
    "object detection", "image classification", "segmentation", "semantic segmentation",
    "instance segmentation", "object tracking", "pose estimation",
    "image generation", "style transfer", "super-resolution",
    "depth estimation", "optical flow", "nerf", "gaussian splatting",
    "3d reconstruction", "point cloud", "multi-modal", "vision-language",
    # 优化
    "sgd", "adam", "adamw", "learning rate", "batch normalization",
    "layer normalization", "dropout", "weight decay", "gradient clipping",
    "backpropagation", "loss function", "cross-entropy", "contrastive loss",
    # 评估
    "benchmark", "sota", "ablation", "hyperparameter",
    # 应用领域
    "autonomous driving", "medical imaging", "nlp", "natural language processing",
    "computer vision", "speech recognition", "recommender system",
    "time series", "anomaly detection", "generative ai",
    # 框架/工具
    "pytorch", "tensorflow", "jax", "huggingface", "cuda",
    "deepspeed", "fsdp", "vllm",
}

# 构建正则：匹配英文技术缩写（连续大写字母，2-6位）和驼峰命名
_RE_ABBR = re.compile(r'\b[A-Z]{2,6}\b')
_RE_CAMEL = re.compile(r'\b[a-z]+[A-Z][a-zA-Z]*\b')
_RE_ARXIV_ID = re.compile(r'\b\d{4}\.\d{4,}\b')  # 过滤 arXiv ID


def extract_keywords(title: str, abstract: str) -> Tuple[List[str], List[str]]:
    """
    从标题和摘要中提取关键词和技术术语。

    返回: (keywords, technologies)
      - keywords: 技术关键词（用于分组和筛选）
      - technologies: 具体技术/方法名（更精确）
    """
    text = f"{title} {abstract}"
    text_clean = _RE_ARXIV_ID.sub("", text)

    keywords = []
    technologies = []

    # 1. 预置词库匹配
    text_lower = text_clean.lower()
    for term in TECH_TERMS:
        if term in text_lower:
            # 短的进 technologies，作为精确技术标签
            if len(term) <= 20:
                technologies.append(term)
            else:
                keywords.append(term)

    # 2. 正则提取缩写
    abbrs = _RE_ABBR.findall(text_clean)
    for a in abbrs:
        if a not in ("The", "We", "Our", "In", "This", "These", "Those",
                     "It", "Its", "For", "And", "Are", "Has", "Can",
                     "With", "From", "How", "New", "Use", "Used"):
            keywords.append(a.lower())

    # 3. 驼峰命名
    camels = _RE_CAMEL.findall(text_clean)
    for c in camels:
        if len(c) >= 4:
            technologies.append(c)

    # 去重 + 清理
    keywords = _dedup(keywords)
    technologies = _dedup(technologies)

    # 合并：technologies 作为更精确的子集
    # keywords 包含 technologies + 额外的粗粒度关键词
    all_kw = _dedup(keywords + technologies)

    return all_kw[:20], technologies[:10]


def extract_batch(papers: List[dict]) -> Counter:
    """
    批量提取，返回全局关键词计数。
    papers: [{"title": ..., "abstract": ...}, ...]
    """
    counter = Counter()
    for paper in papers:
        kws, _ = extract_keywords(paper.get("title", ""), paper.get("abstract", ""))
        for kw in kws:
            counter[kw] += 1
    return counter


def extract_for_paper(paper: dict) -> dict:
    """提取单篇论文的关键词，返回可存入DB的格式。"""
    kws, techs = extract_keywords(paper.get("title", ""), paper.get("abstract", ""))
    return {
        "auto_keywords": json.dumps(kws, ensure_ascii=False),
        "auto_technologies": json.dumps(techs, ensure_ascii=False),
    }


def _dedup(items: List[str]) -> List[str]:
    """去重并保持顺序。"""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
