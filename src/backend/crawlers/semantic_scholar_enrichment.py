"""Bounded DOI enrichment through the public Semantic Scholar Graph API."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from crawlers.crossref_discovery import normalize_doi


SEMANTIC_SCHOLAR_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class SemanticScholarResult:
    records_by_doi: dict[str, dict[str, Any]]


class SemanticScholarEnrichmentCollector:
    name = "semantic_scholar"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    async def enrich(self, dois: list[str]) -> SemanticScholarResult:
        normalized = [normalize_doi(doi) for doi in dois]
        if not 1 <= len(dois) <= 20 or any(doi is None for doi in normalized):
            raise ValueError("Semantic Scholar 补全 DOI 必须为 1–20 个有效值")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Semantic Scholar 补全 DOI 不能重复")
        fields = "paperId,title,abstract,authors,externalIds,openAccessPdf,publicationDate"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20), transport=self.transport,
            follow_redirects=False, trust_env=False,
            headers={"User-Agent": "ResearchMate/0.1 (local research workspace)"},
        ) as client:
            async with client.stream(
                "POST", SEMANTIC_SCHOLAR_BATCH_URL, params={"fields": fields},
                json={"ids": [f"DOI:{doi}" for doi in normalized]},
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(f"Semantic Scholar API 返回 HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type != "application/json":
                    raise RuntimeError("Semantic Scholar API 返回了非 JSON 内容")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("Semantic Scholar API 响应超过 2 MB 限制")
        try:
            payload = json.loads(bytes(content).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Semantic Scholar API 返回了无效 UTF-8 JSON") from exc
        if not isinstance(payload, list):
            raise RuntimeError("Semantic Scholar API 返回了无效 JSON 结构")
        fetched_at = datetime.now(timezone.utc).isoformat()
        records = {}
        for raw in payload:
            record = self._parse(raw, fetched_at)
            if record and record["doi"] in normalized:
                records[record["doi"]] = record
        return SemanticScholarResult(records)

    @staticmethod
    def _parse(raw: Any, fetched_at: str) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        paper_id = raw.get("paperId")
        doi = normalize_doi((raw.get("externalIds") or {}).get("DOI"))
        if not doi or not isinstance(paper_id, str) or len(paper_id) > 80:
            return None
        authors = [
            author["name"] for author in raw.get("authors") or []
            if isinstance(author, dict) and isinstance(author.get("name"), str)
        ]
        open_pdf = raw.get("openAccessPdf") or {}
        pdf_url = open_pdf.get("url") if isinstance(open_pdf.get("url"), str) else ""
        if not pdf_url.startswith("https://"):
            pdf_url = ""
        abstract = raw.get("abstract") if isinstance(raw.get("abstract"), str) else ""
        return {
            "source_record_id": paper_id, "source_url": f"https://www.semanticscholar.org/paper/{paper_id}",
            "doi": doi, "title": str(raw.get("title") or "")[:300],
            "abstract": abstract[:10_000], "authors": authors[:100],
            "publication_date": raw.get("publicationDate"),
            "open_access_pdf_url": pdf_url or None,
            "open_access_status": open_pdf.get("status"), "fetched_at": fetched_at,
        }
