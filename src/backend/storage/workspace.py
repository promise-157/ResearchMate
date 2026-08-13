"""
工作区管理。每个工作区是独立的 SQLite 文件，存放在 data/workspaces/ 下。
"""
import os
import sqlite3
import shutil
import threading
from pathlib import Path
from typing import Optional


# 工作区目录
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "workspaces"

# 当前活跃的工作区（内存中）
_active_db_path: Optional[str] = None
_workspace_lock = threading.RLock()
_workspace_leases: dict[str, int] = {}


class WorkspaceBusyError(RuntimeError):
    """A destructive workspace action was refused while requests still use it."""


class _LeasedWorkspaceConnection(sqlite3.Connection):
    _workspace_lease_path: str | None = None
    _workspace_lease_released = False

    def close(self) -> None:
        super().close()
        if self._workspace_lease_released or not self._workspace_lease_path:
            return
        with _workspace_lock:
            path = self._workspace_lease_path
            remaining = _workspace_leases.get(path, 1) - 1
            if remaining > 0:
                _workspace_leases[path] = remaining
            else:
                _workspace_leases.pop(path, None)
            self._workspace_lease_released = True

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def _workspace_is_busy(db_path: str) -> bool:
    return _workspace_leases.get(str(Path(db_path).resolve()), 0) > 0


def _ensure_dir():
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def get_active_path() -> str:
    """获取当前活跃工作区的数据库路径。"""
    global _active_db_path
    with _workspace_lock:
        _ensure_dir()

        if _active_db_path and os.path.isfile(_active_db_path):
            return _active_db_path

        # 回退到默认工作区
        default = str(WORKSPACE_DIR / "default.db")
        if not os.path.isfile(default):
            _init_workspace_db(default)
        _active_db_path = default
        return default


def get_active_connection() -> sqlite3.Connection:
    """Open a connection pinned to the workspace active at call time."""
    with _workspace_lock:
        db_path = get_active_path()
        resolved_path = str(Path(db_path).resolve())
        conn = sqlite3.connect(resolved_path, factory=_LeasedWorkspaceConnection)
        conn._workspace_lease_path = resolved_path
        _workspace_leases[resolved_path] = _workspace_leases.get(resolved_path, 0) + 1
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            _migrate_workspace_db(conn)
            return conn
        except Exception:
            conn.close()
            raise


def switch_workspace(db_path: str) -> bool:
    """切换到指定工作区。"""
    global _active_db_path
    with _workspace_lock:
        if not _is_workspace_path(db_path) or not os.path.isfile(db_path):
            return False
        _active_db_path = str(Path(db_path).resolve())
        return True


def recover_interrupted_runs(workspace_dir: Path | None = None) -> int:
    """Mark runs left active by a previous backend process as failed."""
    root = (workspace_dir or WORKSPACE_DIR).resolve()
    if not root.is_dir():
        return 0
    recovered = 0
    for db_path in root.glob("*.db"):
        conn = None
        try:
            if not db_path.resolve().is_relative_to(root):
                continue
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            _migrate_workspace_db(conn)
            from storage import candidates, chats, items, paper_ai_runs
            recovered += candidates.fail_running_jobs(conn)
            recovered += chats.fail_running_turns(conn)
            recovered += items.fail_running_extraction_runs(conn)
            recovered += paper_ai_runs.fail_running_runs(conn)
        except (OSError, sqlite3.DatabaseError, ValueError):
            # Invalid/unavailable files are handled by the workspace import boundary.
            continue
        finally:
            if conn is not None:
                conn.close()
    return recovered


def create_workspace(name: str) -> str:
    """创建新的工作区 DB 文件，返回路径。"""
    _ensure_dir()
    safe_name = name.replace(" ", "_").replace("/", "_")
    db_path = str(WORKSPACE_DIR / f"{safe_name}.db")

    if os.path.isfile(db_path):
        # 文件已存在，加序号
        i = 1
        while os.path.isfile(str(WORKSPACE_DIR / f"{safe_name}_{i}.db")):
            i += 1
        db_path = str(WORKSPACE_DIR / f"{safe_name}_{i}.db")

    _init_workspace_db(db_path)
    return db_path


