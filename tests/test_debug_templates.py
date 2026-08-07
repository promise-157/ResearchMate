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

from api.routes.items import get_similar_items, list_items
from services.debug_templates import (
    confirm_debug_template, extract_debug_template, get_debug_template,
)
from services.materials import import_text_material
from storage.workspace import _init_workspace_db


class DebugTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "debug.db")
        _init_workspace_db(self.db_path)
        self.patches = [
            patch("services.materials.get_active_connection", side_effect=self.connect),
            patch("services.materials._update_workspace_item_count"),
            patch("services.debug_templates.get_active_connection", side_effect=self.connect),
            patch("services.similarity.get_active_connection", side_effect=self.connect),
        ]
        for active in self.patches:
            active.start()

    def tearDown(self):
        for active in reversed(self.patches):
            active.stop()
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def create_debug(self, suffix=""):
        item, _ = import_text_material(
            item_type="debug",
            content_text=(
                f"错误: ModuleNotFoundError requests{suffix}\n"
                "环境: Python 3.12 Ubuntu\n"
                "尝试: 重装 requests\n"
                "根因: 虚拟环境未激活\n"
                "方案: 激活环境后重新安装"
            ),
        )
        return item

    def test_extracted_and_user_confirmed_layers_survive_reprocessing(self):
        item = self.create_debug()
        extracted = get_debug_template(item["id"])
        self.assertEqual(extracted["schema_version"], 1)
        self.assertEqual(extracted["extracted"]["environment"], "Python 3.12 Ubuntu")

        confirmed = confirm_debug_template(item["id"], {
            "root_cause": "用户确认：shell 使用了系统 Python",
        })
        self.assertEqual(confirmed["effective"]["root_cause"], "用户确认：shell 使用了系统 Python")

        rerun = extract_debug_template(item["id"])
        self.assertEqual(rerun["confirmed"]["root_cause"], "用户确认：shell 使用了系统 Python")
        conn = self.connect()
        run = conn.execute(
            "SELECT processor, run_kind, status FROM extraction_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        self.assertEqual(tuple(run), ("debug_label_rules", "template_extract", "succeeded"))

    def test_debug_field_filter_and_explainable_similarity_are_persisted(self):
        first = self.create_debug()
        second = self.create_debug(" in pytest")
        import_text_material(item_type="general", content_text="完全无关的烹饪记录")
        get_debug_template(first["id"])
        get_debug_template(second["id"])

        filtered = list_items(
            q=None, item_type=None, status=None, debug_error="ModuleNotFoundError",
            page=1, page_size=20,
        )
        self.assertEqual(filtered["total"], 2)

        result = get_similar_items(first["id"], threshold=0.1, limit=10)
        self.assertEqual(result["algorithm"], "token-jaccard-v1")
        self.assertEqual(result["matches"][0]["item"]["id"], second["id"])
        self.assertTrue(result["matches"][0]["evidence"]["shared_tokens"])
        conn = self.connect()
        relation = conn.execute(
            "SELECT relation_type, evidence_json FROM item_relations WHERE from_item_id = ?",
            (first["id"],),
        ).fetchone()
        conn.close()
        self.assertEqual(relation["relation_type"], "near_text")
        self.assertIn("token-jaccard-v1", relation["evidence_json"])


if __name__ == "__main__":
    unittest.main()
