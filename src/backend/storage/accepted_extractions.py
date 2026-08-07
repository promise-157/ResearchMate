"""Repository for user-accepted deterministic extraction values."""
import sqlite3
from typing import Any


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_for_item(
    conn: sqlite3.Connection, item_id: int, extraction_kind: str | None = None
) -> list[dict[str, Any]]:
    if extraction_kind:
        rows = conn.execute(
            "SELECT * FROM accepted_extractions WHERE item_id = ? AND extraction_kind = ?",
            (item_id, extraction_kind),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM accepted_extractions WHERE item_id = ? ORDER BY extraction_kind",
            (item_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_text(conn: sqlite3.Connection, item_id: int) -> str:
    rows = conn.execute(
        "SELECT text_value FROM accepted_extractions WHERE item_id = ? ORDER BY extraction_kind",
        (item_id,),
    ).fetchall()
    return "\n\n".join(row["text_value"] for row in rows if row["text_value"])


def accept(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    extraction_kind: str,
    run_id: int,
    text_value: str,
) -> dict[str, Any]:
    conn.execute(
        """INSERT INTO accepted_extractions
           (item_id, extraction_kind, run_id, text_value)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(item_id, extraction_kind) DO UPDATE SET
             run_id = excluded.run_id,
             text_value = excluded.text_value,
             accepted_at = datetime('now'),
             updated_at = datetime('now')""",
        (item_id, extraction_kind, run_id, text_value),
    )
    conn.commit()
    return _decode(conn.execute(
        "SELECT * FROM accepted_extractions WHERE item_id = ? AND extraction_kind = ?",
        (item_id, extraction_kind),
    ).fetchone())
