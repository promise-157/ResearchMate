"""Workspace-local persistence for audited chat sessions and turns."""
import json
import sqlite3
from typing import Any


def _decode_turn(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    turn = dict(row)
    for source, target in (
        ("paper_ids_json", "paper_ids"),
        ("input_scope_json", "input_scope"),
        ("history_turn_ids_json", "history_turn_ids"),
    ):
        raw = turn.pop(source, None)
        try:
            turn[target] = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            turn[target] = []
    return turn


def create_session(conn: sqlite3.Connection, title: str = "新对话") -> dict[str, Any]:
    cursor = conn.execute(
        "INSERT INTO chat_sessions(title) VALUES (?)", (title[:80] or "新对话",)
    )
    conn.commit()
    return get_session(conn, cursor.lastrowid)


def get_session(conn: sqlite3.Connection, session_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return dict(row) if row else None


def list_sessions(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT s.*, COUNT(t.id) AS turn_count
           FROM chat_sessions s LEFT JOIN chat_turns t ON t.session_id = s.id
           GROUP BY s.id ORDER BY s.updated_at DESC, s.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_turns(conn: sqlite3.Connection, session_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM chat_turns WHERE session_id = ? ORDER BY id", (session_id,)
    ).fetchall()
    return [_decode_turn(row) for row in rows]


def create_turn(
    conn: sqlite3.Connection,
    *,
    session_id: int,
    user_message: str,
    paper_ids: list[int],
    input_scope: list[str],
    history_turn_ids: list[int],
    provider: str,
    model: str,
    prompt_version: str,
) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO chat_turns
           (session_id, user_message, paper_ids_json, input_scope_json,
            history_turn_ids_json, provider, model, prompt_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            user_message,
            json.dumps(paper_ids),
            json.dumps(input_scope, ensure_ascii=False),
            json.dumps(history_turn_ids),
            provider,
            model,
            prompt_version,
        ),
    )
    turn_id = cursor.lastrowid
    session = get_session(conn, session_id)
    if session and session["title"] == "新对话":
        conn.execute(
            "UPDATE chat_sessions SET title = ? WHERE id = ?",
            (user_message.replace("\n", " ")[:40], session_id),
        )
    conn.execute(
        "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    conn.commit()
    return get_turn(conn, turn_id)


def get_turn(conn: sqlite3.Connection, turn_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM chat_turns WHERE id = ?", (turn_id,)).fetchone()
    return _decode_turn(row)


def complete_turn(
    conn: sqlite3.Connection,
    turn_id: int,
    *,
    assistant_message: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    status = "failed" if error_message else "succeeded"
    conn.execute(
        """UPDATE chat_turns SET
           assistant_message = ?, status = ?, error_message = ?,
           provider_model = ?, input_tokens = ?, output_tokens = ?,
           duration_ms = ?, request_id = ?, completed_at = datetime('now')
           WHERE id = ? AND status = 'running'""",
        (
            assistant_message,
            status,
            error_message,
            metadata.get("provider_model"),
            metadata.get("input_tokens"),
            metadata.get("output_tokens"),
            metadata.get("duration_ms"),
            metadata.get("request_id"),
            turn_id,
        ),
    )
    conn.execute(
        """UPDATE chat_sessions SET updated_at = datetime('now')
           WHERE id = (SELECT session_id FROM chat_turns WHERE id = ?)""",
        (turn_id,),
    )
    conn.commit()
    return get_turn(conn, turn_id)


def fail_running_turns(
    conn: sqlite3.Connection,
    error_message: str = "上次应用退出时对话被中断，请重新发送",
) -> int:
    session_ids = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT session_id FROM chat_turns WHERE status = 'running'"
        ).fetchall()
    ]
    cursor = conn.execute(
        """UPDATE chat_turns
           SET status = 'failed', error_message = ?, completed_at = datetime('now')
           WHERE status = 'running'""",
        (error_message,),
    )
    if session_ids:
        placeholders = ",".join("?" for _ in session_ids)
        conn.execute(
            f"UPDATE chat_sessions SET updated_at = datetime('now') "
            f"WHERE id IN ({placeholders})",
            session_ids,
        )
    conn.commit()
    return cursor.rowcount
