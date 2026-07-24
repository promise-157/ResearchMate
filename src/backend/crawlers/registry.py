"""
爬虫注册表。管理所有爬虫实例，根据 URL 匹配合适的爬虫。
"""
from typing import List, Optional
from crawlers.base import BaseCrawler

_registry: List[BaseCrawler] = []


def register(crawler: BaseCrawler):
    """注册一个爬虫。"""
    _registry.append(crawler)
    print(f"[crawler] registered: {crawler.name}")


def find_crawler(url: str) -> Optional[BaseCrawler]:
    """根据 URL 查找能处理它的爬虫。先精确匹配，后通配。"""
    for crawler in _registry:
        if crawler.can_handle(url):
            return crawler
    return None


def list_crawlers() -> List[str]:
    """列出所有已注册的爬虫名称。"""
    return [c.name for c in _registry]


def init_registry():
    """初始化注册表 — 注册所有内置爬虫。"""
    from crawlers.arxiv_crawler import ArxivCrawler
    from crawlers.generic_crawler import GenericCrawler

    register(ArxivCrawler())
    register(GenericCrawler())
