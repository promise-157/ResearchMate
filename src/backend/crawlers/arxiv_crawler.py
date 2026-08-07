"""
arXiv API 爬虫。使用 arXiv 官方 API (Atom XML) 获取论文元数据。
文档: https://info.arxiv.org/help/api/
"""
import re
import xml.etree.ElementTree as ET
from typing import List, Dict
from urllib.parse import urlparse

import httpx

from crawlers.base import BaseCrawler
from config import get as config_get

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
ARXIV_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS2 = "{http://arxiv.org/schemas/atom}"


class ArxivCrawler(BaseCrawler):
    @property
    def name(self) -> str:
        return "arxiv"

    def can_handle(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        return ((host == "arxiv.org" or host.endswith(".arxiv.org")) and
                bool(re.fullmatch(r"/list/[\w.-]+(?:/(?:recent|new|pastweek))?/", parsed.path.rstrip("/") + "/")))

    async def crawl(self, url: str, mode: str = "new", keywords: str = "", sort_mode: str = "newest") -> List[Dict]:
        """
        从 arXiv URL 爬取论文。
        """
        category, _ = self._parse_list_url(url)
        if not category:
            raise ValueError("Unsupported arXiv URL; use a category list URL")
        return await self._crawl_by_category(category, mode, keywords, sort_mode)

    async def _crawl_by_category(self, category: str, mode: str = "new", keywords: str = "", sort_mode: str = "newest") -> List[Dict]:
        """按分类爬取论文，支持关键词搜索和排序。"""
        max_results = config_get("crawler", "max_papers_per_source") or 50

        # 构建查询
        query_parts = [f"cat:{category}"]
        if keywords:
            query_parts.append(f"all:{keywords}")
        query = " AND ".join(query_parts)

        # 排序参数
        if sort_mode == "hottest":
            sort_by = "relevance"
            sort_order = "descending"
        else:
            sort_by = "submittedDate"
            sort_order = "descending"

        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        timeout = config_get("crawler", "timeout") or 30
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(ARXIV_API_BASE, params=params)
            resp.raise_for_status()

        return self._parse_atom(resp.text, category)

    def _parse_list_url(self, url: str) -> tuple:
        """从 arXiv 列表 URL 中提取分类和年份。"""
        parsed = urlparse(url)
        path = parsed.path

        # /list/cs.AI/recent, /new, /pastweek, or category root.
        m = re.fullmatch(r'/list/([\w.-]+)(?:/(recent|new|pastweek))?/?', path)
        if m:
            category = m.group(1)
            return category, None

        # /abs/1706.03762 → 单个论文
        return None, None

    def _parse_atom(self, xml_text: str, default_category: str = None) -> List[Dict]:
        """解析 arXiv API 返回的 Atom XML。"""
        root = ET.fromstring(xml_text)
        papers = []

        for entry in root.findall(f"{ARXIV_NS}entry"):
            title = self._text(entry, f"{ARXIV_NS}title")
            title = re.sub(r'\s+', ' ', title).strip()

            # 作者
            authors = []
            for author in entry.findall(f"{ARXIV_NS}author"):
                name = self._text(author, f"{ARXIV_NS}name")
                if name:
                    authors.append(name)

            # 摘要
            abstract = self._text(entry, f"{ARXIV_NS}summary")
            abstract = re.sub(r'\s+', ' ', abstract).strip()

            # arXiv ID — 从 id 标签提取
            id_url = self._text(entry, f"{ARXIV_NS}id")
            arxiv_id = None
            if id_url:
                m = re.search(r'abs/([\w.-]+)', id_url)
                if m:
                    arxiv_id = m.group(1)

            paper_url = id_url or None

            # 分类
            categories = []
            for cat in entry.findall(f"{ARXIV_NS}category"):
                term = cat.attrib.get("term", "")
                if term:
                    categories.append(term)
            journal_name = ", ".join(categories) if categories else (default_category or "arXiv")

            # 发布时间
            published = self._text(entry, f"{ARXIV_NS}published")
            publish_year = int(published[:4]) if published else None

            # 检测 GitHub 链接
            has_code, code_url = self._detect_code(abstract)

            # 获取评论 (可能含 DOI 或期刊引用)
            comment = self._text(entry, f"{ARXIV_NS2}journal_ref")
            if comment and not journal_name.startswith(comment):
                pass  # journal_ref 可以提供更精确的期刊名

            papers.append({
                "title": title,
                "authors": self._to_json_str(authors),
                "abstract": abstract,
                "journal_name": journal_name,
                "publish_year": publish_year,
                "arxiv_id": arxiv_id,
                "paper_url": paper_url,
                "has_code": has_code,
                "code_url": code_url,
            })

        return papers

    def _detect_code(self, text: str) -> tuple:
        """从文本中检测代码仓库链接。"""
        if not text:
            return False, None
        patterns = [
            r'https?://github\.com/[\w.-]+/[\w.-]+',
            r'https?://gitlab\.com/[\w.-]+/[\w.-]+',
            r'https?://bitbucket\.org/[\w.-]+/[\w.-]+',
            r'https?://huggingface\.co/[\w.-]+/[\w.-]+',
            r'https?://github\.io/[\w.-]+',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return True, m.group(0)
        return False, None

    def _text(self, element, tag) -> str:
        """安全获取 XML 元素文本。"""
        el = element.find(tag)
        return el.text if el is not None and el.text else ""

    def _to_json_str(self, lst: List[str]) -> str:
        """将列表转为 JSON 字符串，存储到 SQLite。"""
        import json
        return json.dumps(lst, ensure_ascii=False)
