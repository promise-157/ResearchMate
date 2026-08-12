"""Shopping cart and audited, per-paper AI analysis."""
import csv
import io
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services import paper_analysis as paper_analysis_service


router = APIRouter()
MAX_AI_PAPERS = paper_analysis_service.MAX_PAPERS


PaperId = Annotated[int, Field(strict=True, gt=0)]


class CartAnalyzeRequest(BaseModel):
    paper_ids: list[PaperId] = Field(min_length=1, max_length=MAX_AI_PAPERS)


@router.get("/cart")
def get_cart():
    return paper_analysis_service.list_cart_papers()


@router.get("/cart/export")
def export_cart(format: str = Query("csv")):
    rows = paper_analysis_service.list_cart_export_rows()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["标题", "作者", "期刊", "年份", "代码链接"])
        for row in rows:
            writer.writerow(
                [
                    row["title"],
                    row["authors"],
                    row["journal_name"],
                    row["publish_year"],
                    row["code_url"] or "",
                ]
            )
        return {"format": "csv", "data": output.getvalue()}

    return rows


@router.post("/cart/analyze")
async def analyze_cart_papers(body: CartAnalyzeRequest):
    try:
        return await paper_analysis_service.analyze_cart_papers(body.paper_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/cart/analyze/all")
async def analyze_all_cart():
    paper_ids = paper_analysis_service.list_cart_paper_ids()
    if not paper_ids:
        raise HTTPException(status_code=422, detail="购物车为空")
    if len(paper_ids) > MAX_AI_PAPERS:
        raise HTTPException(
            status_code=422,
            detail=f"单次最多分析 {MAX_AI_PAPERS} 篇，请缩小清单",
        )
    try:
        return await paper_analysis_service.analyze_cart_papers(paper_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
