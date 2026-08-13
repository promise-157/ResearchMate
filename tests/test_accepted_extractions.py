import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


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


class TextOCR:
    def __init__(self, text):
        self.text = text

    def extract(self, image_path):
        return self.text


class FailingOCR:
    def extract(self, image_path):
        raise RuntimeError("重新处理 fixture 失败")


def complete_image(format_name="PNG", *, color="white"):
    output = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(output, format=format_name)
    return output.getvalue()


class AcceptedExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = str(self.root / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patches = [
            patch("services.image_materials.get_active_connection", side_effect=self.connect),
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
            filename="fixture.png", data=complete_image("PNG")
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
            filename="other.jpg", data=complete_image("JPEG", color="blue")
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

    def test_reprocessing_preserves_source_history_and_acceptance_until_reaccepted(self):
        item, first_run = self.create_ocr_run()
        accepted = accept_extraction(item["id"], first_run["id"])
        conn = self.connect()
        source_before = tuple(conn.execute(
            "SELECT source_kind, content_text, content_hash FROM items WHERE id = ?",
            (item["id"],),
        ).fetchone())
        asset_before = tuple(conn.execute(
            "SELECT original_name, storage_path, content_hash, size_bytes FROM assets WHERE item_id = ?",
            (item["id"],),
        ).fetchone())
        conn.close()

        second_run = run_local_ocr(item["id"], processor=TextOCR("尚未接受的第二版"))
        with self.assertRaisesRegex(RuntimeError, "重新处理 fixture 失败"):
            run_local_ocr(item["id"], processor=FailingOCR())

        conn = self.connect()
        source_after = tuple(conn.execute(
            "SELECT source_kind, content_text, content_hash FROM items WHERE id = ?",
            (item["id"],),
        ).fetchone())
        asset_after = tuple(conn.execute(
            "SELECT original_name, storage_path, content_hash, size_bytes FROM assets WHERE item_id = ?",
            (item["id"],),
        ).fetchone())
        current = conn.execute(
            "SELECT run_id, text_value FROM accepted_extractions WHERE item_id = ?",
            (item["id"],),
        ).fetchone()
        runs = conn.execute(
            "SELECT id, status FROM extraction_runs WHERE item_id = ? ORDER BY id",
            (item["id"],),
        ).fetchall()
        conn.close()

        self.assertEqual(source_after, source_before)
        self.assertEqual(asset_after, asset_before)
        self.assertEqual(tuple(current), (accepted["run_id"], accepted["text_value"]))
        self.assertEqual(
            [(run["id"], run["status"]) for run in runs],
            [(first_run["id"], "succeeded"), (second_run["id"], "succeeded"), (runs[2]["id"], "failed")],
        )

        updated = accept_extraction(item["id"], second_run["id"])
        self.assertEqual((updated["run_id"], updated["text_value"]), (second_run["id"], "尚未接受的第二版"))

    def test_reprocessing_is_isolated_to_the_connection_workspace(self):
        first_item, first_run = self.create_ocr_run()
        first_accepted = accept_extraction(first_item["id"], first_run["id"])
        first_db = self.db_path

        second_db = str(self.root / "second.db")
        _init_workspace_db(second_db)
        self.db_path = second_db
        second_item, _ = import_image_material(
            filename="second.png", data=complete_image("PNG", color="blue")
        )
        self.assertEqual(second_item["id"], first_item["id"])
        second_run = run_local_ocr(second_item["id"], processor=TextOCR("second workspace"))

        second_conn = self.connect()
        second_runs = second_conn.execute(
            "SELECT id, result_json FROM extraction_runs ORDER BY id"
        ).fetchall()
        second_accepted_count = second_conn.execute(
            "SELECT COUNT(*) FROM accepted_extractions"
        ).fetchone()[0]
        second_conn.close()

        self.db_path = first_db
        first_conn = self.connect()
        first_runs = first_conn.execute(
            "SELECT id, result_json FROM extraction_runs ORDER BY id"
        ).fetchall()
        first_current = first_conn.execute(
            "SELECT run_id, text_value FROM accepted_extractions WHERE item_id = ?",
            (first_item["id"],),
        ).fetchone()
        first_conn.close()

        self.assertEqual(len(first_runs), 1)
        self.assertIn("刷新后仍可检索", first_runs[0]["result_json"])
        self.assertEqual(tuple(first_current), (first_accepted["run_id"], first_accepted["text_value"]))
        self.assertEqual(len(second_runs), 1)
        self.assertEqual(second_runs[0]["id"], second_run["id"])
        self.assertIn("second workspace", second_runs[0]["result_json"])
        self.assertEqual(second_accepted_count, 0)


if __name__ == "__main__":
    unittest.main()
