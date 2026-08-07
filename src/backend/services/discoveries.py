"""Persistent, bounded public-source discovery workflows."""
import asyncio
import hashlib
from typing import Any

from crawlers.arxiv_discovery import ArxivDiscoveryCollector
from services.materials import normalize_text
from storage import candidates as candidate_repository
from storage.workspace import get_active_connection


def list_collection_jobs() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return candidate_repository.list_jobs(conn)
    finally:
        conn.close()


async def discover_arxiv(
    query: str, *, limit: int = 10, collector: Any | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("搜索词不能为空")
    if len(normalized_query) > 200:
        raise ValueError("搜索词不能超过 200 字符")
    if not 1 <= limit <= 20:
        raise ValueError("单次发现数量必须在 1–20 之间")
    conn = get_active_connection()
    job = candidate_repository.create_job(
        conn, collector="arxiv_api", query={"query": normalized_query, "limit": limit}
    )
    try:
        try:
            async with asyncio.timeout(25):
                records = await (collector or ArxivDiscoveryCollector()).search(
                    normalized_query, limit
                )
        except TimeoutError as exc:
            raise RuntimeError("arXiv 公开 API 搜索超时（总计 25 秒）") from exc
        candidates = []
        for record in records:
            normalized = normalize_text(record.content_text)
            if not normalized:
                continue
            candidates.append(candidate_repository.create_candidate(conn, {
                "job_id": job["id"],
                "title": record.title,
                "content_text": normalized,
                "summary": record.summary,
                "source_kind": "arxiv_api",
                "source_url": record.source_url,
                "content_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                "source_facts": record.source_facts,
            }))
        job = candidate_repository.complete_job(
            conn, job["id"], candidate_count=len(candidates)
        )
        return job, candidates
    except Exception as exc:
        conn.rollback()
        message = str(exc).strip()[:1_000] or "arXiv 公开 API 搜索失败"
        candidate_repository.complete_job(conn, job["id"], error_message=message)
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(message) from exc
    finally:
        conn.close()
