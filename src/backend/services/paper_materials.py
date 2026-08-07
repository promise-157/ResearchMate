"""Compatibility mapping from legacy paper rows into the generic material core."""
import hashlib
import json
import sqlite3
from typing import Any

from services.materials import normalize_text
from storage import items as item_repository


MAPPING_VERSION = 1


def ensure_paper_material_mapping(conn: sqlite3.Connection) -> int:
    """Idempotently link every paper row to an item without changing user items."""
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'papers'"
    ).fetchone()
    if not table:
        return 0
    columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
    if "item_id" not in columns:
        conn.execute(
            "ALTER TABLE papers ADD COLUMN item_id INTEGER REFERENCES items(id) ON DELETE SET NULL"
        )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ws_papers_item ON papers(item_id)")
    conn.execute(
        """UPDATE papers SET item_id = NULL
           WHERE item_id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM items WHERE items.id = papers.item_id)"""
    )
    paper_ids = [row[0] for row in conn.execute(
        "SELECT id FROM papers WHERE item_id IS NULL ORDER BY id"
    ).fetchall()]
    mapped = 0
    for paper_id in paper_ids:
        if map_paper_to_material(conn, paper_id) is not None:
            mapped += 1
    if mapped:
        conn.commit()
    return mapped


def map_paper_to_material(
    conn: sqlite3.Connection, paper_id: int
) -> dict[str, Any] | None:
    paper_row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not paper_row:
        return None
    paper = dict(paper_row)
    if paper.get("item_id"):
        existing = item_repository.get_item(conn, paper["item_id"])
        if existing:
            return existing

    content = normalize_text(paper.get("abstract") or paper.get("title") or "")
    if not content:
        return None
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    item = item_repository.find_by_hash(conn, content_hash)
    if item is None:
        item = item_repository.create_item(conn, {
            "item_type": "paper",
            "title": (paper.get("title") or "未命名论文")[:300],
            "content_text": content,
            "summary": " ".join(content.split())[:240],
            "source_kind": "paper_adapter",
            "source_url": paper.get("paper_url"),
            "status": "active",
            "tags": _json_list(paper.get("auto_keywords")),
            "metadata": {
                "schema_version": 1,
                "paper_mapping": {
                    "version": MAPPING_VERSION,
                    "paper_id": paper_id,
                    "arxiv_id": paper.get("arxiv_id"),
                    "source_id": paper.get("source_id"),
                },
                "source_facts": {
                    "authors": _json_list(paper.get("authors")),
                    "journal_name": paper.get("journal_name"),
                    "publish_year": paper.get("publish_year"),
                    "has_code": bool(paper.get("has_code")),
                    "code_url": paper.get("code_url"),
                },
            },
            "content_hash": content_hash,
        }, commit=False)
    conn.execute("UPDATE papers SET item_id = ? WHERE id = ?", (item["id"], paper_id))
    return item


def _json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(value) for value in raw if str(value).strip()]
    try:
        parsed = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(value) for value in parsed if str(value).strip()] if isinstance(parsed, list) else []
