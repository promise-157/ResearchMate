"""Workspace-local persistence helpers for legacy paper records."""
import sqlite3
from typing import Any

from storage.database import dict_from_row


def list_cart(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM papers WHERE in_cart = 1 ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [dict_from_row(row) for row in rows]


def list_cart_ids(conn: sqlite3.Connection) -> list[int]:
    return [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM papers WHERE in_cart = 1 ORDER BY created_at DESC, id DESC"
        ).fetchall()
    ]


def get_cart_selection(
    conn: sqlite3.Connection, paper_ids: list[int]
) -> list[dict[str, Any]]:
    if not paper_ids:
        return []
    placeholders = ",".join("?" for _ in paper_ids)
    rows = conn.execute(
        f"SELECT * FROM papers WHERE id IN ({placeholders}) AND in_cart = 1",
        paper_ids,
    ).fetchall()
    by_id = {row["id"]: dict_from_row(row) for row in rows}
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]


def get_selection(
    conn: sqlite3.Connection, paper_ids: list[int]
) -> list[dict[str, Any]]:
    """Return explicit paper metadata in caller order without widening scope."""
    if not paper_ids:
        return []
    placeholders = ",".join("?" for _ in paper_ids)
    rows = conn.execute(
        "SELECT id, title, authors, abstract, journal_name, publish_year, paper_url "
        f"FROM papers WHERE id IN ({placeholders})",
        paper_ids,
    ).fetchall()
    by_id = {row["id"]: dict_from_row(row) for row in rows}
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]


def list_cart_export_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT title, authors, journal_name, publish_year, code_url "
        "FROM papers WHERE in_cart = 1 ORDER BY created_at DESC, id DESC"
    ).fetchall()
    return [dict_from_row(row) for row in rows]
