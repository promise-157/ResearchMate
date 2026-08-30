"""Bounded public GitHub evidence checks for explicitly selected papers."""
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from crawlers.crossref_discovery import normalize_doi


GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
MAX_CANDIDATES = 5
MAX_REPOSITORIES = 3
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_README_BYTES = 256 * 1024
REPOSITORY_RE = re.compile(r"^https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]{1,100})(?:[/?#].*)?$")


@dataclass(frozen=True)
class GitHubCodeEvidenceResult:
    records_by_candidate_id: dict[int, dict[str, Any]]
    errors_by_candidate_id: dict[int, str]


def normalize_words(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def repository_url(value: str) -> str | None:
    cleaned = value.rstrip(".,;:)]}>'\"")
    match = REPOSITORY_RE.fullmatch(cleaned)
    if not match or match.group(2).lower().endswith(".git"):
        return None
    return f"https://github.com/{match.group(1)}/{match.group(2)}"


class GitHubCodeEvidenceCollector:
    name = "github_code"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

    async def check(self, papers: list[dict[str, Any]]) -> GitHubCodeEvidenceResult:
        if not 1 <= len(papers) <= MAX_CANDIDATES:
            raise ValueError("源码检查论文数量必须在 1–5 之间")
        records: dict[int, dict[str, Any]] = {}
        errors: dict[int, str] = {}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20), transport=self.transport, follow_redirects=False,
            trust_env=False, headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ResearchMate/0.1 (local research workspace)",
            },
        ) as client:
            for paper in papers:
                try:
                    records[paper["candidate_id"]] = await self._check_one(client, paper)
                except Exception as exc:
                    errors[paper["candidate_id"]] = str(exc).strip()[:1_000] or "GitHub 源码检查失败"
        return GitHubCodeEvidenceResult(records, errors)

    async def _check_one(self, client: httpx.AsyncClient, paper: dict[str, Any]) -> dict[str, Any]:
        declared = self._declared_repositories(paper.get("evidence_texts", []))
        repositories = []
        if declared:
            for url in declared[:MAX_REPOSITORIES]:
                full_name = url.removeprefix("https://github.com/")
                metadata = await self._repository_metadata(client, full_name)
                if metadata is None:
                    repositories.append({
                        "repository_url": url, "full_name": full_name,
                        "description": "", "stars": None, "updated_at": None,
                        "archived": False, "license_spdx": None, "available": False,
                        "level": "paper_declared", "matched_fields": ["source_link"],
                    })
                    continue
                readme = await self._readme(client, full_name)
                evidence = self._evidence(paper, readme, declared=True)
                repositories.append(self._repository(metadata, url, evidence))
        else:
            payload = await self._json(client, GITHUB_SEARCH_URL, params={
                "q": self._search_query(paper), "per_page": MAX_REPOSITORIES,
                "sort": "updated", "order": "desc",
            })
            items = payload.get("items") if isinstance(payload, dict) else None
            if not isinstance(items, list):
                raise RuntimeError("GitHub repository search 返回了无效 JSON 结构")
            for metadata in items[:MAX_REPOSITORIES]:
                full_name = metadata.get("full_name") if isinstance(metadata, dict) else None
                if not isinstance(full_name, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}", full_name):
                    continue
                readme = await self._readme(client, full_name)
                evidence = self._evidence(paper, readme, declared=False)
                if evidence["level"] == "insufficient":
                    continue
                repositories.append(self._repository(
                    metadata, f"https://github.com/{full_name}", evidence
                ))
        return {
            "source_record_id": f"candidate:{paper['candidate_id']}",
            "source_url": "https://github.com/search",
            "query": self._search_query(paper) if not declared else None,
            "declared_repository_count": len(declared),
            "repositories": repositories,
            "checked_repository_count": min(len(declared), MAX_REPOSITORIES) if declared else MAX_REPOSITORIES,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _repository_metadata(
        self, client: httpx.AsyncClient, full_name: str
    ) -> dict[str, Any] | None:
        url = f"https://api.github.com/repos/{quote(full_name, safe='/')}"
        async with client.stream("GET", url) as response:
            if response.status_code == 404:
                return None
            if response.status_code != 200:
                raise RuntimeError(self._http_error(response))
            if response.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                raise RuntimeError("GitHub API 返回了非 JSON 内容")
            content = await self._bounded(response, MAX_JSON_BYTES)
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("GitHub API 返回了无效 UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("GitHub API 返回了无效 JSON 结构")
        return value

    async def _json(self, client: httpx.AsyncClient, url: str, *, params=None) -> dict[str, Any]:
        async with client.stream("GET", url, params=params) as response:
            if response.status_code != 200:
                raise RuntimeError(self._http_error(response))
            if response.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
                raise RuntimeError("GitHub API 返回了非 JSON 内容")
            content = await self._bounded(response, MAX_JSON_BYTES)
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError("GitHub API 返回了无效 UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise RuntimeError("GitHub API 返回了无效 JSON 结构")
        return value

    async def _readme(self, client: httpx.AsyncClient, full_name: str) -> str:
        async with client.stream(
            "GET", f"https://api.github.com/repos/{quote(full_name, safe='/')}/readme",
            headers={"Accept": "application/vnd.github.raw+json"},
        ) as response:
            if response.status_code == 404:
                return ""
            if response.status_code != 200:
                raise RuntimeError(self._http_error(response))
            content = await self._bounded(response, MAX_README_BYTES)
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError("GitHub README 无法按 UTF-8 解码") from exc

    @staticmethod
    async def _bounded(response: httpx.Response, limit: int) -> bytes:
        content = bytearray()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
            if len(content) > limit:
                raise RuntimeError("GitHub API 响应超过大小限制")
        return bytes(content)

    @staticmethod
    def _http_error(response: httpx.Response) -> str:
        if response.status_code in {403, 429}:
            reset = response.headers.get("x-ratelimit-reset")
            return f"GitHub API 已限流{f'（重置时间 {reset}）' if reset else ''}"
        return f"GitHub API 返回 HTTP {response.status_code}"

    @staticmethod
    def _declared_repositories(texts: list[str]) -> list[str]:
        found = []
        for text in texts:
            if not isinstance(text, str):
                continue
            for raw in re.findall(r"https://github\.com/[^\s<]+", text):
                url = repository_url(raw)
                if url and url not in found:
                    found.append(url)
        return found

    @staticmethod
    def _search_query(paper: dict[str, Any]) -> str:
        doi = normalize_doi(paper.get("doi"))
        if doi:
            return f"{doi} in:readme"
        arxiv_id = str(paper.get("arxiv_id") or "").lower().split("v", 1)[0]
        if arxiv_id:
            return f"{arxiv_id} in:readme"
        title = paper["title"]
        prefix = title.split(":", 1)[0].strip()
        if ":" in title and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,30}", prefix):
            detail = normalize_words(title.split(":", 1)[1]).split()[:4]
            return " ".join([prefix, *detail, "in:readme"])[:220]
        words = normalize_words(title).split()
        return " ".join(words[:16])[:220]

    @staticmethod
    def _evidence(paper: dict[str, Any], readme: str, *, declared: bool) -> dict[str, Any]:
        if declared:
            return {"level": "paper_declared", "matched_fields": ["source_link"]}
        normalized_readme = normalize_words(readme)
        doi = normalize_doi(paper.get("doi"))
        arxiv_id = str(paper.get("arxiv_id") or "").lower().split("v", 1)[0]
        matched = []
        if doi and doi in readme.casefold():
            matched.append("doi")
        if arxiv_id and re.search(rf"(?<![\d.]){re.escape(arxiv_id)}(?!\d)", readme.casefold()):
            matched.append("arxiv_id")
        if matched:
            return {"level": "strong_identifier", "matched_fields": matched}
        title = normalize_words(paper["title"])
        if len(title) >= 20 and title in normalized_readme:
            authors = [normalize_words(value) for value in paper.get("authors", [])]
            shared = [author for author in authors if len(author) >= 4 and author in normalized_readme]
            return {
                "level": "title_author_match" if shared else "title_match",
                "matched_fields": ["title", *(["author"] if shared else [])],
                "matched_authors": shared[:10],
            }
        return {"level": "insufficient", "matched_fields": []}

    @staticmethod
    def _repository(metadata: dict[str, Any], url: str, evidence: dict[str, Any]) -> dict[str, Any]:
        expected = repository_url(str(metadata.get("html_url") or ""))
        if expected != url:
            raise RuntimeError("GitHub 仓库响应与请求不一致")
        license_data = metadata.get("license") or {}
        return {
            "repository_url": url, "full_name": metadata.get("full_name"),
            "description": str(metadata.get("description") or "")[:500],
            "stars": metadata.get("stargazers_count") if isinstance(metadata.get("stargazers_count"), int) else None,
            "updated_at": metadata.get("updated_at"), "archived": bool(metadata.get("archived")),
            "available": True,
            "license_spdx": license_data.get("spdx_id") if isinstance(license_data, dict) else None,
            **evidence,
        }
