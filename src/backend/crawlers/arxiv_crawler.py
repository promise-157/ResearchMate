"""
arXiv API 爬虫。使用 arXiv 官方 API (Atom XML) 获取论文元数据。
文档: https://info.arxiv.org/help/api/
"""
import re
import xml.etree.ElementTree as ET
from typing import List, Dict
from urllib.parse import urlencode, urlparse

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
        return "arxiv.org" in url

    async def crawl(self, url: str, mode: str = "new", keywords: str = "", sort_mode: str = "newest") -> List[Dict]:
        """
        从 arXiv URL 爬取论文。
        """
        category, year = self._parse_list_url(url)

        if category:
            return await self._crawl_by_category(category, year, mode, keywords, sort_mode)
        else:
            return await self._crawl_generic(url, mode)

    async def _crawl_by_category(self, category: str, year: str = None, mode: str = "new", keywords: str = "", sort_mode: str = "newest") -> List[Dict]:
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

    async def _crawl_generic(self, url: str, mode: str = "new") -> List[Dict]:
        """通用爬取 — 尝试从 arXiv 页面提取论文。"""
        timeout = config_get("crawler", "timeout") or 30
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        # 如果是单个论文页 (arxiv.org/abs/...)，直接解析
        text = resp.text
        papers = self._parse_abs_page(text)
        if papers:
            return papers

        # 否则当作列表页
        return self._parse_listing_page(text)

    def _parse_list_url(self, url: str) -> tuple:
        """从 arXiv 列表 URL 中提取分类和年份。"""
        parsed = urlparse(url)
        path = parsed.path

        # /list/cs.AI/recent 或 /list/cs.AI/2024
        m = re.search(r'/list/([\w.-]+)(?:/(\d{4}|recent))?', path)
        if m:
            category = m.group(1)
            year = m.group(2) if m.group(2) and m.group(2) != "recent" else None
            return category, year

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

    def _parse_abs_page(self, html: str) -> List[Dict]:
        """解析单个论文页面 (arxiv.org/abs/xxx)。"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        title_tag = soup.find("h1", class_="title")
        if not title_tag:
            return []
        title = title_tag.get_text(strip=True).replace("Title:", "").strip()

        authors_tag = soup.find("div", class_="authors")
        authors = []
        if authors_tag:
            for a in authors_tag.find_all("a"):
                authors.append(a.get_text(strip=True))

        abstract_tag = soup.find("blockquote", class_="abstract")
        abstract = ""
        if abstract_tag:
            abstract = abstract_tag.get_text(strip=True).replace("Abstract:", "").strip()

        # Detect code in abstract + page
        full_text = abstract + " " + html[:5000]
        has_code, code_url = self._detect_code(full_text)

        return [{
            "title": title,
            "authors": self._to_json_str(authors),
            "abstract": abstract,
            "journal_name": "arXiv",
            "publish_year": None,
            "arxiv_id": None,
            "paper_url": None,
            "has_code": has_code,
            "code_url": code_url,
        }]

    def _parse_listing_page(self, html: str) -> List[Dict]:
        """解析 arXiv 列表页。"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        papers = []

        for dl in soup.find_all("dl"):
            for dt in dl.find_all("dt"):
                link = dt.find("a", href=re.compile(r'/abs/'))
                if not link:
                    continue
                arxiv_id = link.get_text(strip=True).replace("arXiv:", "")
                title = link.get("title", "").strip() or link.get_text(strip=True)

                # Try to find abstract in sibling dd
                dd = dt.find_next_sibling("dd")
                abstract = ""
                authors = []
                if dd:
                    abstract_div = dd.find("div", class_="list-comments")
                    if abstract_div:
                        abstract = abstract_div.get_text(strip=True)[:500]
                    # Authors are usually in the dd text before any div
                    authors_text = dd.get_text(separator=" ", strip=True)
                    # Simple heuristic: text before first div content
                    authors_raw = dd.find(string=True, recursive=False)
                    if authors_raw:
                        authors = [a.strip() for a in authors_raw.split(",") if a.strip()]

                has_code, code_url = self._detect_code(abstract)

                papers.append({
                    "title": title,
                    "authors": self._to_json_str(authors),
                    "abstract": abstract[:2000] if abstract else "",
                    "journal_name": "arXiv",
                    "publish_year": None,
                    "arxiv_id": arxiv_id,
                    "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
                    "has_code": has_code,
                    "code_url": code_url,
                })

        return papers

    def _detect_code(self, text: str) -> tuple:
        """从文本中检测 GitHub 链接。"""
        if not text:
            return False, None
        m = re.search(r'https?://github\.com/[\w.-]+/[\w.-]+', text, re.IGNORECASE)
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
