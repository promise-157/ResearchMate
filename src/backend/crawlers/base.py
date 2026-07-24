"""
爬虫基类。所有爬虫继承此类，实现 can_handle / crawl。
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseCrawler(ABC):
    """所有爬虫的抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """爬虫名称，如 'arxiv'、'generic_html'。"""
        ...

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """判断此爬虫能否处理给定 URL。"""
        ...

    @abstractmethod
    async def crawl(self, url: str, mode: str = "new") -> List[Dict]:
        """
        爬取指定 URL，返回论文列表。

        Args:
            url: 期刊源 URL
            mode: "new" (仅新增) 或 "all" (全部重新爬取)

        Returns:
            List[Dict]: 论文信息列表，每条包含:
                - title: str
                - authors: str (JSON 数组字符串)
                - abstract: str
                - journal_name: str
                - publish_year: int
                - arxiv_id: str | None
                - paper_url: str | None
                - has_code: bool
                - code_url: str | None
        """
        ...
