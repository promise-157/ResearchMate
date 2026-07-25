"""工作区管理 API"""
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from storage.database import get_connection as get_main_conn, dict_from_row
from storage.workspace import (
    get_active_path, switch_workspace, create_workspace,
    delete_workspace_file, clear_workspace, WORKSPACE_DIR,
)

router = APIRouter()


@router.get("/workspaces")
def list_workspaces():
    """列出所有工作区 + 当前活跃信息。"""
    conn = get_main_conn()

    # 确保 workspaces 表存在
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            db_path     TEXT NOT NULL,
            paper_count INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            opened_at   TEXT DEFAULT (datetime('now'))
        );
    """)

    rows = conn.execute("SELECT * FROM workspaces ORDER BY opened_at DESC").fetchall()
    conn.close()

    active_path = get_active_path()
    return {
        "active_path": active_path,
        "active_name": os.path.basename(active_path).replace(".db", ""),
        "items": [dict_from_row(r) for r in rows],
    }


@router.post("/workspaces")
def create_workspace_api(name: str = ""):
    """创建新工作区。"""
    name = name.strip() or f"workspace_{datetime.now().strftime('%Y%m%d_%H%M')}"
    db_path = create_workspace(name)
    display_name = os.path.basename(db_path).replace(".db", "")

    conn = get_main_conn()
    conn.execute(
        "INSERT INTO workspaces (name, db_path) VALUES (?, ?)",
        (display_name, db_path),
    )
    conn.commit()
    conn.close()

    switch_workspace(db_path)
    return {"ok": True, "name": display_name, "db_path": db_path}


@router.post("/workspaces/load")
def load_workspace_api(db_path: str = ""):
    """切换到指定工作区。"""
    if not db_path or not os.path.isfile(db_path):
        raise HTTPException(status_code=404, detail="工作区文件不存在")

    if not switch_workspace(db_path):
        raise HTTPException(status_code=500, detail="切换失败")

    # 更新最后打开时间
    conn = get_main_conn()
    conn.execute(
        "UPDATE workspaces SET opened_at = ? WHERE db_path = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M"), db_path),
    )
    conn.commit()
    conn.close()

    return {"ok": True, "db_path": db_path}


@router.delete("/workspaces/{workspace_id}")
def delete_workspace_api(workspace_id: int):
    """删除工作区。"""
    conn = get_main_conn()
    row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="工作区不存在")

    db_path = row["db_path"]
    conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
    conn.commit()
    conn.close()

    delete_workspace_file(db_path)
    return {"ok": True}


@router.post("/workspaces/current/clear")
def clear_current_workspace():
    """清空当前工作区论文数据。"""
    clear_workspace()

    # 更新主DB中的计数
    active_path = get_active_path()
    conn = get_main_conn()
    conn.execute(
        "UPDATE workspaces SET paper_count = 0 WHERE db_path = ?",
        (active_path,),
    )
    conn.commit()
    conn.close()

    return {"ok": True}