def delete_workspace_file(db_path: str):
    """删除工作区 DB 文件。"""
    with _workspace_lock:
        if str(Path(db_path).resolve()) == str(Path(get_active_path()).resolve()):
            raise WorkspaceBusyError("不能删除当前正在使用的工作区，请先切换到其他工作区")
        if _workspace_is_busy(db_path):
            raise WorkspaceBusyError("工作区仍有请求正在运行，请等待完成后再删除")
        if _is_workspace_path(db_path) and os.path.isfile(db_path):
            os.remove(db_path)
            from storage.assets import workspace_asset_path
            asset_dir = workspace_asset_path(db_path)
            if asset_dir.is_dir():
                shutil.rmtree(asset_dir)


def clear_workspace():
    """Clear all user content in the active workspace."""
    with _workspace_lock:
        active_path = get_active_path()
        if _workspace_is_busy(active_path):
            raise WorkspaceBusyError("工作区仍有请求正在运行，请等待完成后再清空")
        conn = get_active_connection()
    try:
        conn.execute("DELETE FROM action_project_items")
        conn.execute("DELETE FROM action_projects")
        conn.execute("DELETE FROM item_relations")
        conn.execute("DELETE FROM item_template_data")
        conn.execute("DELETE FROM accepted_extractions")
        conn.execute("DELETE FROM extraction_runs")
        conn.execute("DELETE FROM assets")
        conn.execute("DELETE FROM items")
        conn.execute("DELETE FROM candidates")
        conn.execute("DELETE FROM collection_jobs")
        conn.execute("DELETE FROM chat_sessions")
        conn.execute("DELETE FROM paper_ai_runs")
        conn.execute("DELETE FROM papers")
        conn.execute("DELETE FROM crawl_tasks")
        conn.execute("DELETE FROM workspace_reviews")
        conn.commit()
    finally:
        conn.close()
    from storage.assets import workspace_asset_path
    asset_dir = workspace_asset_path(active_path)
    if asset_dir.is_dir():
        shutil.rmtree(asset_dir)


def _init_workspace_db(db_path: str):
    """初始化工作区 DB 表结构。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS crawl_tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id   INTEGER,
            keywords    TEXT,
            sort_mode   TEXT DEFAULT 'newest',
            paper_count INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS papers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id         INTEGER REFERENCES crawl_tasks(id),
            source_id       INTEGER,
            title           TEXT NOT NULL,
            authors         TEXT,
            abstract        TEXT,
            journal_name    TEXT,
            publish_year    INTEGER,
            arxiv_id        TEXT UNIQUE,
            paper_url       TEXT,
            has_code        INTEGER DEFAULT 0,
            code_url        TEXT,
            auto_keywords   TEXT,
            auto_technologies TEXT,
            ai_innovation   TEXT,
            ai_technologies TEXT,
            ai_code_url     TEXT,
            ai_analyzed     INTEGER DEFAULT 0,
            in_cart         INTEGER DEFAULT 0,
            cart_ai_analyzed INTEGER DEFAULT 0,
            item_id         INTEGER REFERENCES items(id) ON DELETE SET NULL,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS workspace_reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_ids    TEXT,
            ai_review   TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_ws_papers_arxiv   ON papers(arxiv_id);
        CREATE INDEX IF NOT EXISTS idx_ws_papers_cart    ON papers(in_cart);
        CREATE INDEX IF NOT EXISTS idx_ws_papers_year    ON papers(publish_year);
        CREATE INDEX IF NOT EXISTS idx_ws_papers_task    ON papers(task_id);
    """)
    _migrate_workspace_db(conn)
    conn.commit()
    conn.close()


def _is_workspace_path(db_path: str) -> bool:
    """Keep workspace operations inside the application data directory."""
    try:
        return Path(db_path).resolve().is_relative_to(WORKSPACE_DIR.resolve())
    except (OSError, ValueError, TypeError):
        return False


def _migrate_workspace_db(conn: sqlite3.Connection):
    """Apply small idempotent schema upgrades to imported/existing workspaces."""
    from storage.workspace_schema import ensure_material_schema
    from services.paper_materials import ensure_paper_material_mapping

    columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    if "source_id" not in columns:
        conn.execute("ALTER TABLE papers ADD COLUMN source_id INTEGER")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ws_papers_source ON papers(source_id)")
    ensure_material_schema(conn)
    ensure_paper_material_mapping(conn)
    conn.commit()
