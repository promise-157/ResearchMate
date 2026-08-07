"""Repository for URL collection jobs and their review candidates."""
import json
import sqlite3
from typing import Any


def _decode_candidate(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    candidate = dict(row)
    raw = candidate.pop("source_facts_json", "{}")
    try:
        candidate["source_facts"] = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        candidate["source_facts"] = {}
    return candidate


def _decode_job(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    job = dict(row)
    raw = job.pop("query_json", "{}")
    try:
        job["query"] = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        job["query"] = {}
    return job


def create_job(
    conn: sqlite3.Connection, *, collector: str, query: dict[str, Any]
) -> dict[str, Any]:
    cursor = conn.execute(
        "INSERT INTO collection_jobs (collector, query_json, status) VALUES (?, ?, 'running')",
        (collector, json.dumps(query, ensure_ascii=False)),
    )
    conn.commit()
    return get_job(conn, cursor.lastrowid)


def complete_job(
    conn: sqlite3.Connection,
    job_id: int,
    *,
    candidate_count: int = 1,
    error_message: str | None = None,
) -> dict[str, Any]:
    status = "failed" if error_message else "succeeded"
    conn.execute(
        """UPDATE collection_jobs
           SET status = ?, candidate_count = ?, error_message = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (status, 0 if error_message else candidate_count, error_message, job_id),
    )
    conn.commit()
    return get_job(conn, job_id)


def get_job(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    return _decode_job(conn.execute(
        "SELECT * FROM collection_jobs WHERE id = ?", (job_id,)
    ).fetchone())


def list_jobs(
    conn: sqlite3.Connection, *, collector: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    if collector:
        rows = conn.execute(
            "SELECT * FROM collection_jobs WHERE collector = ? ORDER BY id DESC LIMIT ?",
            (collector, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM collection_jobs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_decode_job(row) for row in rows]


def create_candidate(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO candidates
           (job_id, title, content_text, summary, source_kind, source_url,
            content_hash, source_facts_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["job_id"], data["title"], data["content_text"], data["summary"],
            data["source_kind"], data["source_url"], data["content_hash"],
            json.dumps(data.get("source_facts", {}), ensure_ascii=False),
        ),
    )
    return get_candidate(conn, cursor.lastrowid)


def get_candidate(conn: sqlite3.Connection, candidate_id: int) -> dict[str, Any] | None:
    return _decode_candidate(conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone())


def list_candidates(
    conn: sqlite3.Connection, *, status: str | None = None
) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute(
            "SELECT * FROM candidates WHERE status = ? ORDER BY id DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM candidates ORDER BY id DESC").fetchall()
    return [_decode_candidate(row) for row in rows]


def set_candidate_status(
    conn: sqlite3.Connection,
    candidate_id: int,
    *,
    status: str,
    accepted_item_id: int | None = None,
) -> dict[str, Any] | None:
    conn.execute(
        """UPDATE candidates SET status = ?, accepted_item_id = ?,
           updated_at = datetime('now') WHERE id = ?""",
        (status, accepted_item_id, candidate_id),
    )
    return get_candidate(conn, candidate_id)
