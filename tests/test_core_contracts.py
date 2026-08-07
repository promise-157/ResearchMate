import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

import config
from api.routes.chat import ChatRequest, _build_prompt
from api.routes.crawl import _insert_paper, _update_paper
from crawlers.arxiv_crawler import ArxivCrawler
from crawlers.policy import validate_source_url
from storage.workspace import _init_workspace_db, _is_workspace_path, WORKSPACE_DIR


class SourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.previous = config.config["crawler"]["enable_generic_fetch"]
        config.config["crawler"]["enable_generic_fetch"] = False

    def tearDown(self):
        config.config["crawler"]["enable_generic_fetch"] = self.previous

    def test_arxiv_is_allowlisted(self):
        self.assertTrue(validate_source_url("https://arxiv.org/list/cs.AI/recent")[0])

    def test_arbitrary_and_credential_urls_are_rejected(self):
        self.assertFalse(validate_source_url("https://example.com/papers")[0])
        self.assertFalse(validate_source_url("https://user:pass@arxiv.org/list/cs.AI")[0])
        self.assertFalse(validate_source_url("https://arxiv.org/search/?query=ai")[0])

    def test_arxiv_adapter_does_not_match_lookalike_host(self):
        crawler = ArxivCrawler()
        self.assertFalse(crawler.can_handle("https://arxiv.org.evil.example/list/cs.AI"))
        self.assertFalse(crawler.can_handle("https://evil-arxiv.org/list/cs.AI"))

    def test_generic_opt_in_still_blocks_local_networks(self):
        config.config["crawler"]["enable_generic_fetch"] = True
        self.assertFalse(validate_source_url("http://127.0.0.1:8000/api/settings")[0])
        self.assertFalse(validate_source_url("http://localhost/admin")[0])
        self.assertTrue(validate_source_url("https://example.com/papers")[0])


class SecretConfigTests(unittest.TestCase):
    def test_persisted_snapshot_excludes_key_without_mutating_runtime(self):
        runtime = {"ai": {"api_key": "secret", "model": "test"}, "crawler": {}}
        persisted = config._persistable_config(runtime)
        self.assertNotIn("api_key", persisted["ai"])
        self.assertEqual(runtime["ai"]["api_key"], "secret")


class WorkspaceSchemaTests(unittest.TestCase):
    def test_new_workspace_records_source_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "workspace.db")
            _init_workspace_db(db_path)
            conn = sqlite3.connect(db_path)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
            conn.close()
            self.assertIn("source_id", columns)

    def test_workspace_paths_cannot_escape_data_directory(self):
        self.assertTrue(_is_workspace_path(str(WORKSPACE_DIR / "safe.db")))
        self.assertFalse(_is_workspace_path(str(WORKSPACE_DIR / ".." / "outside.db")))

    def test_sync_records_source_and_preserves_positive_code_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "workspace.db")
            _init_workspace_db(db_path)
            conn = sqlite3.connect(db_path)
            task_id = conn.execute(
                "INSERT INTO crawl_tasks (source_id) VALUES (7)"
            ).lastrowid
            paper = {
                "title": "Paper", "authors": "[]", "abstract": "transformer",
                "journal_name": "arXiv", "publish_year": 2026, "arxiv_id": "2601.1",
                "paper_url": "https://arxiv.org/abs/2601.1", "has_code": True,
                "code_url": "https://github.com/example/repo",
                "auto_keywords": "[]", "auto_technologies": "[]",
            }
            _insert_paper(conn, paper, source_id=7, task_id=task_id)
            _update_paper(
                conn,
                {**paper, "has_code": False, "code_url": None},
                source_id=8,
                task_id=task_id,
            )
            row = conn.execute(
                "SELECT source_id, task_id, has_code, code_url FROM papers"
            ).fetchone()
            conn.close()
            self.assertEqual(row, (8, task_id, 1, "https://github.com/example/repo"))


class ChatScopeTests(unittest.TestCase):
    def test_no_attachment_means_no_implicit_workspace_context(self):
        request = ChatRequest(message="summarize")
        self.assertEqual(_build_prompt(request), "summarize")

    def test_only_explicit_ids_are_loaded(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE papers (id INTEGER, title TEXT, authors TEXT, abstract TEXT, "
            "journal_name TEXT, publish_year INTEGER, paper_url TEXT)"
        )
        conn.executemany(
            "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "Selected", "[]", "selected abstract", "arXiv", 2026, "https://arxiv.org/abs/1"),
                (2, "Not selected", "[]", "private abstract", "arXiv", 2026, "https://arxiv.org/abs/2"),
            ],
        )
        with patch("api.routes.chat.get_active_connection", return_value=conn):
            prompt = _build_prompt(ChatRequest(message="compare", paper_ids=[1]))
        self.assertIn("Selected", prompt)
        self.assertNotIn("Not selected", prompt)
        self.assertNotIn("private abstract", prompt)


if __name__ == "__main__":
    unittest.main()
