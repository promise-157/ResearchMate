"""
SQLite 数据库管理。连接、初始化表结构。
"""
import sqlite3
import os
from config import get_db_path


def get_connection() -> sqlite3.Connection:
    """获取数据库连接。"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构（幂等，重复执行安全）。"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            db_path     TEXT NOT NULL,
            paper_count INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            opened_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS journal_sources (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT NOT NULL,
            label           TEXT,
            last_crawled_at TEXT,
            last_paper_count INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS papers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id       INTEGER REFERENCES journal_sources(id) ON DELETE SET NULL,
            title           TEXT NOT NULL,
            authors         TEXT,           -- JSON 数组
            abstract        TEXT,
            journal_name    TEXT,
            publish_year    INTEGER,
            arxiv_id        TEXT UNIQUE,
            paper_url       TEXT,
            has_code        INTEGER DEFAULT 0,
            code_url        TEXT,
            ai_innovation   TEXT,
            ai_technologies TEXT,           -- JSON 数组
            ai_analyzed     INTEGER DEFAULT 0,
            in_cart         INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS crawl_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sources         TEXT,           -- JSON 数组
            paper_count     INTEGER DEFAULT 0,
            ai_review       TEXT,           -- AI 批量点评全文
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_papers_source    ON papers(source_id);
        CREATE INDEX IF NOT EXISTS idx_papers_arxiv     ON papers(arxiv_id);
        CREATE INDEX IF NOT EXISTS idx_papers_in_cart   ON papers(in_cart);
        CREATE INDEX IF NOT EXISTS idx_papers_year      ON papers(publish_year);
    """)

    conn.commit()
    conn.close()


def dict_from_row(row):
    """将 sqlite3.Row 转为普通字典。"""
    if row is None:
        return None
    return dict(row)
