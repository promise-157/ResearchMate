"""Public-source discovery API."""
from fastapi import APIRouter, HTTPException, status

from services.discoveries import (
    check_code_evidence, delete_discovery_rule, discover_arxiv, discover_crossref,
    enrich_openalex, list_collection_jobs, list_discovery_rules, run_all_discovery_rules,
    run_discovery_rule, save_discovery_rule, update_discovery_rule,
)
from services.candidate_insights import (
    create_candidate_brief, list_candidate_briefs, rank_candidates,
)
from storage.models import (
    ArxivDiscoveryRequest, CandidateBriefRequest, CandidateRankingRequest,
    CodeEvidenceRequest, CrossrefDiscoveryRequest,
    OpenAlexEnrichmentRequest, SavedDiscoveryRuleCreate, SavedDiscoveryRuleUpdate,
)


router = APIRouter()


@router.post("/discoveries/candidates/rank")
def rank_discovery_candidates(body: CandidateRankingRequest):
    try:
        ranking = rank_candidates(
            body.candidate_ids, focus=body.focus,
            preferred_journal=body.preferred_journal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ranking": ranking}


@router.get("/discoveries/candidates/briefs")
def get_candidate_briefs():
    return {"runs": list_candidate_briefs()}


@router.post("/discoveries/candidates/briefs", status_code=status.HTTP_201_CREATED)
async def create_discovery_candidate_brief(body: CandidateBriefRequest):
    try:
        run = await create_candidate_brief(
            body.candidate_ids, focus=body.focus,
            preferred_journal=body.preferred_journal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": run["status"] == "succeeded", "run": run}


@router.get("/discovery-rules")
def get_discovery_rules():
    return {"rules": list_discovery_rules()}


@router.post("/discovery-rules", status_code=status.HTTP_201_CREATED)
def create_discovery_rule(body: SavedDiscoveryRuleCreate):
    try:
        return save_discovery_rule(body.name, body.query.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/discovery-rules/{rule_id}")
def replace_discovery_rule(rule_id: int, body: SavedDiscoveryRuleUpdate):
    try:
        return update_discovery_rule(rule_id, body.name, body.query.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/discovery-rules/run", status_code=status.HTTP_201_CREATED)
async def run_saved_discovery_rules():
    try:
        results = await run_all_discovery_rules()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"results": results}


@router.delete("/discovery-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_discovery_rule(rule_id: int):
    try:
        delete_discovery_rule(rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/discovery-rules/{rule_id}/run", status_code=status.HTTP_201_CREATED)
async def run_saved_discovery_rule(rule_id: int):
    try:
        job, candidates = await run_discovery_rule(rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job": job, "candidates": candidates}


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


@router.post("/discoveries/crossref", status_code=status.HTTP_201_CREATED)
async def create_crossref_discovery(body: CrossrefDiscoveryRequest):
    try:
        job, candidates = await discover_crossref(body.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job": job, "candidates": candidates}


@router.post("/discoveries/openalex/enrich", status_code=status.HTTP_201_CREATED)
async def create_openalex_enrichment(body: OpenAlexEnrichmentRequest):
    try:
        job, candidates = await enrich_openalex(body.candidate_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job": job, "candidates": candidates}


@router.post("/discoveries/code/evidence", status_code=status.HTTP_201_CREATED)
async def create_code_evidence(body: CodeEvidenceRequest):
    try:
        job, candidates = await check_code_evidence(body.candidate_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job": job, "candidates": candidates}
