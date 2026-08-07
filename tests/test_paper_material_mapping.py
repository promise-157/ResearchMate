import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes.crawl import _insert_paper
from api.routes.papers import list_papers
from services.materials import normalize_text
from services.paper_materials import ensure_paper_material_mapping, map_paper_to_material
from storage import items as item_repository
from storage.workspace import _init_workspace_db, _migrate_workspace_db


class PaperMaterialMappingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "workspace.db")
        _init_workspace_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def insert_legacy_paper(self, conn, *, title="Fixture 论文", abstract="离线摘要内容"):
        cursor = conn.execute(
            """INSERT INTO papers
               (title, authors, abstract, journal_name, publish_year, arxiv_id,
                paper_url, has_code, code_url, auto_keywords)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title, json.dumps(["Alice"]), abstract, "cs.AI", 2026,
                f"fixture.{conn.execute('SELECT COUNT(*) FROM papers').fetchone()[0] + 1}",
                "https://arxiv.org/abs/fixture", 1, "https://example.com/code",
                json.dumps(["fixture"]),
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def test_existing_paper_migrates_once_and_is_visible_as_generic_item(self):
        conn = self.connect()
        paper_id = self.insert_legacy_paper(conn)
        mapped_first = ensure_paper_material_mapping(conn)
        mapped_second = ensure_paper_material_mapping(conn)
        paper = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        item = item_repository.get_item(conn, paper["item_id"])
        self.assertEqual(mapped_first, 1)
        self.assertEqual(mapped_second, 0)
        self.assertEqual(item["item_type"], "paper")
        self.assertEqual(item["source_kind"], "paper_adapter")
        self.assertEqual(item["metadata"]["paper_mapping"]["paper_id"], paper_id)
        listed = item_repository.list_items(conn, item_type="paper")
        self.assertEqual([entry["id"] for entry in listed["items"]], [item["id"]])
        conn.close()

    def test_matching_user_item_is_reused_without_overwrite(self):
        conn = self.connect()
        abstract = "相同的规范化正文"
        normalized = normalize_text(abstract)
        existing = item_repository.create_item(conn, {
            "item_type": "general", "title": "用户标题", "content_text": normalized,
            "summary": "用户摘要", "source_kind": "text_import", "source_url": None,
            "status": "archived", "tags": ["用户标签"], "metadata": {"user": True},
            "content_hash": hashlib.sha256(normalized.encode()).hexdigest(),
        })
        paper_id = self.insert_legacy_paper(conn, title="来源标题", abstract=abstract)
        ensure_paper_material_mapping(conn)
        paper = conn.execute("SELECT item_id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        preserved = item_repository.get_item(conn, existing["id"])
        self.assertEqual(paper["item_id"], existing["id"])
        self.assertEqual(preserved["title"], "用户标题")
        self.assertEqual(preserved["item_type"], "general")
        self.assertEqual(preserved["status"], "archived")
        self.assertEqual(preserved["metadata"], {"user": True})
        conn.close()

    def test_new_crawl_insert_can_map_in_same_transaction(self):
        conn = self.connect()
        paper_id = _insert_paper(conn, {
            "title": "新论文", "authors": "[]", "abstract": "Abstract: offline",
            "journal_name": "cs.LG", "publish_year": 2026, "arxiv_id": "fixture.new",
            "paper_url": "https://arxiv.org/abs/fixture.new", "has_code": False,
            "code_url": None, "auto_keywords": "[]", "auto_technologies": "[]",
        }, source_id=2, task_id=None)
        item = map_paper_to_material(conn, paper_id)
        conn.commit()
        linked = conn.execute("SELECT item_id FROM papers WHERE id = ?", (paper_id,)).fetchone()
        self.assertEqual(linked["item_id"], item["id"])
        self.assertEqual(item["item_type"], "paper")
        _migrate_workspace_db(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)
        conn.close()

    def test_paper_api_preserves_specialized_view_and_exposes_item_link(self):
        conn = self.connect()
        paper_id = self.insert_legacy_paper(conn)
        ensure_paper_material_mapping(conn)
        conn.close()
        with patch("api.routes.papers.get_connection", side_effect=self.connect):
            result = list_papers(
                q=None, has_code=None, in_cart=None, source_id=None, keywords=None,
                kw_mode="or", sort="newest", page=1, page_size=20,
            )
        self.assertEqual(result["items"][0]["id"], paper_id)
        self.assertIsNotNone(result["items"][0]["item_id"])


if __name__ == "__main__":
    unittest.main()
