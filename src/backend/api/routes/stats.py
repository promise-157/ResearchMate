"""统计概览"""
from fastapi import APIRouter
from storage.database import get_connection
from storage.models import Stats

router = APIRouter()


@router.get("/stats")
def get_stats():
    conn = get_connection()

    paper_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    cart_count = conn.execute("SELECT COUNT(*) FROM papers WHERE in_cart = 1").fetchone()[0]

    last_session = conn.execute(
        "SELECT created_at FROM crawl_sessions ORDER BY created_at DESC LIMIT 1"
    ).fetchone()

    conn.close()

    return Stats(
        paper_count=paper_count,
        cart_count=cart_count,
        last_update=last_session["created_at"] if last_session else None,
    )
