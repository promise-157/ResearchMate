"""
处理器注册表。管理所有处理器实例。
"""
from typing import List, Optional
from processors.base import BaseProcessor

_registry: List[BaseProcessor] = []


def register(processor: BaseProcessor):
    _registry.append(processor)
    print(f"[processor] registered: {processor.name}")


def get(name: str) -> Optional[BaseProcessor]:
    for p in _registry:
        if p.name == name:
            return p
    return None


def init_registry():
    from processors.llm_analyzer import LLMAnalyzer
    register(LLMAnalyzer())
