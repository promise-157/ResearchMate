"""
处理器基类。分析器、摘要器等都继承此类。
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseProcessor(ABC):
    """所有处理器的抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """处理器名称。"""
        ...

    @abstractmethod
    async def analyze(self, paper: Dict) -> Dict:
        """
        分析单篇论文，返回分析结果。

        Args:
            paper: 论文字典（需含 title, abstract）

        Returns:
            Dict with keys: has_code, code_url, innovation, technologies, analyzed
        """
        ...

    @abstractmethod
    async def review(self, papers: List[Dict]) -> Optional[str]:
        """对一批论文进行汇总点评。"""
        ...

    async def review_with_prompt(self, prompt: str) -> Optional[str]:
        """直接发送自定义 prompt。可选实现。"""
        return None
