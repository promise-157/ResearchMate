"""论文查询"""
from fastapi import APIRouter, Query, HTTPException
from storage.workspace import get_active_connection as get_connection
from storage.database import dict_from_row
from storage.models import PaperUpdate

router = APIRouter()


@router.get("/papers")
def list_papers(
    q: str = Query(None, description="搜索关键词"),
    has_code: bool = Query(None),
    in_cart: bool = Query(None),
    source_id: int = Query(None),
    keywords: str = Query(None),
    kw_mode: str = Query("or"),
    sort: str = Query("newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_connection()

    where = ["1=1"]
    params = []

    if q:
        where.append("(title LIKE ? OR authors LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if has_code is not None:
        where.append("has_code = ?")
        params.append(int(has_code))
    if in_cart is not None:
        where.append("in_cart = ?")
        params.append(int(in_cart))
    if source_id is not None:
        where.append("source_id = ?")
        params.append(source_id)

    if keywords:
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if kw_list:
            if kw_mode == "and":
                for kw in kw_list:
                    where.append("auto_keywords LIKE ?")
                    params.append(f"%{kw}%")
            else:
                or_clauses = []
                for kw in kw_list:
                    or_clauses.append("auto_keywords LIKE ?")
                    params.append(f"%{kw}%")
                where.append(f"({' OR '.join(or_clauses)})")

    order = "publish_year DESC"
    if sort == "oldest":
        order = "publish_year ASC"
    elif sort == "title_asc":
        order = "title ASC"

    where_clause = " AND ".join(where)

    # Count
    total = conn.execute(
        f"SELECT COUNT(*) FROM papers WHERE {where_clause}", params
    ).fetchone()[0]

    # Page
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT * FROM papers WHERE {where_clause} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()

    conn.close()
    return {
        "items": [dict_from_row(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/papers/{paper_id}")
def get_paper(paper_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="论文不存在")
    return dict_from_row(row)




@router.patch("/papers/{paper_id}")
def update_paper(paper_id: int, body: PaperUpdate):
    conn = get_connection()
    if body.in_cart is not None:
        conn.execute(
            "UPDATE papers SET in_cart = ? WHERE id = ?",
            (int(body.in_cart), paper_id),
        )
    conn.commit()
    row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="论文不存在")
    return dict_from_row(row)
