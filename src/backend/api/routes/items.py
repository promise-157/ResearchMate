"""Generic material item API."""
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status as http_status
from fastapi.responses import FileResponse

from services.material_analysis import (
    analyze_material, compare_materials, list_comparison_runs, list_material_runs,
)
from services.materials import get_material, import_text_material, list_materials, update_material
from services.image_materials import get_asset_file, import_image_material, run_local_ocr
from services.accepted_extractions import accept_extraction
from services.template_registry import (
    confirm_item_template as confirm_template,
    extract_item_template as extract_template,
    get_item_template as get_template,
)
from services.similarity import find_similar_items
from storage.models import (
    MaterialAnalysisRequest, MaterialComparisonRequest, MaterialCreate, MaterialUpdate,
    TemplateConfirmationRequest,
)


router = APIRouter()
STORED_TYPES = {"general", "paper", "job", "debug"}
STATUSES = {"inbox", "active", "archived"}


@router.post("/items/import-image")
async def import_image(file: UploadFile = File(...), title: str = Form("")):
    data = await file.read(10 * 1024 * 1024 + 1)
    try:
        item, created = import_image_material(
            filename=file.filename or "image", data=data, title=title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item, "created": created, "duplicate": not created}


@router.get("/assets/{asset_id}/content")
def get_asset_content(asset_id: int):
    try:
        found = get_asset_file(asset_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=404, detail="资产不存在")
    asset, path = found
    return FileResponse(path, media_type=asset["mime_type"], filename=asset["original_name"])


@router.get("/items/analysis-comparisons")
def get_comparison_runs():
    return {"runs": list_comparison_runs()}


@router.post("/items/analysis-comparisons")
async def create_comparison_run(body: MaterialComparisonRequest):
    try:
        run, reused = await compare_materials(
            body.item_ids, input_fields=body.input_fields
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"run": run, "reused": reused}


@router.post("/items")
def create_item(body: MaterialCreate, response: Response):
    try:
        item, created = import_text_material(
            content_text=body.content_text,
            title=body.title,
            item_type=body.item_type,
            source_url=str(body.source_url) if body.source_url else None,
            tags=body.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response.status_code = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return {"created": created, "duplicate": not created, "item": item}


@router.get("/items")
def list_items(
    q: str | None = Query(None, max_length=200),
    item_type: str | None = Query(None),
    status: str | None = Query(None),
    debug_error: Annotated[str | None, Query(max_length=200)] = None,
    job_company: Annotated[str | None, Query(max_length=200)] = None,
    job_role: Annotated[str | None, Query(max_length=200)] = None,
    job_application_status: Annotated[str | None, Query(max_length=200)] = None,
    include_accepted_extractions: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if item_type and item_type not in STORED_TYPES:
        raise HTTPException(status_code=400, detail="未知资料类型")
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail="未知资料状态")
    return list_materials(
        query=q,
        item_type=item_type,
        status=status,
        debug_error=debug_error,
        job_company=job_company,
        job_role=job_role,
        job_application_status=job_application_status,
        include_accepted_extractions=include_accepted_extractions,
        page=page,
        page_size=page_size,
    )


@router.get("/items/{item_id}")
def get_item(item_id: int):
    item = get_material(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="资料不存在")
    return item


@router.get("/items/{item_id}/template")
def get_item_template(item_id: int):
    try:
        template = get_template(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not template:
        raise HTTPException(status_code=404, detail="资料不存在")
    return template


@router.post("/items/{item_id}/template/extract")
def extract_item_template(item_id: int):
    try:
        template = extract_template(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not template:
        raise HTTPException(status_code=404, detail="资料不存在")
    return template


@router.put("/items/{item_id}/template/confirmation")
def confirm_item_template(item_id: int, body: TemplateConfirmationRequest):
    try:
        template = confirm_template(item_id, body.root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not template:
        raise HTTPException(status_code=404, detail="资料不存在")
    return template


@router.get("/items/{item_id}/similar")
def get_similar_items(
    item_id: int,
    threshold: float = Query(0.2, ge=0, le=1),
    limit: int = Query(10, ge=1, le=50),
):
    matches = find_similar_items(item_id, threshold=threshold, limit=limit)
    if matches is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    return {"algorithm": "token-jaccard-v1", "matches": matches}


@router.patch("/items/{item_id}")
def update_item(item_id: int, body: MaterialUpdate):
    try:
        item = update_material(
            item_id,
            title=body.title,
            item_type=body.item_type,
            status=body.status,
            tags=body.tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not item:
        raise HTTPException(status_code=404, detail="资料不存在")
    return item


@router.get("/items/{item_id}/analysis-runs")
def get_analysis_runs(item_id: int):
    runs = list_material_runs(item_id)
    if runs is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    return {"runs": runs}


@router.post("/items/{item_id}/analysis-runs")
async def create_analysis_run(item_id: int, body: MaterialAnalysisRequest):
    try:
        run, reused = await analyze_material(
            item_id,
            analysis_type=body.analysis_type,
            input_fields=body.input_fields,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    return {"run": run, "reused": reused}


@router.post("/items/{item_id}/ocr-runs")
def create_ocr_run(item_id: int):
    try:
        run = run_local_ocr(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    return {"run": run}


@router.post("/items/{item_id}/extraction-runs/{run_id}/accept")
def accept_item_extraction(item_id: int, run_id: int):
    try:
        accepted = accept_extraction(item_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if accepted is None:
        raise HTTPException(status_code=404, detail="资料不存在")
    return {"accepted_extraction": accepted}
