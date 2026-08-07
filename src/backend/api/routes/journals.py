"""期刊源 CRUD"""
from fastapi import APIRouter, HTTPException
from storage.database import get_connection, dict_from_row
from storage.models import JournalSourceCreate
from crawlers.policy import validate_source_url

router = APIRouter()


@router.get("/journals")
def list_journals():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM journal_sources ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]


@router.post("/journals")
def create_journal(body: JournalSourceCreate):
    url = body.url.strip()
    allowed, reason = validate_source_url(url)
    if not allowed:
        raise HTTPException(status_code=400, detail=reason)
    conn = get_connection()
    existing = conn.execute(
        "SELECT * FROM journal_sources WHERE url = ?", (url,)
    ).fetchone()
    if existing:
        conn.close()
        return dict_from_row(existing)
    cursor = conn.execute(
        "INSERT INTO journal_sources (url, label) VALUES (?, ?)",
        (url, body.label),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM journal_sources WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return dict_from_row(row)


@router.delete("/journals/{journal_id}")
def delete_journal(journal_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM journal_sources WHERE id = ?", (journal_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
