"""Public-source discovery API."""
from fastapi import APIRouter, HTTPException, status

from services.discoveries import discover_arxiv, list_collection_jobs
from storage.models import ArxivDiscoveryRequest


router = APIRouter()


@router.get("/collection-jobs")
def get_collection_jobs():
    return {"jobs": list_collection_jobs()}


@router.post("/discoveries/arxiv", status_code=status.HTTP_201_CREATED)
async def create_arxiv_discovery(body: ArxivDiscoveryRequest):
    try:
        job, candidates = await discover_arxiv(body.query, limit=body.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job": job, "candidates": candidates}
