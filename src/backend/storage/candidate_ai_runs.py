"""Workspace-local audit records for explicitly scoped candidate AI briefs."""
import json
import sqlite3
from typing import Any


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    run = dict(row)
    for source, target, fallback in (
        ("candidate_ids_json", "candidate_ids", []),
        ("input_scope_json", "input_scope", []),
        ("result_json", "result", None),
    ):
        raw = run.pop(source, None)
        try:
            run[target] = json.loads(raw) if raw else fallback
        except (json.JSONDecodeError, TypeError):
            run[target] = fallback
    return run


def create_run(
    conn: sqlite3.Connection, *, candidate_ids: list[int], input_scope: list[str],
    input_hash: str, processor: str, processor_version: str, prompt_version: str,
    provider: str, model: str,
) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO candidate_ai_runs
           (candidate_ids_json, input_scope_json, input_hash, processor,
            processor_version, prompt_version, provider, model)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (json.dumps(candidate_ids), json.dumps(input_scope, ensure_ascii=False), input_hash,
         processor, processor_version, prompt_version, provider, model),
    )
    conn.commit()
    return get_run(conn, cursor.lastrowid)


def get_run(conn: sqlite3.Connection, run_id: int) -> dict[str, Any] | None:
    return _decode(conn.execute(
        "SELECT * FROM candidate_ai_runs WHERE id = ?", (run_id,)
    ).fetchone())


def complete_run(
    conn: sqlite3.Connection, run_id: int, *, result: dict[str, Any] | None = None,
    error_message: str | None = None, provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = provider_metadata or {}
    conn.execute(
        """UPDATE candidate_ai_runs SET status = ?, result_json = ?, error_message = ?,
           provider_model = ?, input_tokens = ?, output_tokens = ?, duration_ms = ?,
           request_id = ?, completed_at = datetime('now') WHERE id = ? AND status = 'running'""",
        ("failed" if error_message else "succeeded",
         json.dumps(result, ensure_ascii=False) if result is not None else None,
         error_message, metadata.get("provider_model"), metadata.get("input_tokens"),
         metadata.get("output_tokens"), metadata.get("duration_ms"),
         metadata.get("request_id"), run_id),
    )
    conn.commit()
    return get_run(conn, run_id)


def list_runs(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM candidate_ai_runs ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 100),)
    ).fetchall()
    return [_decode(row) for row in rows]


def fail_running_runs(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        """UPDATE candidate_ai_runs SET status = 'failed',
           error_message = '上次应用退出时候选简报被中断，请重新执行',
           completed_at = datetime('now') WHERE status = 'running'"""
    )
    conn.commit()
    return cursor.rowcount
