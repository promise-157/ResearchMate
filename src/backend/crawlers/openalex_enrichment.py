"""Bounded OpenAlex DOI enrichment for explicitly selected candidates."""
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from crawlers.crossref_discovery import normalize_doi


OPENALEX_API_URL = "https://api.openalex.org/works"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/json"}


@dataclass(frozen=True)
class OpenAlexEnrichmentResult:
    records_by_doi: dict[str, dict[str, Any]]


class OpenAlexEnrichmentCollector:
    name = "openalex"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    async def enrich(self, dois: list[str]) -> OpenAlexEnrichmentResult:
        if not 1 <= len(dois) <= 20:
            raise ValueError("OpenAlex 单次补全数量必须在 1–20 之间")
        normalized = [normalize_doi(value) for value in dois]
        if any(value is None for value in normalized) or len(set(normalized)) != len(dois):
            raise ValueError("OpenAlex 补全 DOI 无效或重复")
        params = {
            "filter": "doi:" + "|".join(f"https://doi.org/{doi}" for doi in normalized),
            "per-page": len(dois),
            "select": (
                "id,doi,title,type,publication_date,updated_date,abstract_inverted_index,"
                "authorships,topics,concepts,cited_by_count,open_access,best_oa_location,primary_location"
            ),
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0), transport=self.transport,
            follow_redirects=False, trust_env=False,
            headers={"User-Agent": "ResearchMate/0.1 (local research workspace)"},
        ) as client:
            async with client.stream("GET", OPENALEX_API_URL, params=params) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"OpenAlex API 返回 HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise RuntimeError("OpenAlex API 返回了非 JSON 内容")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("OpenAlex API 响应超过 2 MB 限制")
        try:
            payload = json.loads(bytes(content).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("OpenAlex API 返回了无效 UTF-8 JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise RuntimeError("OpenAlex API 返回了无效 JSON 结构")
        fetched_at = datetime.now(timezone.utc).isoformat()
        records = {}
        for raw in payload["results"]:
            record = self._parse_record(raw, fetched_at)
            if record and record["doi"] in normalized:
                records[record["doi"]] = record
        return OpenAlexEnrichmentResult(records)

    def _parse_record(self, raw: Any, fetched_at: str) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        doi = normalize_doi(raw.get("doi"))
        source_id = raw.get("id")
        if not doi or not isinstance(source_id, str) or not re.fullmatch(
            r"https://openalex\.org/W\d+", source_id
        ):
            return None
        institutions = []
        authors = []
        for authorship in raw.get("authorships") or []:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author") or {}
            if isinstance(author.get("display_name"), str):
                authors.append(author["display_name"])
            for institution in authorship.get("institutions") or []:
                if isinstance(institution, dict) and isinstance(institution.get("display_name"), str):
                    institutions.append(institution["display_name"])
        topics = []
        for topic in [*(raw.get("topics") or []), *(raw.get("concepts") or [])]:
            if isinstance(topic, dict) and isinstance(topic.get("display_name"), str):
                topics.append(topic["display_name"])
        best_oa = raw.get("best_oa_location") or {}
        open_access = raw.get("open_access") or {}
        return {
            "source_record_id": source_id.rsplit("/", 1)[-1],
            "source_url": source_id,
            "doi": doi,
            "title": str(raw.get("title") or "")[:300],
            "work_type": raw.get("type"),
            "publication_date": raw.get("publication_date"),
            "updated_date": raw.get("updated_date"),
            "abstract": self._abstract(raw.get("abstract_inverted_index")),
            "authors": list(dict.fromkeys(authors))[:100],
            "institutions": list(dict.fromkeys(institutions))[:100],
            "topics": list(dict.fromkeys(topics))[:50],
            "cited_by_count": raw.get("cited_by_count") if isinstance(raw.get("cited_by_count"), int) else None,
            "is_open_access": bool(open_access.get("is_oa")),
            "oa_status": open_access.get("oa_status"),
            "best_open_url": best_oa.get("landing_page_url") or best_oa.get("pdf_url"),
            "primary_source": (raw.get("primary_location") or {}).get("source", {}).get("display_name"),
            "fetched_at": fetched_at,
        }

    @staticmethod
    def _abstract(index: Any) -> str:
        if not isinstance(index, dict):
            return ""
        positions = []
        for word, indexes in index.items():
            if not isinstance(word, str) or not isinstance(indexes, list):
                continue
            for position in indexes:
                if isinstance(position, int) and 0 <= position < 10_000:
                    positions.append((position, word))
        positions.sort()
        return " ".join(word for _, word in positions)[:6_000]
