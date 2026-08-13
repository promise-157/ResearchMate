"""HTTP boundary for user-owned action projects."""
from fastapi import APIRouter, HTTPException

from services.action_projects import (
    create_action_project,
    get_action_project,
    list_action_projects,
    replace_action_project_materials,
    update_action_project,
)
from storage.models import (
    ActionProjectCreate,
    ActionProjectMaterialsUpdate,
    ActionProjectUpdate,
)


router = APIRouter()


@router.get("/action-projects")
def list_projects():
    return {"projects": list_action_projects()}


@router.post("/action-projects", status_code=201)
def create_project(body: ActionProjectCreate):
    try:
        return {"project": create_action_project(body.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/action-projects/{project_id}")
def get_project(project_id: int):
    project = get_action_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="行动专题不存在")
    return {"project": project}


@router.patch("/action-projects/{project_id}")
def update_project(project_id: int, body: ActionProjectUpdate):
    try:
        project = update_action_project(project_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="行动专题不存在")
    return {"project": project}


@router.put("/action-projects/{project_id}/materials")
def replace_project_materials(project_id: int, body: ActionProjectMaterialsUpdate):
    try:
        project = replace_action_project_materials(project_id, body.item_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="行动专题不存在")
    return {"project": project}
