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


def _decode_source_record(row: sqlite3.Row) -> dict[str, Any]:
    record = dict(row)
    raw = record.pop("facts_json", "{}")
    try:
        record["facts"] = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        record["facts"] = {}
    return record


def _attach_source_records(
    conn: sqlite3.Connection, candidate: dict[str, Any] | None
) -> dict[str, Any] | None:
    if candidate is None:
        return None
    rows = conn.execute(
        "SELECT * FROM candidate_source_records WHERE candidate_id = ? ORDER BY id DESC",
        (candidate["id"],),
    ).fetchall()
    candidate["source_records"] = [_decode_source_record(row) for row in rows]
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
    raw_result = job.pop("result_json", "{}")
    try:
        job["result"] = json.loads(raw_result) if raw_result else {}
    except (json.JSONDecodeError, TypeError):
        job["result"] = {}
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
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = "failed" if error_message else "succeeded"
    conn.execute(
        """UPDATE collection_jobs
           SET status = ?, candidate_count = ?, error_message = ?, result_json = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (status, 0 if error_message else candidate_count, error_message,
         json.dumps(result or {}, ensure_ascii=False), job_id),
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


def fail_running_jobs(
    conn: sqlite3.Connection,
    error_message: str = "上次应用退出时采集任务被中断，请重新执行",
) -> int:
    cursor = conn.execute(
        """UPDATE collection_jobs
           SET status = 'failed', candidate_count = 0, error_message = ?,
               updated_at = datetime('now')
           WHERE status = 'running'""",
        (error_message,),
    )
    conn.commit()
    return cursor.rowcount


def create_candidate(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO candidates
           (job_id, title, content_text, summary, source_kind, source_url,
            content_hash, canonical_id, source_facts_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["job_id"], data["title"], data["content_text"], data["summary"],
            data["source_kind"], data["source_url"], data["content_hash"],
            data.get("canonical_id"),
            json.dumps(data.get("source_facts", {}), ensure_ascii=False),
        ),
    )
    return get_candidate(conn, cursor.lastrowid)


def find_latest_by_canonical_id(
    conn: sqlite3.Connection, canonical_id: str
) -> dict[str, Any] | None:
    return _decode_candidate(conn.execute(
        "SELECT * FROM candidates WHERE canonical_id = ? ORDER BY id DESC LIMIT 1",
        (canonical_id,),
    ).fetchone())


def get_candidate(conn: sqlite3.Connection, candidate_id: int) -> dict[str, Any] | None:
    return _attach_source_records(conn, _decode_candidate(conn.execute(
        "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()))


def list_candidates(
    conn: sqlite3.Connection, *, status: str | None = None
) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute(
            "SELECT * FROM candidates WHERE status = ? ORDER BY id DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM candidates ORDER BY id DESC").fetchall()
    return [_attach_source_records(conn, _decode_candidate(row)) for row in rows]


def create_source_record(
    conn: sqlite3.Connection, data: dict[str, Any]
) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO candidate_source_records
           (candidate_id, job_id, source_kind, source_record_id, status,
            facts_json, error_message, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["candidate_id"], data["job_id"], data["source_kind"],
            data.get("source_record_id"), data["status"],
            json.dumps(data.get("facts", {}), ensure_ascii=False),
            data.get("error_message"), data.get("fetched_at"),
        ),
    )
    row = conn.execute(
        "SELECT * FROM candidate_source_records WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return _decode_source_record(row)


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
