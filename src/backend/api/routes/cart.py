"""购物车 + AI 深度分析"""
import json
import asyncio
import threading
import traceback
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional
from storage.workspace import get_active_connection as get_connection
from storage.database import dict_from_row

router = APIRouter()


class CartAnalyzeRequest(BaseModel):
    paper_ids: List[int]


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


@router.post("/cart/analyze")
def analyze_cart_papers(body: CartAnalyzeRequest):
    """对购物车中指定论文进行 AI 深度分析（后台线程）。"""
    if not body.paper_ids:
        return {"ok": False, "message": "未选择论文"}

    thread = threading.Thread(target=_run_cart_analyze, args=(body.paper_ids,), daemon=True)
    thread.start()
    return {"ok": True, "message": f"开始分析 {len(body.paper_ids)} 篇论文"}


@router.post("/cart/analyze/all")
def analyze_all_cart():
    """分析购物车中全部论文。"""
    conn = get_connection()
    paper_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM papers WHERE in_cart = 1"
    ).fetchall()]
    conn.close()

    if not paper_ids:
        return {"ok": False, "message": "购物车为空"}

    thread = threading.Thread(target=_run_cart_analyze, args=(paper_ids,), daemon=True)
    thread.start()
    return {"ok": True, "message": f"开始分析 {len(paper_ids)} 篇论文"}


def _run_cart_analyze(paper_ids: List[int]):
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_do_cart_analyze(paper_ids))
    except Exception as e:
        traceback.print_exc()
    finally:
        loop.close()


async def _do_cart_analyze(paper_ids: List[int]):
    """逐篇深度分析购物车论文。"""
    from processors.registry import get as get_processor
    analyzer = get_processor("llm")
    if not analyzer:
        return

    conn = get_connection()

    for pid in paper_ids:
        paper = conn.execute("SELECT * FROM papers WHERE id = ?", (pid,)).fetchone()
        if not paper:
            continue
        paper = dict_from_row(paper)

        try:
            result = await analyzer.analyze(paper)
        except Exception as e:
            print(f"[cart-ai] analyze error paper#{pid}: {e}")
            continue

        if not result.get("analyzed"):
            continue

        conn.execute(
            """UPDATE papers SET
               has_code = ?, code_url = ?,
               ai_innovation = ?, ai_technologies = ?,
               ai_code_url = ?, ai_analyzed = 1, cart_ai_analyzed = 1
               WHERE id = ?""",
            (
                int(result.get("has_code", False)),
                result.get("code_url") or paper.get("code_url"),
                result.get("innovation"),
                result.get("technologies", "[]"),
                result.get("code_url"),
                pid,
            ),
        )
        conn.commit()
        await asyncio.sleep(0.5)

    conn.close()
    print(f"[cart-ai] analyzed {len(paper_ids)} papers")
