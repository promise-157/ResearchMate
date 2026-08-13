"""Application workflow for turning selected materials into user-owned action projects."""
from typing import Any

from storage import action_projects as project_repository
from storage import items as item_repository
from storage.workspace import get_active_connection


UPDATABLE_FIELDS = {"title", "objective", "notes", "next_action", "status"}


def _validated_item_ids(conn: Any, item_ids: list[int]) -> list[int]:
    unique_ids = list(dict.fromkeys(item_ids))
    if len(unique_ids) != len(item_ids):
        raise ValueError("证据清单不能包含重复资料")
    if not 1 <= len(unique_ids) <= 20:
        raise ValueError("请选择 1–20 条资料作为证据")
    if len(item_repository.get_items_by_ids(conn, unique_ids)) != len(unique_ids):
        raise ValueError("部分资料不属于当前工作区，请刷新后重新选择")
    return unique_ids


def list_action_projects() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return project_repository.list_projects(conn)
    finally:
        conn.close()


def get_action_project(project_id: int) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        return project_repository.get_project(conn, project_id)
    finally:
        conn.close()


def create_action_project(data: dict[str, Any]) -> dict[str, Any]:
    conn = get_active_connection()
    try:
        item_ids = _validated_item_ids(conn, data["item_ids"])
        title = data["title"].strip()
        if not title:
            raise ValueError("专题标题不能为空")
        return project_repository.create_project(
            conn,
            title=title,
            objective=data["objective"].strip(),
            notes=data["notes"].strip(),
            next_action=data["next_action"].strip(),
            item_ids=item_ids,
        )
    finally:
        conn.close()


def update_action_project(
    project_id: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        if any(key not in UPDATABLE_FIELDS for key in data):
            raise ValueError("行动专题包含不可更新的字段")
        fields = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in data.items()
            if value is not None
        }
        if "title" in fields and not fields["title"]:
            raise ValueError("专题标题不能为空")
        return project_repository.update_project(conn, project_id, fields)
    finally:
        conn.close()


def replace_action_project_materials(
    project_id: int, item_ids: list[int]
) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        if project_repository.get_project(conn, project_id) is None:
            return None
        validated = _validated_item_ids(conn, item_ids)
        return project_repository.replace_materials(conn, project_id, validated)
    finally:
        conn.close()
