"""购物车"""
from fastapi import APIRouter, Query
from storage.workspace import get_active_connection as get_connection
from storage.database import dict_from_row

router = APIRouter()


@router.get("/cart")
def get_cart():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM papers WHERE in_cart = 1 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]


@router.get("/cart/export")
def export_cart(format: str = Query("csv")):
    conn = get_connection()
    rows = conn.execute(
        "SELECT title, authors, journal_name, publish_year, code_url "
        "FROM papers WHERE in_cart = 1 ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    if format == "csv":
        import io, csv

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["标题", "作者", "期刊", "年份", "代码链接"])
        for r in rows:
            writer.writerow([r["title"], r["authors"], r["journal_name"],
                             r["publish_year"], r["code_url"] or ""])
        return {"format": "csv", "data": output.getvalue()}

    return [dict_from_row(r) for r in rows]
