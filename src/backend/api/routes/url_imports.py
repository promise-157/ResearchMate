"""Single public URL import and candidate review API."""
from fastapi import APIRouter, HTTPException, Query, Response, status as http_status

from services.url_imports import (
    accept_candidate,
    get_candidate,
    import_public_url,
    list_candidates,
    list_url_imports,
    reject_candidate,
)
from storage.models import PublicURLImportRequest


router = APIRouter()
CANDIDATE_STATUSES = {"pending", "accepted", "rejected"}


@router.get("/url-imports")
def get_url_imports():
    return {"jobs": list_url_imports()}


@router.post("/url-imports", status_code=http_status.HTTP_201_CREATED)
async def create_url_import(body: PublicURLImportRequest):
    try:
        job, candidate = await import_public_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job": job, "candidate": candidate}


@router.get("/candidates")
def get_candidates(status: str | None = Query(None)):
    if status and status not in CANDIDATE_STATUSES:
        raise HTTPException(status_code=400, detail="未知候选状态")
    return {"candidates": list_candidates(status=status)}


@router.get("/candidates/{candidate_id}")
def get_candidate_detail(candidate_id: int):
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="候选不存在")
    return candidate


@router.post("/candidates/{candidate_id}/accept")
def accept_candidate_route(candidate_id: int, response: Response):
    try:
        result = accept_candidate(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="候选不存在")
    candidate, item, duplicate = result
    response.status_code = http_status.HTTP_200_OK if duplicate else http_status.HTTP_201_CREATED
    return {"candidate": candidate, "item": item, "duplicate": duplicate}


@router.post("/candidates/{candidate_id}/reject")
def reject_candidate_route(candidate_id: int):
    try:
        candidate = reject_candidate(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not candidate:
        raise HTTPException(status_code=404, detail="候选不存在")
    return candidate
