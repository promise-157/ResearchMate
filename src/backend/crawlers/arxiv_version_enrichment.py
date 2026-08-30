"""Strict, bounded arXiv version matching for formal paper candidates."""
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from crawlers.arxiv_discovery import ArxivDiscoveryCollector


MAX_BATCH_TITLES = 4
MAX_CANDIDATES = 20


@dataclass(frozen=True)
class ArxivVersionResult:
    records_by_candidate_id: dict[int, dict[str, Any]]


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def normalize_author(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


class ArxivVersionCollector:
    name = "arxiv_version"

    def __init__(self, *, discovery: ArxivDiscoveryCollector | None = None):
        self.discovery = discovery or ArxivDiscoveryCollector()

    async def match(self, candidates: list[dict[str, Any]]) -> ArxivVersionResult:
        if not 1 <= len(candidates) <= MAX_CANDIDATES:
            raise ValueError("arXiv 版本匹配数量必须在 1–20 之间")
        matches: dict[int, dict[str, Any]] = {}
        for start in range(0, len(candidates), MAX_BATCH_TITLES):
            batch = candidates[start:start + MAX_BATCH_TITLES]
            clauses = [f'ti:"{self._escape(candidate["title"])}"' for candidate in batch]
            records = await self.discovery.search_query(
                " OR ".join(clauses), min(20, len(batch) * 3)
            )
            for candidate in batch:
                matched = self._strict_match(candidate, records)
                if matched is not None:
                    matches[candidate["candidate_id"]] = matched
        return ArxivVersionResult(matches)

    @staticmethod
    def _escape(value: str) -> str:
        return re.sub(r'["\\]+', " ", value)[:300]

    @staticmethod
    def _strict_match(candidate: dict[str, Any], records) -> dict[str, Any] | None:
        target_title = normalize_title(candidate["title"])
        target_authors = {
            normalize_author(author) for author in candidate.get("authors", []) if author
        }
        if not target_title or not target_authors:
            return None
        for record in records:
            if normalize_title(record.title) != target_title:
                continue
            source_authors = {
                normalize_author(author)
                for author in record.source_facts.get("authors", []) if author
            }
            shared = sorted(target_authors & source_authors)
            if not shared:
                continue
            facts = dict(record.source_facts)
            facts.update({
                "source_record_id": facts["arxiv_id"],
                "source_url": record.source_url,
                "title": record.title,
                "abstract": record.content_text.split("\n\n", 1)[-1],
                "match_kind": "exact_title_author",
                "matched_authors": shared,
                "formal_candidate_id": candidate["candidate_id"],
                "formal_doi": candidate["doi"],
            })
            return facts
        return None
