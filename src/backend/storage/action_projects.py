"""Repository for user-owned action projects and ordered material evidence."""
import json
import sqlite3
from typing import Any


def _decode_project(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _decode_material(row: sqlite3.Row) -> dict[str, Any]:
    material = dict(row)
    for source, target, fallback in (
        ("tags_json", "tags", []),
        ("metadata_json", "metadata", {}),
    ):
        raw = material.pop(source, None)
        try:
            material[target] = json.loads(raw) if raw else fallback
        except (json.JSONDecodeError, TypeError):
            material[target] = fallback
    return material


def list_projects(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT action_projects.*, COUNT(action_project_items.item_id) AS material_count
           FROM action_projects
           LEFT JOIN action_project_items
             ON action_project_items.project_id = action_projects.id
           GROUP BY action_projects.id
           ORDER BY CASE action_projects.status
                      WHEN 'active' THEN 0 WHEN 'completed' THEN 1 ELSE 2 END,
                    action_projects.updated_at DESC, action_projects.id DESC"""
    ).fetchall()
    return [dict(row) for row in rows]


def get_project(conn: sqlite3.Connection, project_id: int) -> dict[str, Any] | None:
    project = _decode_project(conn.execute(
        "SELECT * FROM action_projects WHERE id = ?", (project_id,)
    ).fetchone())
    if project is None:
        return None
    rows = conn.execute(
        """SELECT items.*, action_project_items.position
           FROM action_project_items
           JOIN items ON items.id = action_project_items.item_id
           WHERE action_project_items.project_id = ?
           ORDER BY action_project_items.position""",
        (project_id,),
    ).fetchall()
    project["materials"] = [_decode_material(row) for row in rows]
    project["material_count"] = len(project["materials"])
    return project


def create_project(
    conn: sqlite3.Connection,
    *,
    title: str,
    objective: str,
    notes: str,
    next_action: str,
    item_ids: list[int],
) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO action_projects(title, objective, notes, next_action)
           VALUES (?, ?, ?, ?)""",
        (title, objective, notes, next_action),
    )
    project_id = cursor.lastrowid
    conn.executemany(
        """INSERT INTO action_project_items(project_id, item_id, position)
           VALUES (?, ?, ?)""",
        ((project_id, item_id, position) for position, item_id in enumerate(item_ids)),
    )
    conn.commit()
    return get_project(conn, project_id)


def update_project(
    conn: sqlite3.Connection, project_id: int, fields: dict[str, str]
) -> dict[str, Any] | None:
    if not fields:
        return get_project(conn, project_id)
    assignments = [f"{field} = ?" for field in fields]
    params = [*fields.values(), project_id]
    cursor = conn.execute(
        f"""UPDATE action_projects
            SET {', '.join(assignments)}, updated_at = datetime('now')
            WHERE id = ?""",
        params,
    )
    if cursor.rowcount == 0:
        conn.rollback()
        return None
    conn.commit()
    return get_project(conn, project_id)


def replace_materials(
    conn: sqlite3.Connection, project_id: int, item_ids: list[int]
) -> dict[str, Any] | None:
    if conn.execute(
        "SELECT 1 FROM action_projects WHERE id = ?", (project_id,)
    ).fetchone() is None:
        return None
    try:
        conn.execute(
            "DELETE FROM action_project_items WHERE project_id = ?", (project_id,)
        )
        conn.executemany(
            """INSERT INTO action_project_items(project_id, item_id, position)
               VALUES (?, ?, ?)""",
            ((project_id, item_id, position) for position, item_id in enumerate(item_ids)),
        )
        conn.execute(
            "UPDATE action_projects SET updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_project(conn, project_id)
