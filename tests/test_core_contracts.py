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

    def test_config_mode_persists_key_and_session_mode_removes_it(self):
        previous_config = config.config
        previous_key = config._persisted_api_key
        previous_source = config._api_key_source
        try:
            config.config = {
                "ai": {"api_key": "", "key_storage_mode": "session"},
                "crawler": {},
            }
            config._persisted_api_key = ""
            with patch("config.save_config") as save:
                config.update_ai_config(
                    api_key="fixture-secret", key_storage_mode="config"
                )
                persisted = config._persistable_config(config.config)
                self.assertEqual(persisted["ai"]["api_key"], "fixture-secret")
                self.assertEqual(config.get_ai_key_source(), "config")

                config.update_ai_config(key_storage_mode="session")
                safe = config._persistable_config(config.config)
                self.assertNotIn("api_key", safe["ai"])
                self.assertEqual(config.get("ai", "api_key"), "fixture-secret")
                self.assertEqual(config.get_ai_key_source(), "session")
                self.assertEqual(save.call_count, 2)
        finally:
            config.config = previous_config
            config._persisted_api_key = previous_key
            config._api_key_source = previous_source

    def test_config_file_is_owner_only_and_plaintext_is_opt_in(self):
        previous_dir = config.BACKEND_DIR
        previous_config = config.config
        previous_key = config._persisted_api_key
        previous_source = config._api_key_source
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.BACKEND_DIR = Path(tmp)
                config.config = {
                    "ai": {"api_key": "", "key_storage_mode": "session"},
                    "crawler": {},
                }
                config._persisted_api_key = ""
                config.update_ai_config(
                    api_key="fixture-secret", key_storage_mode="config"
                )
                config_path = Path(tmp) / "config.yaml"
                self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)
                self.assertIn("fixture-secret", config_path.read_text())

                config.update_ai_config(key_storage_mode="session")
                self.assertNotIn("fixture-secret", config_path.read_text())
                self.assertNotIn("api_key:", config_path.read_text())
        finally:
            config.BACKEND_DIR = previous_dir
            config.config = previous_config
            config._persisted_api_key = previous_key
            config._api_key_source = previous_source

    def test_failed_save_rolls_back_runtime_and_persisted_key(self):
        previous_config = config.config
        previous_key = config._persisted_api_key
        previous_source = config._api_key_source
        try:
            config.config = {
                "ai": {"api_key": "old", "key_storage_mode": "session"},
                "crawler": {},
            }
            config._persisted_api_key = ""
            config._api_key_source = "session"
            with patch("config.save_config", side_effect=config.ConfigSaveError("失败")):
                with self.assertRaises(config.ConfigSaveError):
                    config.update_ai_config(
                        api_key="fixture-new", key_storage_mode="config"
                    )
            self.assertEqual(config.get("ai", "api_key"), "old")
            self.assertEqual(config.get("ai", "key_storage_mode"), "session")
            self.assertEqual(config._persisted_api_key, "")
            self.assertEqual(config.get_ai_key_source(), "session")
        finally:
            config.config = previous_config
            config._persisted_api_key = previous_key
            config._api_key_source = previous_source


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


if __name__ == "__main__":
    unittest.main()
