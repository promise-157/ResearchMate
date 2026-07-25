"""
通用网页爬虫。用 BeautifulSoup 从任意网页提取论文元数据。
支持: meta 标签 (Highwire/Google Scholar)、JSON-LD (Schema.org)、常规 HTML。
"""
import re
import json as json_lib
from typing import List, Dict
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler
from config import get as config_get


class GenericCrawler(BaseCrawler):
    @property
    def name(self) -> str:
        return "generic"

    def can_handle(self, url: str) -> bool:
        # 兜底：不满足任何专用爬虫条件的 URL 都由它处理
        return True

    async def crawl(self, url: str, mode: str = "new", keywords: str = "", sort_mode: str = "newest") -> List[Dict]:
        timeout = config_get("crawler", "timeout") or 30
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "ResearchMate/0.1 (academic research tool)"},
            )
            resp.raise_for_status()

        html = resp.text
        soup = BeautifulSoup(html, "lxml")
        papers = []

        # 策略 1: meta 标签 (Highwire Press / Google Scholar 格式)
        meta_papers = self._extract_from_meta(soup, url)
        if meta_papers:
            papers.extend(meta_papers)

        # 策略 2: JSON-LD (Schema.org)
        ld_papers = self._extract_from_jsonld(soup, url)
        for p in ld_papers:
            if not any(existing.get("title") == p["title"] for existing in papers):
                papers.append(p)

        # 策略 3: 如果前两种都没提取到，尝试遍历常见论文列表结构
        if not papers:
            papers = self._extract_from_listing(soup, url)

        return papers

    def _extract_from_meta(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """从 <meta> 标签提取论文信息。"""
        meta_tags = {tag.get("name", ""): tag.get("content", "")
                     for tag in soup.find_all("meta") if tag.get("name")}

        title = meta_tags.get("citation_title", "")
        if not title:
            return []

        authors = []
        for key in sorted(meta_tags.keys()):
            if key.startswith("citation_author") and not key.endswith(("_orcid", "_email")):
                authors.append(meta_tags[key])

        abstract = meta_tags.get("citation_abstract", "")
        if not abstract:
            abstract = meta_tags.get("description", "")[:2000]

        journal = meta_tags.get("citation_journal_title", "")
        date_str = meta_tags.get("citation_date", "")
        publish_year = int(date_str[:4]) if len(date_str) >= 4 else None
        paper_url = meta_tags.get("citation_abstract_html_url", "")

        arxiv_id = None
        if paper_url:
            m = re.search(r'arxiv\.org/abs/([\w.-]+)', paper_url)
            if m:
                arxiv_id = m.group(1)
        if not arxiv_id and abstract:
            m = re.search(r'arXiv:(\d{4}\.\d{4,})', abstract)
            if m:
                arxiv_id = m.group(1)

        has_code, code_url = self._detect_code(abstract)

        return [{
            "title": title,
            "authors": json_lib.dumps(authors, ensure_ascii=False),
            "abstract": abstract[:3000],
            "journal_name": journal or self._guess_journal(base_url),
            "publish_year": publish_year,
            "arxiv_id": arxiv_id,
            "paper_url": paper_url or None,
            "has_code": has_code,
            "code_url": code_url,
        }]

    def _extract_from_jsonld(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """从 JSON-LD 提取论文信息。"""
        papers = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json_lib.loads(script.string or "")
            except (json_lib.JSONDecodeError, TypeError):
                continue

            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in ("ScholarlyArticle", "Article"):
                    title = item.get("name") or item.get("headline") or ""
                    authors = []
                    for a in item.get("author", []):
                        if isinstance(a, dict):
                            authors.append(a.get("name", ""))
                        elif isinstance(a, str):
                            authors.append(a)

                    abstract = item.get("description") or ""
                    journal = item.get("publisher", {}).get("name", "") if isinstance(item.get("publisher"), dict) else ""
                    date_str = item.get("datePublished", "")
                    publish_year = int(date_str[:4]) if len(date_str) >= 4 else None
                    paper_url = item.get("url", "")

                    has_code, code_url = self._detect_code(abstract)

                    papers.append({
                        "title": title,
                        "authors": json_lib.dumps(authors, ensure_ascii=False),
                        "abstract": abstract[:3000],
                        "journal_name": journal or self._guess_journal(base_url),
                        "publish_year": publish_year,
                        "arxiv_id": None,
                        "paper_url": paper_url or None,
                        "has_code": has_code,
                        "code_url": code_url,
                    })

        return papers

    def _extract_from_listing(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """遍历常见论文列表结构：<article>、<li class='paper'>、<div class='paper'> 等。"""
        papers = []

        # 常见论文容器选择器
        candidates = soup.select(
            "article, li.paper, div.paper, tr.paper-row, div.pub-row, "
            "div.result-item, div.search-result, li[class*='paper'], div[class*='paper-item'], "
            "div.listing, div.card"
        )

        for cand in candidates[:50]:  # 最多取 50 个候选项
            title_tag = cand.find(["h1", "h2", "h3", "h4", "a"], href=re.compile(r'paper|abs|article|publication'))
            if not title_tag:
                title_tag = cand.find("a")

            title = title_tag.get_text(strip=True) if title_tag else ""
            if len(title) < 10:
                continue

            link = title_tag.get("href", "") if title_tag and title_tag.name == "a" else ""
            if link:
                link = urljoin(base_url, link)

            # 尝试在容器中找作者和摘要
            text = cand.get_text(" ", strip=True)[:3000]
            has_code, code_url = self._detect_code(text)

            # 尝试提取 arXiv ID
            arxiv_id = None
            m = re.search(r'arXiv:(\d{4}\.\d{4,})', text)
            if m:
                arxiv_id = m.group(1)

            papers.append({
                "title": title[:500],
                "authors": "[]",
                "abstract": text[:2000],
                "journal_name": self._guess_journal(base_url),
                "publish_year": self._guess_year(text),
                "arxiv_id": arxiv_id,
                "paper_url": link or None,
                "has_code": has_code,
                "code_url": code_url,
            })

        return papers

    def _detect_code(self, text: str) -> tuple:
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

    def _guess_journal(self, url: str) -> str:
        """从域名猜测期刊名称。"""
        domain = urlparse(url).netloc
        domain = re.sub(r'^www\.', '', domain)
        parts = domain.split(".")
        if len(parts) >= 2:
            return parts[-2].upper()
        return domain

    def _guess_year(self, text: str) -> int:
        """从文本中猜测发表年份。"""
        m = re.search(r'\b(20\d{2})\b', text)
        return int(m.group(1)) if m else None
