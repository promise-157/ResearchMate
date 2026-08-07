import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes.items import create_analysis_run
from services.material_analysis import analyze_material, compare_materials, list_material_runs
from services.materials import import_text_material
from storage import items as item_repository
from storage.models import MaterialAnalysisRequest
from storage.workspace import _init_workspace_db
from storage.workspace_schema import ensure_material_schema


class FakeProvider:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def analyze(self, analysis_type, selected_input):
        self.calls.append((analysis_type, selected_input))
        return self.response


class MaterialAnalysisTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "materials.db")
        _init_workspace_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def configured(self, section, key=None):
        values = {"api_type": "fake", "model": "fixture-model", "api_key": "fixture-key"}
        return values.get(key) if section == "ai" else None

    def create_item(self):
        with patch("services.materials.get_active_connection", side_effect=self.connect), \
             patch("services.materials._update_workspace_item_count"):
            item, _ = import_text_material(
                content_text="岗位职责：维护 Python 服务\n工作地点：上海",
                title="后端岗位",
                tags=["待确认"],
            )
        return item

    async def test_success_is_audited_without_overwriting_item(self):
        item = self.create_item()
        fake = FakeProvider(json.dumps({
            "suggested_type": "job", "confidence": 0.9, "reason": "包含岗位职责"
        }))
        with patch("services.material_analysis.get_active_connection", side_effect=self.connect), \
             patch("services.material_analysis.config_get", side_effect=self.configured):
            run, reused = await analyze_material(
                item["id"], analysis_type="classify",
                input_fields=["title", "content_text"], provider_client=fake,
            )
        self.assertFalse(reused)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["input_scope"], ["title", "content_text"])
        self.assertEqual(run["result"]["suggested_type"], "job")
        conn = self.connect()
        stored = conn.execute("SELECT item_type, metadata_json FROM items WHERE id = ?", (item["id"],)).fetchone()
        conn.close()
        self.assertEqual(stored["item_type"], "job")  # deterministic import suggestion, not AI mutation
        self.assertNotIn("fixture-model", stored["metadata_json"])

    async def test_identical_success_is_reused(self):
        item = self.create_item()
        fake = FakeProvider(json.dumps({
            "summary": "Python 后端岗位", "tags": ["Python"], "fields": {"location": "上海"}
        }))
        with patch("services.material_analysis.get_active_connection", side_effect=self.connect), \
             patch("services.material_analysis.config_get", side_effect=self.configured):
            first, reused_first = await analyze_material(
                item["id"], analysis_type="extract", input_fields=["content_text"],
                provider_client=fake,
            )
            second, reused_second = await analyze_material(
                item["id"], analysis_type="extract", input_fields=["content_text"],
                provider_client=fake,
            )
        self.assertFalse(reused_first)
        self.assertTrue(reused_second)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(fake.calls), 1)

    async def test_accepted_extraction_is_sent_only_when_explicitly_selected(self):
        item = self.create_item()
        conn = self.connect()
        run = item_repository.create_extraction_run(conn, {
            "item_id": item["id"], "processor": "fixture-ocr", "processor_version": "1",
            "run_kind": "ocr", "input_hash": "image-hash", "input_scope": ["asset"],
            "provider": "local", "model": "fixture", "prompt_version": "none",
        })
        item_repository.complete_extraction_run(
            conn, run["id"], result={"text": "用户明确接受的 OCR 文本"}
        )
        conn.execute(
            "INSERT INTO accepted_extractions (item_id, extraction_kind, run_id, text_value) "
            "VALUES (?, 'ocr', ?, ?)",
            (item["id"], run["id"], "用户明确接受的 OCR 文本"),
        )
        conn.commit()
        conn.close()
        fake = FakeProvider(json.dumps({
            "summary": "fixture", "tags": [], "fields": {}
        }))
        with patch("services.material_analysis.get_active_connection", side_effect=self.connect), \
             patch("services.material_analysis.config_get", side_effect=self.configured):
            audited, _ = await analyze_material(
                item["id"], analysis_type="extract",
                input_fields=["title", "accepted_extraction"], provider_client=fake,
            )
        sent = fake.calls[0][1]
        self.assertEqual(sent["accepted_extraction"], "用户明确接受的 OCR 文本")
        self.assertNotIn("content_text", sent)
        self.assertEqual(audited["input_scope"], ["title", "accepted_extraction"])

    async def test_invalid_model_output_records_failure(self):
        item = self.create_item()
        fake = FakeProvider('{"suggested_type":"job","confidence":4}')
        with patch("services.material_analysis.get_active_connection", side_effect=self.connect), \
             patch("services.material_analysis.config_get", side_effect=self.configured):
            with self.assertRaisesRegex(RuntimeError, "结构校验"):
                await analyze_material(
                    item["id"], analysis_type="classify", input_fields=["title"],
                    provider_client=fake,
                )
            runs = list_material_runs(item["id"])
        self.assertEqual(runs[0]["status"], "failed")
        self.assertIsNone(runs[0]["result"])
        self.assertIn("结构校验", runs[0]["error_message"])

    async def test_missing_configuration_is_actionable_and_calls_no_provider(self):
        item = self.create_item()
        fake = FakeProvider("{}")
        def unconfigured(section, key=None):
            return {"api_type": "openai", "model": "gpt", "api_key": ""}.get(key)
        with patch("services.material_analysis.config_get", side_effect=unconfigured):
            with self.assertRaisesRegex(ValueError, "设置页"):
                await analyze_material(
                    item["id"], analysis_type="classify", input_fields=["title"],
                    provider_client=fake,
                )
        self.assertEqual(fake.calls, [])

    async def test_api_returns_reuse_flag(self):
        body = MaterialAnalysisRequest(
            analysis_type="classify", input_fields=["title"]
        )
        expected = {"id": 8, "status": "succeeded"}
        with patch(
            "api.routes.items.analyze_material",
            new=AsyncMock(return_value=(expected, True)),
        ):
            response = await create_analysis_run(3, body)
        self.assertEqual(response, {"run": expected, "reused": True})

    async def test_compare_two_to_twenty_items_with_bounded_text(self):
        first = self.create_item()
        with patch("services.materials.get_active_connection", side_effect=self.connect), \
             patch("services.materials._update_workspace_item_count"):
            second, _ = import_text_material(content_text="另一个岗位：Go 服务", title="Go 岗位")
        fake = FakeProvider(json.dumps({
            "summary": "两个后端岗位", "common_themes": ["服务开发"],
            "differences": ["语言不同"], "item_insights": {str(first["id"]): "Python"},
        }))
        with patch("services.material_analysis.get_active_connection", side_effect=self.connect), \
             patch("services.material_analysis.config_get", side_effect=self.configured):
            run, reused = await compare_materials(
                [first["id"], second["id"]], input_fields=["title", "content_text"],
                provider_client=fake,
            )
        self.assertFalse(reused)
        self.assertEqual(run["input_item_ids"], [first["id"], second["id"]])
        self.assertEqual(run["result"]["differences"], ["语言不同"])
        self.assertEqual(len(fake.calls), 1)

    def test_v1_run_table_migrates_idempotently_without_losing_history(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE items (id INTEGER PRIMARY KEY, item_type TEXT, "
            "status TEXT, created_at TEXT)"
        )
        conn.execute(
            """CREATE TABLE extraction_runs (
                id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL,
                processor TEXT NOT NULL, processor_version TEXT NOT NULL,
                run_kind TEXT NOT NULL, status TEXT NOT NULL, input_hash TEXT NOT NULL,
                result_json TEXT, error_message TEXT, provider TEXT, model TEXT,
                prompt_version TEXT, created_at TEXT
            )"""
        )
        conn.execute(
            "INSERT INTO extraction_runs VALUES "
            "(1, 7, 'old', '1', 'classify', 'succeeded', 'hash', '{}', NULL, "
            "'fake', 'old-model', 'v1', '2026-01-01')"
        )
        ensure_material_schema(conn)
        ensure_material_schema(conn)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(extraction_runs)")}
        row = conn.execute(
            "SELECT processor, input_scope_json FROM extraction_runs WHERE id = 1"
        ).fetchone()
        conn.close()
        self.assertIn("input_scope_json", columns)
        self.assertIn("input_item_ids_json", columns)
        self.assertEqual(row, ("old", "[]"))


if __name__ == "__main__":
    unittest.main()
