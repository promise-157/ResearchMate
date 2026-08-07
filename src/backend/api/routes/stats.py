"""统计概览 + 最新爬取会话点评"""
import json
from fastapi import APIRouter
from storage.workspace import get_active_connection as get_connection
from storage.database import dict_from_row
from storage.models import Stats

router = APIRouter()


@router.get("/stats")
def get_stats():
    conn = get_connection()

    paper_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    material_count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    cart_count = conn.execute("SELECT COUNT(*) FROM papers WHERE in_cart = 1").fetchone()[0]

    last_session = conn.execute(
        "SELECT created_at FROM crawl_tasks ORDER BY created_at DESC LIMIT 1"
    ).fetchone()

    conn.close()

    return Stats(
        material_count=material_count,
        paper_count=paper_count,
        cart_count=cart_count,
        last_update=last_session["created_at"] if last_session else None,
    )


@router.get("/sessions/latest")
def get_latest_session():
    """返回最近一次工作区 AI 点评。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM workspace_reviews ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()

    if not row:
        return None

    session = dict_from_row(row)

    # 解析 JSON 字段
    if session.get("ai_review"):
        try:
            session["ai_review"] = json.loads(session["ai_review"])
        except (json.JSONDecodeError, TypeError):
            pass

    if session.get("task_ids"):
        try:
            session["task_ids"] = json.loads(session["task_ids"])
        except (json.JSONDecodeError, TypeError):
            pass

    return session
