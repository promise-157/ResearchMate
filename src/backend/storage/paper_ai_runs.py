"""Workspace-local persistence for audited paper AI runs."""
import json
import sqlite3
from typing import Any


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    run = dict(row)
    for source, target, fallback in (
        ("paper_ids_json", "paper_ids", []),
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
    conn: sqlite3.Connection,
    *,
    paper_id: int | None,
    paper_ids: list[int],
    run_kind: str,
    input_scope: list[str],
    input_hash: str,
    processor: str,
    processor_version: str,
    prompt_version: str,
    provider: str,
    model: str,
    commit: bool = True,
) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO paper_ai_runs
           (paper_id, paper_ids_json, run_kind, input_scope_json, input_hash,
            processor, processor_version, prompt_version, provider, model)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            paper_id,
            json.dumps(paper_ids),
            run_kind,
            json.dumps(input_scope, ensure_ascii=False),
            input_hash,
            processor,
            processor_version,
            prompt_version,
            provider,
            model,
        ),
    )
    if commit:
        conn.commit()
    return get_run(conn, cursor.lastrowid)


def get_run(conn: sqlite3.Connection, run_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM paper_ai_runs WHERE id = ?", (run_id,)
    ).fetchone()
    return _decode(row)


def complete_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = provider_metadata or {}
    status = "failed" if error_message is not None else "succeeded"
    conn.execute(
        """UPDATE paper_ai_runs SET
           status = ?, result_json = ?, error_message = ?,
           provider_model = ?, input_tokens = ?, output_tokens = ?,
           duration_ms = ?, request_id = ?, completed_at = datetime('now')
           WHERE id = ? AND status = 'running'""",
        (
            status,
            json.dumps(result, ensure_ascii=False) if result is not None else None,
            error_message,
            metadata.get("provider_model"),
            metadata.get("input_tokens"),
            metadata.get("output_tokens"),
            metadata.get("duration_ms"),
            metadata.get("request_id"),
            run_id,
        ),
    )
    conn.commit()
    return get_run(conn, run_id)


def list_runs(
    conn: sqlite3.Connection,
    *,
    run_kind: str,
    paper_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List one audited paper workflow without coupling it to a UI surface."""
    bounded_limit = max(1, min(int(limit), 200))
    clauses = ["run_kind = ?"]
    params: list[Any] = [run_kind]
    if paper_id is not None:
        clauses.append("paper_id = ?")
        params.append(paper_id)
    params.append(bounded_limit)
    rows = conn.execute(
        f"SELECT * FROM paper_ai_runs WHERE {' AND '.join(clauses)} "
        "ORDER BY id DESC LIMIT ?",
        params,
    ).fetchall()
    return [_decode(row) for row in rows]


def fail_running_runs(
    conn: sqlite3.Connection,
    error_message: str = "上次应用退出时分析被中断，请重新执行",
) -> int:
    cursor = conn.execute(
        """UPDATE paper_ai_runs
           SET status = 'failed', error_message = ?, completed_at = datetime('now')
           WHERE status = 'running'""",
        (error_message,),
    )
    conn.commit()
    return cursor.rowcount


def list_runs_for_paper(
    conn: sqlite3.Connection, paper_id: int, *, limit: int = 10
) -> list[dict[str, Any]]:
    return list_runs(
        conn, run_kind="paper_analysis", paper_id=paper_id, limit=limit
    )


def list_legacy_workspace_reviews(
    conn: sqlite3.Connection, *, limit: int = 20
) -> list[dict[str, Any]]:
    """Expose pre-M11 reviews as explicitly incomplete, read-only history."""
    bounded_limit = max(1, min(int(limit), 100))
    rows = conn.execute(
        "SELECT id, task_ids, ai_review, created_at "
        "FROM workspace_reviews ORDER BY id DESC LIMIT ?",
        (bounded_limit,),
    ).fetchall()
    reviews = []
    for row in rows:
        review = dict(row)
        try:
            review["task_ids"] = json.loads(review.get("task_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            review["task_ids"] = []
        raw_review = review.pop("ai_review") or ""
        try:
            review["review"] = json.loads(raw_review or "{}")
        except (json.JSONDecodeError, TypeError):
            review["review"] = {"raw": raw_review}
        review["compatibility"] = "legacy_read_only"
        reviews.append(review)
    return reviews
