"""HTTP boundary for audited workspace paper reviews."""
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import workspace_review as review_service


router = APIRouter()
PaperId = Annotated[int, Field(strict=True, gt=0)]


class WorkspaceReviewRequest(BaseModel):
    paper_ids: list[PaperId] = Field(
        min_length=review_service.MIN_PAPERS,
        max_length=review_service.MAX_PAPERS,
    )


@router.get("/workspace/reviews")
def list_workspace_reviews():
    return review_service.list_review_history()


@router.post("/workspace/reviews")
async def create_workspace_review(body: WorkspaceReviewRequest):
    try:
        run = await review_service.create_review(body.paper_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": run["status"] == "succeeded", "run": run}
