"""
关键词自动提取。不使用 AI，纯本地规则 + 词库匹配。
提取技术术语：英文缩写、专有名词、预置词库匹配。
"""
import re
import json
from collections import Counter
from typing import List, Tuple

# === 预置 ML/DL 术语词库 ===
# 补充规则匹配不到但常见的术语
TECH_TERMS = {
    # 模型架构
    "transformer", "attention", "self-attention", "multi-head attention",
    "cnn", "rnn", "lstm", "gru", "gan", "vae", "diffusion model",
    "u-net", "resnet", "vit", "vision transformer", "mlp", "mamba",
    "state space model", "moe", "mixture of experts", "encoder", "decoder",
    "autoencoder", "graph neural network", "gnn", "reinforcement learning",
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

# 构建正则
_RE_ABBR = re.compile(r'\b[A-Z]{3,6}\b')           # 最少3个字符的缩写
_RE_CAMEL = re.compile(r'\b[a-z]+[A-Z][a-zA-Z]*\b')
_RE_ARXIV_ID = re.compile(r'\b\d{4}\.\d{4,}\b')

# 非技术常用词黑名单（即使是大写也不应该是技术关键词）
_NON_TECH_WORDS = {
    "THE", "WE", "OUR", "IN", "THIS", "THESE", "THOSE", "IT", "ITS",
    "FOR", "AND", "ARE", "HAS", "CAN", "WITH", "FROM", "HOW", "NEW",
    "USE", "USED", "USING", "ONE", "TWO", "ALL", "NOT", "BUT", "ALSO",
    "THAT", "THAN", "THEN", "WHEN", "WERE", "BEEN", "BEING", "DOES",
    "WILL", "WOULD", "COULD", "SHOULD", "MAY", "MIGHT", "MUST",
    "DUE", "VIA", "PER", "BASED", "GIVEN", "HOWEVER", "THUS",
    "YET", "STILL", "JUST", "ONLY", "EVEN", "MUCH",
    "WELL", "FIRST", "NEXT", "LAST", "SAME", "SUCH", "EACH",
    "BOTH", "FEW", "MORE", "MOST", "LESS", "MANY", "SOME",
    "ANY", "NO", "NONE", "OTHER", "OWN", "MAIN", "REAL",
    "LARGE", "SMALL", "BEST", "BETTER", "HIGH", "LOW",
    "KEY", "SET", "CASE", "PART", "FORM", "NUMBER", "NOVEL",
    "PAPER", "WORK", "RESULT", "METHOD", "APPROACH", "MODEL",
    "DATA", "TASK", "EXAMPLE", "TABLE", "FIGURE", "ET", "AL",
    "VARIOUS", "DIFFERENT", "IMPORTANT", "SIGNIFICANT",
    "PROPOSED", "EXISTING", "PREVIOUS", "RECENT",
    "PC", "MM", "PIE", "AI", "CI", "CD",
}


def extract_keywords(title: str, abstract: str) -> Tuple[List[str], List[str]]:
    """从标题和摘要中提取关键词和技术术语。"""
    text = f"{title} {abstract}"
    text_clean = _RE_ARXIV_ID.sub("", text)
    text_lower = text_clean.lower()

    keywords = []
    technologies = []

    # 1. 预置词库匹配（优先级最高）
    for term in TECH_TERMS:
        if term in text_lower:
            if len(term) <= 20:
                technologies.append(term)
            else:
                keywords.append(term)

    # 2. 正则提取缩写（>=3 字符，且不在黑名单）
    abbrs = _RE_ABBR.findall(text_clean)
    for a in abbrs:
        upper = a.upper()
        if upper not in _NON_TECH_WORDS:
            keywords.append(a.lower())

    # 3. 驼峰命名（>=4 字符）
    camels = _RE_CAMEL.findall(text_clean)
    for c in camels:
        if len(c) >= 4 and c.lower() not in _NON_TECH_WORDS:
            technologies.append(c)

    # 4. 去重 + 限制数量
    keywords = _dedup(keywords)
    technologies = _dedup(technologies)
    all_kw = _dedup(technologies + keywords)

    return all_kw[:20], technologies[:8]


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
