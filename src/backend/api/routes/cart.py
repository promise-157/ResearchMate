"""购物车 + AI 深度分析"""
import csv
import io
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import List
from storage.workspace import get_active_connection as get_connection
from storage.database import dict_from_row

router = APIRouter()
MAX_AI_PAPERS = 20


class CartAnalyzeRequest(BaseModel):
    paper_ids: List[int] = Field(max_length=MAX_AI_PAPERS)


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
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["标题", "作者", "期刊", "年份", "代码链接"])
        for r in rows:
            writer.writerow([r["title"], r["authors"], r["journal_name"],
                             r["publish_year"], r["code_url"] or ""])
        return {"format": "csv", "data": output.getvalue()}

    return [dict_from_row(r) for r in rows]


@router.post("/cart/analyze")
async def analyze_cart_papers(body: CartAnalyzeRequest):
    """Analyze selected papers and return only after results are stored."""
    if not body.paper_ids:
        return {"ok": False, "message": "未选择论文"}

    analyzed = await _do_cart_analyze(body.paper_ids)
    return {
        "ok": analyzed > 0,
        "analyzed": analyzed,
        "requested": len(body.paper_ids),
        "message": "" if analyzed else "未生成有效分析，请检查 AI 配置与模型响应",
    }


@router.post("/cart/analyze/all")
async def analyze_all_cart():
    """分析购物车中全部论文。"""
    conn = get_connection()
    paper_ids = [r["id"] for r in conn.execute(
        "SELECT id FROM papers WHERE in_cart = 1"
    ).fetchall()]
    conn.close()

    if not paper_ids:
        return {"ok": False, "message": "购物车为空"}
    if len(paper_ids) > MAX_AI_PAPERS:
        return {"ok": False, "message": f"单次最多分析 {MAX_AI_PAPERS} 篇，请缩小清单"}

    analyzed = await _do_cart_analyze(paper_ids)
    return {
        "ok": analyzed > 0,
        "analyzed": analyzed,
        "requested": len(paper_ids),
        "message": "" if analyzed else "未生成有效分析，请检查 AI 配置与模型响应",
    }


async def _do_cart_analyze(paper_ids: List[int]):
    """逐篇深度分析购物车论文。"""
    from processors.registry import get as get_processor
    analyzer = get_processor("llm")
    if not analyzer:
        return 0

    conn = get_connection()
    analyzed_count = 0

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
                int(bool(result.get("has_code")) or bool(paper.get("has_code"))),
                result.get("code_url") or paper.get("code_url"),
                result.get("innovation"),
                result.get("technologies", "[]"),
                result.get("code_url"),
                pid,
            ),
        )
        conn.commit()
        analyzed_count += 1

    conn.close()
    return analyzed_count
