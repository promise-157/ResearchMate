"""
工作区管理。每个工作区是独立的 SQLite 文件，存放在 data/workspaces/ 下。
"""
import os
import sqlite3
import shutil
from pathlib import Path
from typing import Optional


# 工作区目录
WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "workspaces"

# 当前活跃的工作区（内存中）
_active_db_path: Optional[str] = None


def _ensure_dir():
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def get_active_path() -> str:
    """获取当前活跃工作区的数据库路径。"""
    global _active_db_path
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
    """获取当前活跃工作区的数据库连接。"""
    db_path = get_active_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate_workspace_db(conn)
    return conn


def switch_workspace(db_path: str) -> bool:
    """切换到指定工作区。"""
    global _active_db_path
    if not _is_workspace_path(db_path) or not os.path.isfile(db_path):
        return False
    _active_db_path = str(Path(db_path).resolve())
    return True


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
    global _active_db_path
    if _is_workspace_path(db_path) and os.path.isfile(db_path):
        os.remove(db_path)
        from storage.assets import workspace_asset_path
        asset_dir = workspace_asset_path(db_path)
        if asset_dir.is_dir():
            shutil.rmtree(asset_dir)
    # 如果删的是当前活跃的，回退到默认
    if _active_db_path == db_path:
        _active_db_path = None
        get_active_path()


def clear_workspace():
    """Clear all user content in the active workspace."""
    conn = get_active_connection()
    conn.execute("DELETE FROM item_relations")
    conn.execute("DELETE FROM item_template_data")
    conn.execute("DELETE FROM accepted_extractions")
    conn.execute("DELETE FROM extraction_runs")
    conn.execute("DELETE FROM assets")
    conn.execute("DELETE FROM items")
    conn.execute("DELETE FROM candidates")
    conn.execute("DELETE FROM collection_jobs")
    conn.execute("DELETE FROM papers")
    conn.execute("DELETE FROM crawl_tasks")
    conn.execute("DELETE FROM workspace_reviews")
    conn.commit()
    conn.close()
    from storage.assets import workspace_asset_path
    asset_dir = workspace_asset_path(get_active_path())
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
