"""期刊源 CRUD"""
from fastapi import APIRouter, HTTPException
from storage.database import get_connection, dict_from_row
from storage.models import JournalSourceCreate, JournalSource

router = APIRouter()


@router.get("/journals")
def list_journals():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM journal_sources ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]


@router.post("/journals")
def create_journal(body: JournalSourceCreate):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO journal_sources (url, label) VALUES (?, ?)",
        (body.url, body.label),
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
