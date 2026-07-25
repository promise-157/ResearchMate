"""
工作区管理。每个工作区是独立的 SQLite 文件，存放在 data/workspaces/ 下。
"""
import os
import sqlite3
from pathlib import Path
from typing import Optional

from storage.database import get_connection as get_main_conn

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
    return conn


def switch_workspace(db_path: str) -> bool:
    """切换到指定工作区。"""
    global _active_db_path
    if not os.path.isfile(db_path):
        return False
    _active_db_path = db_path
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
    if os.path.isfile(db_path):
        os.remove(db_path)
    # 如果删的是当前活跃的，回退到默认
    if _active_db_path == db_path:
        _active_db_path = None
        get_active_path()


def clear_workspace():
    """清空当前工作区的所有论文数据。"""
    conn = get_active_connection()
    conn.execute("DELETE FROM papers")
    conn.execute("DELETE FROM crawl_tasks")
    conn.execute("DELETE FROM workspace_reviews")
    conn.commit()
    conn.close()


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
    conn.commit()
    conn.close()
