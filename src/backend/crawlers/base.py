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
    async def crawl(self, url: str, mode: str = "new", keywords: str = "", sort_mode: str = "newest") -> List[Dict]:
        """
        爬取指定 URL，返回论文列表。

        Args:
            url: 期刊源 URL
            mode: "new" (仅新增) 或 "all" (全部重新爬取)
            keywords: 空格分隔的搜索关键词
            sort_mode: "newest" (最新) 或 "hottest" (最热)

        Returns:
            List[Dict]: 论文信息列表
        """
        ...
