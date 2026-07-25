"""关键词 API"""
import json
from collections import Counter
from fastapi import APIRouter
from storage.workspace import get_active_connection as get_connection

router = APIRouter()


@router.get("/keywords")
def get_keywords():
    """返回当前工作区的关键词统计（Top-30）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT auto_keywords FROM papers WHERE auto_keywords IS NOT NULL AND auto_keywords != '[]'"
    ).fetchall()
    conn.close()

    counter = Counter()
    for r in rows:
        try:
            for k in json.loads(r["auto_keywords"]):
                counter[k] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    return [{"keyword": k, "count": v} for k, v in counter.most_common(30)]
