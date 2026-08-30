"""Workspace-local saved public discovery conditions."""
import json
import sqlite3
from typing import Any


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    value = dict(row)
    try:
        value["query"] = json.loads(value.pop("query_json"))
    except (json.JSONDecodeError, TypeError):
        value["query"] = {}
    return value


def list_rules(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [_decode(row) for row in conn.execute(
        "SELECT * FROM saved_discovery_rules ORDER BY id DESC"
    ).fetchall()]


def get_rule(conn: sqlite3.Connection, rule_id: int) -> dict[str, Any] | None:
    return _decode(conn.execute(
        "SELECT * FROM saved_discovery_rules WHERE id = ?", (rule_id,)
    ).fetchone())


def create_rule(
    conn: sqlite3.Connection, *, name: str, source_kind: str, query: dict[str, Any]
) -> dict[str, Any]:
    cursor = conn.execute(
        "INSERT INTO saved_discovery_rules(name, source_kind, query_json) VALUES (?, ?, ?)",
        (name, source_kind, json.dumps(query, ensure_ascii=False)),
    )
    conn.commit()
    return get_rule(conn, cursor.lastrowid)


def update_rule(
    conn: sqlite3.Connection, rule_id: int, *, name: str, query: dict[str, Any]
) -> dict[str, Any] | None:
    cursor = conn.execute(
        """UPDATE saved_discovery_rules
           SET name = ?, query_json = ?, updated_at = datetime('now') WHERE id = ?""",
        (name, json.dumps(query, ensure_ascii=False), rule_id),
    )
    conn.commit()
    return get_rule(conn, rule_id) if cursor.rowcount == 1 else None


def record_run(
    conn: sqlite3.Connection, rule_id: int, *, ran_at: str, status: str,
    error: str | None = None, job_id: int | None = None,
) -> None:
    if status == "succeeded":
        conn.execute(
            """UPDATE saved_discovery_rules SET last_run_at = ?, last_run_status = ?,
               last_error = NULL, last_success_at = ?, last_successful_job_id = ?,
               updated_at = datetime('now') WHERE id = ?""",
            (ran_at, status, ran_at, job_id, rule_id),
        )
    else:
        conn.execute(
            """UPDATE saved_discovery_rules SET last_run_at = ?, last_run_status = ?,
               last_error = ?, updated_at = datetime('now') WHERE id = ?""",
            (ran_at, status, error, rule_id),
        )
    conn.commit()


def delete_rule(conn: sqlite3.Connection, rule_id: int) -> bool:
    cursor = conn.execute("DELETE FROM saved_discovery_rules WHERE id = ?", (rule_id,))
    conn.commit()
    return cursor.rowcount == 1
