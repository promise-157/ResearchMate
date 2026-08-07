import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes.items import accept_item_extraction
from services.accepted_extractions import accept_extraction
from services.image_materials import import_image_material, run_local_ocr
from storage import items as item_repository
from storage.workspace import _init_workspace_db
from storage.workspace_schema import ensure_material_schema


class FakeOCR:
    def extract(self, image_path):
        return "刷新后仍可检索的 OCR fixture 文本"


class AcceptedExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = str(self.root / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patches = [
            patch("services.image_materials.get_active_connection", side_effect=self.connect),
            patch("services.image_materials.get_active_path", return_value=self.db_path),
            patch("services.image_materials._update_workspace_item_count"),
            patch("services.accepted_extractions.get_active_connection", side_effect=self.connect),
            patch("storage.assets.DATA_DIR", self.root),
            patch("storage.assets.ASSET_ROOT", self.root / "assets"),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def create_ocr_run(self):
        item, _ = import_image_material(
            filename="fixture.png", data=b"\x89PNG\r\n\x1a\naccepted-fixture"
        )
        return item, run_local_ocr(item["id"], processor=FakeOCR())

    def test_preview_run_is_explicitly_accepted_without_overwriting_source(self):
        item, run = self.create_ocr_run()
        response = accept_item_extraction(item["id"], run["id"])
        accepted = response["accepted_extraction"]
        self.assertEqual(accepted["run_id"], run["id"])
        self.assertEqual(accepted["text_value"], "刷新后仍可检索的 OCR fixture 文本")

        repeated = accept_extraction(item["id"], run["id"])
        self.assertEqual(repeated["run_id"], run["id"])
        conn = self.connect()
        stored = item_repository.get_item(conn, item["id"])
        count = conn.execute("SELECT COUNT(*) FROM accepted_extractions").fetchone()[0]
        conn.close()
        self.assertEqual(stored["content_text"], "")
        self.assertEqual(count, 1)

    def test_search_only_expands_when_accepted_scope_is_explicit(self):
        item, run = self.create_ocr_run()
        accept_extraction(item["id"], run["id"])
        conn = self.connect()
        original_only = item_repository.list_items(conn, query="OCR fixture")
        expanded = item_repository.list_items(
            conn, query="OCR fixture", include_accepted_extractions=True
        )
        conn.close()
        self.assertEqual(original_only["total"], 0)
        self.assertEqual(expanded["total"], 1)
        self.assertEqual(expanded["items"][0]["id"], item["id"])
        self.assertTrue(expanded["items"][0]["has_accepted_extraction"])

    def test_rejects_cross_item_and_non_deterministic_runs(self):
        item, run = self.create_ocr_run()
        other, _ = import_image_material(
            filename="other.jpg", data=b"\xff\xd8\xffother-accepted-fixture"
        )
        with self.assertRaisesRegex(ValueError, "不属于"):
            accept_extraction(other["id"], run["id"])

        conn = self.connect()
        ai_run = item_repository.create_extraction_run(conn, {
            "item_id": item["id"], "processor": "fixture-ai", "processor_version": "1",
            "run_kind": "extract", "input_hash": "fixture", "input_scope": ["title"],
            "provider": "local", "model": "fixture", "prompt_version": "v1",
        })
        item_repository.complete_extraction_run(conn, ai_run["id"], result={"text": "unsafe"})
        conn.close()
        with self.assertRaisesRegex(ValueError, "确定性"):
            accept_extraction(item["id"], ai_run["id"])

    def test_reaccept_replaces_current_version_and_migration_preserves_it(self):
        item, first_run = self.create_ocr_run()
        accept_extraction(item["id"], first_run["id"])
        conn = self.connect()
        second_run = item_repository.create_extraction_run(conn, {
            "item_id": item["id"], "processor": "local_tesseract",
            "processor_version": "2", "run_kind": "ocr", "input_hash": "new-fixture",
            "input_scope": ["asset"], "provider": "local", "model": "tesseract",
            "prompt_version": "none",
        })
        item_repository.complete_extraction_run(
            conn, second_run["id"], result={"text": "第二版 OCR 文本"}
        )
        conn.close()
        accepted = accept_extraction(item["id"], second_run["id"])
        self.assertEqual(accepted["text_value"], "第二版 OCR 文本")

        conn = self.connect()
        ensure_material_schema(conn)
        ensure_material_schema(conn)
        current = conn.execute(
            "SELECT run_id, text_value FROM accepted_extractions WHERE item_id = ?",
            (item["id"],),
        ).fetchone()
        history_count = conn.execute(
            "SELECT COUNT(*) FROM extraction_runs WHERE item_id = ? AND run_kind = 'ocr'",
            (item["id"],),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(tuple(current), (second_run["id"], "第二版 OCR 文本"))
        self.assertEqual(history_count, 2)


if __name__ == "__main__":
    unittest.main()
