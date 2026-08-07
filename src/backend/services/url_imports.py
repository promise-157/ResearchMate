"""Application workflow for one public URL and its review candidate."""
import asyncio
import hashlib
from typing import Any

from crawlers.single_url import SinglePublicURLCollector
from services.materials import _update_workspace_item_count, classify_text, normalize_text
from storage import candidates as candidate_repository
from storage import items as item_repository
from storage.workspace import get_active_connection


def list_url_imports() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return candidate_repository.list_jobs(conn, collector="single_public_url")
    finally:
        conn.close()


def list_candidates(*, status: str | None = None) -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return candidate_repository.list_candidates(conn, status=status)
    finally:
        conn.close()


def get_candidate(candidate_id: int) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        return candidate_repository.get_candidate(conn, candidate_id)
    finally:
        conn.close()


async def import_public_url(
    url: str, *, collector: Any | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    submitted_url = url.strip()
    if not submitted_url or len(submitted_url) > 2_000:
        raise ValueError("请输入不超过 2,000 字符的公开 URL")
    conn = get_active_connection()
    job = candidate_repository.create_job(
        conn, collector="single_public_url", query={"url": submitted_url}
    )
    try:
        try:
            async with asyncio.timeout(30):
                page = await (collector or SinglePublicURLCollector()).collect(submitted_url)
        except TimeoutError as exc:
            raise RuntimeError("公开 URL 导入超时（总计 30 秒）") from exc
        normalized = normalize_text(page.content_text)
        if not normalized:
            raise RuntimeError("页面未提取到可用正文")
        content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        summary = normalized[:300]
        candidate = candidate_repository.create_candidate(conn, {
            "job_id": job["id"],
            "title": page.title[:300],
            "content_text": normalized,
            "summary": summary,
            "source_kind": "public_url",
            "source_url": page.source_url,
            "content_hash": content_hash,
            "source_facts": page.source_facts,
        })
        job = candidate_repository.complete_job(conn, job["id"])
        return job, candidate
    except Exception as exc:
        message = str(exc).strip()[:1_000] or "公开 URL 导入失败"
        candidate_repository.complete_job(conn, job["id"], error_message=message)
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError(message) from exc
    finally:
        conn.close()


def accept_candidate(candidate_id: int) -> tuple[dict[str, Any], dict[str, Any], bool] | None:
    conn = get_active_connection()
    try:
        candidate = candidate_repository.get_candidate(conn, candidate_id)
        if not candidate:
            return None
        if candidate["status"] == "rejected":
            raise ValueError("已拒绝的候选不能入库")
        if candidate["status"] == "accepted":
            item = item_repository.get_item(conn, candidate["accepted_item_id"])
            if not item:
                raise RuntimeError("候选的已入库资料不存在")
            return candidate, item, True

        duplicate = item_repository.find_by_hash(conn, candidate["content_hash"])
        created = duplicate is None
        if duplicate:
            item = duplicate
        else:
            classification = classify_text(candidate["content_text"])
            suggested_type = candidate["source_facts"].get("suggested_item_type")
            resolved_type = suggested_type if suggested_type in {"general", "paper", "job", "debug"} else classification.item_type
            item = item_repository.create_item(conn, {
                "item_type": resolved_type,
                "title": candidate["title"],
                "content_text": candidate["content_text"],
                "summary": candidate["summary"],
                "source_kind": candidate["source_kind"],
                "source_url": candidate["source_url"],
                "status": "inbox",
                "tags": [],
                "metadata": {
                    "schema_version": 1,
                    "classification": {
                        "suggested_type": resolved_type,
                        "signals": classification.signals,
                        "method": "rules-v1",
                        "user_selected_type": None,
                    },
                    "provenance": candidate["source_facts"],
                    "candidate_id": candidate["id"],
                },
                "content_hash": candidate["content_hash"],
            }, commit=False)
        candidate = candidate_repository.set_candidate_status(
            conn, candidate_id, status="accepted", accepted_item_id=item["id"]
        )
        conn.execute(
            "UPDATE collection_jobs SET accepted_count = accepted_count + 1, updated_at = datetime('now') WHERE id = ?",
            (candidate["job_id"],),
        )
        conn.commit()
        item_count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        _update_workspace_item_count(item_count)
        return candidate, item, not created
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reject_candidate(candidate_id: int) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        candidate = candidate_repository.get_candidate(conn, candidate_id)
        if not candidate:
            return None
        if candidate["status"] == "accepted":
            raise ValueError("已入库的候选不能拒绝")
        if candidate["status"] == "rejected":
            return candidate
        updated = candidate_repository.set_candidate_status(
            conn, candidate_id, status="rejected"
        )
        conn.commit()
        return updated
    finally:
        conn.close()
