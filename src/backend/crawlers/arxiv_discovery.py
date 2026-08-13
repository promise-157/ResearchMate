"""Bounded arXiv public API discovery adapter for review candidates."""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "application/atom+xml", "application/xml", "text/xml",
}


@dataclass(frozen=True)
class DiscoveredRecord:
    title: str
    content_text: str
    summary: str
    source_url: str
    source_facts: dict[str, Any]


class ArxivDiscoveryCollector:
    name = "arxiv_api"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    async def search(self, query: str, limit: int) -> list[DiscoveredRecord]:
        timeout = httpx.Timeout(20.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            transport=self.transport,
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "ResearchMate/0.1 (local research workspace)"},
        ) as client:
            async with client.stream("GET", ARXIV_API_URL, params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": limit,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"arXiv API 返回 HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "").split(";", 1)[0]
                if content_type.strip().lower() not in ALLOWED_CONTENT_TYPES:
                    raise RuntimeError("arXiv API 返回了非 Atom XML 内容")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("arXiv API 响应超过 2 MB 限制")
        try:
            xml_text = bytes(content).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise RuntimeError("arXiv API 返回了无法按 UTF-8 解码的 Atom XML") from exc
        return self.parse_atom(xml_text, limit=limit)

    def parse_atom(self, xml_text: str, *, limit: int) -> list[DiscoveredRecord]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise RuntimeError("arXiv API 返回了无效 Atom XML") from exc
        records = []
        fetched_at = datetime.now(timezone.utc).isoformat()
        for entry in root.findall(f"{ATOM}entry")[:limit]:
            title = self._text(entry, "title")
            abstract = self._text(entry, "summary")
            source_url = self._text(entry, "id")
            if not title or not abstract or not re.match(r"^https?://arxiv\.org/abs/", source_url):
                continue
            source_url = re.sub(r"^http://", "https://", source_url)
            authors = [
                self._child_text(author, "name")
                for author in entry.findall(f"{ATOM}author")
            ]
            authors = [author for author in authors if author]
            categories = [node.attrib.get("term", "") for node in entry.findall(f"{ATOM}category")]
            arxiv_id = source_url.rsplit("/", 1)[-1]
            content_text = f"{title}\n\n{abstract}"
            records.append(DiscoveredRecord(
                title=title[:300],
                content_text=content_text,
                summary=abstract[:300],
                source_url=source_url,
                source_facts={
                    "collector": self.name,
                    "source_api": ARXIV_API_URL,
                    "arxiv_id": arxiv_id,
                    "authors": authors,
                    "categories": [value for value in categories if value],
                    "published": self._text(entry, "published") or None,
                    "fetched_at": fetched_at,
                    "suggested_item_type": "paper",
                },
            ))
        return records

    @staticmethod
    def _child_text(element: ET.Element, name: str) -> str:
        node = element.find(f"{ATOM}{name}")
        return re.sub(r"\s+", " ", node.text or "").strip() if node is not None else ""

    def _text(self, element: ET.Element, name: str) -> str:
        return self._child_text(element, name)
