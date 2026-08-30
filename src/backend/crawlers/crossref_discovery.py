"""Bounded Crossref discovery adapter for formally published IEEE records."""
import asyncio
import html
import json
import math
import re
from urllib.parse import quote
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from crawlers.discovery_models import DiscoveredRecord


CROSSREF_API_URL = "https://api.crossref.org/works"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PAGES = 5
MAX_PAGE_SIZE = 20
ALLOWED_CONTENT_TYPES = {"application/json", "application/vnd.crossref-api-message+json"}
IEEE_PREFIX = "10.1109/"


@dataclass(frozen=True)
class CrossrefResult:
    records: list[DiscoveredRecord]
    total_results: int
    skipped_count: int
    truncated: bool


def normalize_doi(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    normalized = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", normalized)
    normalized = normalized.strip().rstrip(".,;)")
    if not re.fullmatch(r"10\.\d{4,9}/\S+", normalized):
        return None
    return normalized


class CrossrefDiscoveryCollector:
    name = "crossref_ieee"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    async def search(self, query: dict[str, Any]) -> CrossrefResult:
        exact_doi = normalize_doi(query.get("query")) if query.get("intent") == "exact" else None
        if exact_doi:
            return await self._search_doi(exact_doi, query)
        limit = query["limit"]
        page_size = min(MAX_PAGE_SIZE, limit)
        records: list[DiscoveredRecord] = []
        seen: set[str] = set()
        skipped = 0
        total_results = 0
        cursor = "*"
        pages = 0
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0), transport=self.transport, follow_redirects=False,
            trust_env=False, headers={"User-Agent": "ResearchMate/0.1 (local research workspace)"},
        ) as client:
            while len(records) < limit and pages < MAX_PAGES:
                params = self._params(query, page_size, cursor)
                response = await self._request_with_retry(client, params)
                payload = await self._read_json(response)
                message = payload.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("items"), list):
                    raise RuntimeError("Crossref 返回了无效 JSON 结构")
                total_results = max(total_results, int(message.get("total-results") or 0))
                items = message["items"]
                pages += 1
                for item in items:
                    record = self._parse_item(item, query, len(records) + skipped + 1)
                    if record is None:
                        skipped += 1
                        continue
                    canonical_id = record.source_facts["canonical_id"]
                    if canonical_id in seen:
                        skipped += 1
                        continue
                    seen.add(canonical_id)
                    records.append(record)
                    if len(records) >= limit:
                        break
                next_cursor = message.get("next-cursor")
                if not items or not isinstance(next_cursor, str) or not next_cursor:
                    break
                cursor = next_cursor
        truncated = total_results > len(records) or pages >= MAX_PAGES and len(records) < limit
        return CrossrefResult(records, total_results, skipped, truncated)

    def _params(self, query: dict[str, Any], rows: int, cursor: str) -> dict[str, str | int]:
        filters = ["prefix:10.1109"]
        if query["intent"] != "exact":
            date_filter = "pub" if query["date_basis"] == "published" else "index"
            filters.extend([
                f"from-{date_filter}-date:{query['date_from']}",
                f"until-{date_filter}-date:{query['date_to']}",
            ])
        if query["scope"] == "journal":
            filters.append("type:journal-article")
        if query.get("issn"):
            filters.append(f"issn:{query['issn']}")
        params: dict[str, str | int] = {
            "filter": ",".join(filters), "rows": rows, "cursor": cursor,
            "select": "DOI,title,author,container-title,type,published,published-online,published-print,issued,created,indexed,URL,ISSN,score,abstract",
        }
        if query.get("query"):
            query_key = {
                "exact": "query.title", "author": "query.author",
            }.get(query["intent"], "query.bibliographic")
            params[query_key] = query["query"]
        if query.get("container_title"):
            params["query.container-title"] = query["container_title"]
        params["sort"] = {"relevance": "score", "published": "published", "indexed": "indexed"}[query["sort"]]
        params["order"] = "desc"
        return params

    async def _request_with_retry(
        self, client: httpx.AsyncClient, params: dict[str, Any], *, url: str = CROSSREF_API_URL
    ) -> httpx.Response:
        for attempt in range(3):
            async with client.stream("GET", url, params=params) as response:
                if response.status_code not in {429, 503}:
                    if response.status_code != 200:
                        raise RuntimeError(f"Crossref API 返回 HTTP {response.status_code}")
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_RESPONSE_BYTES:
                            raise RuntimeError("Crossref API 响应超过 2 MB 限制")
                    decoded_headers = {
                        key: value for key, value in response.headers.items()
                        if key.lower() not in {"content-encoding", "content-length"}
                    }
                    return httpx.Response(
                        response.status_code, headers=decoded_headers,
                        content=bytes(content), request=response.request,
                    )
                if attempt == 2:
                    raise RuntimeError(f"Crossref API 限流或暂不可用（HTTP {response.status_code}）")
                delay = self._retry_delay(response.headers.get("retry-after"), attempt)
            await asyncio.sleep(delay)
        raise RuntimeError("Crossref API 请求失败")

    async def _search_doi(self, doi: str, query: dict[str, Any]) -> CrossrefResult:
        url = f"{CROSSREF_API_URL}/{quote(doi, safe='')}"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0), transport=self.transport, follow_redirects=False,
            trust_env=False, headers={"User-Agent": "ResearchMate/0.1 (local research workspace)"},
        ) as client:
            response = await self._request_with_retry(client, {}, url=url)
            payload = await self._read_json(response)
        item = payload.get("message")
        record = self._parse_item(item, query, 1)
        return CrossrefResult([record] if record else [], 1 if record else 0, 0 if record else 1, False)

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        if value:
            try:
                return min(max(float(value), 0.0), 2.0)
            except ValueError:
                try:
                    return min(max((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds(), 0), 2.0)
                except (TypeError, ValueError, OverflowError):
                    pass
        return 0.25 * (2 ** attempt)

    async def _read_json(self, response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise RuntimeError("Crossref API 返回了非 JSON 内容")
        try:
            value = json.loads(response.content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Crossref API 返回了无效 UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("Crossref API 返回了无效 JSON 结构")
        return value

    def _parse_item(self, item: Any, query: dict[str, Any], position: int) -> DiscoveredRecord | None:
        if not isinstance(item, dict):
            return None
        doi = normalize_doi(item.get("DOI"))
        allowed = {"journal-article"} if query["scope"] == "journal" else {"journal-article", "proceedings-article"}
        if not doi or not doi.startswith(IEEE_PREFIX) or item.get("type") not in allowed:
            return None
        title = self._first_text(item.get("title"))
        if not title:
            return None
        authors = []
        for author in item.get("author") or []:
            if isinstance(author, dict):
                name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
                if name.strip():
                    authors.append(html.unescape(name.strip()))
        container = self._first_text(item.get("container-title"))
        abstract = self._clean_abstract(item.get("abstract"))
        source_url = f"https://doi.org/{doi}"
        facts = {
            "collector": self.name, "source_api": CROSSREF_API_URL, "doi": doi,
            "canonical_id": f"doi:{doi}", "authors": authors, "container_title": container or None,
            "issn": [str(value) for value in item.get("ISSN") or []], "work_type": item.get("type"),
            "published": self._date(item.get("published")), "published_online": self._date(item.get("published-online")),
            "published_print": self._date(item.get("published-print")), "issued": self._date(item.get("issued")),
            "created": self._timestamp(item.get("created")), "indexed": self._timestamp(item.get("indexed")),
            "result_position": position, "score": item.get("score") if isinstance(item.get("score"), (int, float)) and math.isfinite(item["score"]) else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(), "has_abstract": bool(abstract),
            "suggested_item_type": "paper", "formal_publication": True,
        }
        content_text = title + (f"\n\n{abstract}" if abstract else "")
        summary = abstract[:300] if abstract else ""
        return DiscoveredRecord(title[:300], content_text, summary, source_url, facts)

    @staticmethod
    def _first_text(value: Any) -> str:
        raw = value[0] if isinstance(value, list) and value else value
        return re.sub(r"\s+", " ", html.unescape(str(raw or ""))).strip()

    @staticmethod
    def _clean_abstract(value: Any) -> str:
        text = re.sub(r"<[^>]+>", " ", str(value or ""))
        return re.sub(r"\s+", " ", html.unescape(text)).strip()

    @staticmethod
    def _date(value: Any) -> str | None:
        try:
            parts = value["date-parts"][0]
            return "-".join([str(parts[0]).zfill(4), *[str(part).zfill(2) for part in parts[1:3]]])
        except (KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _timestamp(value: Any) -> str | None:
        return value.get("date-time") if isinstance(value, dict) and isinstance(value.get("date-time"), str) else None
