"""工作区管理 API"""
import os
import tempfile
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from services.workspace_archives import (
    MAX_ARCHIVE_BYTES,
    WorkspaceArchiveError,
    create_workspace_archive,
    import_workspace_upload,
    remove_temporary_export,
)
from storage.database import get_connection as get_main_conn, dict_from_row
from storage.workspace import (
    get_active_path, switch_workspace, create_workspace,
    delete_workspace_file, clear_workspace,
    get_active_connection,
    WorkspaceBusyError,
)

router = APIRouter()


@router.get("/workspaces")
def list_workspaces():
    """列出所有工作区 + 当前活跃信息。"""
    conn = get_main_conn()
    active_path = get_active_path()

    # 确保 workspaces 表存在
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            db_path     TEXT NOT NULL,
            paper_count INTEGER DEFAULT 0,
            item_count  INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            opened_at   TEXT DEFAULT (datetime('now'))
        );
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(workspaces)").fetchall()}
    if "item_count" not in columns:
        conn.execute("ALTER TABLE workspaces ADD COLUMN item_count INTEGER DEFAULT 0")

    active_conn = get_active_connection()
    try:
        paper_count = active_conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        item_count = active_conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    finally:
        active_conn.close()
    existing = conn.execute(
        "SELECT id FROM workspaces WHERE db_path = ?", (active_path,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE workspaces SET paper_count = ?, item_count = ? WHERE id = ?",
            (paper_count, item_count, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO workspaces (name, db_path, paper_count, item_count) VALUES (?, ?, ?, ?)",
            (
                os.path.basename(active_path).removesuffix(".db"),
                active_path,
                paper_count,
                item_count,
            ),
        )
    conn.commit()

    rows = conn.execute("SELECT * FROM workspaces ORDER BY opened_at DESC").fetchall()
    conn.close()

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
    if not db_path or not switch_workspace(db_path):
        raise HTTPException(status_code=404, detail="工作区文件不存在")
    active_path = get_active_path()

    # 更新最后打开时间
    conn = get_main_conn()
    conn.execute(
        "UPDATE workspaces SET opened_at = ? WHERE db_path = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M"), active_path),
    )
    conn.commit()
    conn.close()

    return {"ok": True, "db_path": active_path}


@router.delete("/workspaces/{workspace_id}")
def delete_workspace_api(workspace_id: int):
    """删除工作区。"""
    conn = get_main_conn()
    row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="工作区不存在")

    db_path = row["db_path"]
    conn.close()
    try:
        delete_workspace_file(db_path)
    except WorkspaceBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    conn = get_main_conn()
    conn.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

@router.get("/workspace/export")
def export_workspace():
    """Download a consistent database + asset archive for the current workspace."""
    try:
        exported = create_workspace_archive()
    except WorkspaceArchiveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return FileResponse(
        exported.path,
        media_type="application/zip",
        filename=exported.filename,
        background=BackgroundTask(remove_temporary_export, exported.path),
    )


@router.post("/workspace/import")
async def import_workspace(file: UploadFile = File(...)):
    """Upload a portable archive, or a legacy asset-free SQLite database."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="请选择工作区归档文件")
    upload_fd, upload_name = tempfile.mkstemp(
        prefix="researchmate-upload-", suffix=".upload"
    )
    os.close(upload_fd)
    size = 0
    try:
        with open(upload_name, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_ARCHIVE_BYTES:
                    raise HTTPException(status_code=413, detail="工作区归档文件不能超过 512 MB")
                output.write(chunk)
        imported = import_workspace_upload(Path(upload_name), file.filename)
    except WorkspaceArchiveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    finally:
        if os.path.exists(upload_name):
            os.remove(upload_name)

    # 注册到主DB
    previous_path = get_active_path()
    conn = get_main_conn()
    try:
        conn.execute(
            "INSERT INTO workspaces (name, db_path) VALUES (?, ?)",
            (imported.name, imported.db_path),
        )
        conn.commit()
        if not switch_workspace(imported.db_path):
            raise RuntimeError("导入后的工作区无法加载")
    except Exception as exc:
        conn.rollback()
        if get_active_path() == imported.db_path:
            switch_workspace(previous_path)
        try:
            conn.execute("DELETE FROM workspaces WHERE db_path = ?", (imported.db_path,))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            delete_workspace_file(imported.db_path)
        except Exception:
            pass
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="工作区注册失败") from exc
    finally:
        conn.close()
    return {
        "ok": True,
        "name": imported.name,
        "db_path": imported.db_path,
        "legacy_database_only": imported.legacy_database_only,
    }


@router.post("/workspaces/current/clear")
def clear_current_workspace():
    """清空当前工作区论文数据。"""
    try:
        clear_workspace()
    except WorkspaceBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    active_path = get_active_path()
    conn = get_main_conn()
    conn.execute(
        "UPDATE workspaces SET paper_count = 0, item_count = 0 WHERE db_path = ?",
        (active_path,),
    )
    conn.commit()
    conn.close()

    return {"ok": True}
