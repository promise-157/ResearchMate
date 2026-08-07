import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Response
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from services.materials import classify_text, import_text_material, normalize_text
from api.routes.items import create_item, list_items, update_item
from storage import items as item_repository
from storage.models import MaterialCreate, MaterialUpdate
from storage.workspace import _init_workspace_db


class MaterialServiceTests(unittest.TestCase):
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

    def test_normalization_is_stable(self):
        self.assertEqual(normalize_text("  A\t B\r\n\r\n\r\n C  "), "A B\n\nC")

    def test_rule_classifier_suggests_domain_without_ai(self):
        result = classify_text("岗位职责：开发系统\n任职要求：熟悉 Python\n工作地点：上海")
        self.assertEqual(result.item_type, "job")
        self.assertIn("岗位职责", result.signals)

    def test_import_is_deduplicated_by_normalized_content(self):
        with patch("services.materials.get_active_connection", side_effect=self.connect), \
             patch("services.materials._update_workspace_item_count"):
            first, created = import_text_material(
                content_text="Traceback\nError: failed", tags=[" python ", "python"]
            )
            duplicate, created_again = import_text_material(
                content_text="  Traceback\r\nError:   failed  "
            )
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["id"], duplicate["id"])
        self.assertEqual(first["item_type"], "debug")
        self.assertEqual(first["tags"], ["python"])

    def test_search_treats_like_wildcards_as_text(self):
        with patch("services.materials.get_active_connection", side_effect=self.connect), \
             patch("services.materials._update_workspace_item_count"):
            import_text_material(content_text="100% reproducible_error")
            import_text_material(content_text="ordinary text")
        conn = self.connect()
        result = item_repository.list_items(conn, query="% reproducible_", page_size=20)
        conn.close()
        self.assertEqual(result["total"], 1)

    def test_status_update_is_persisted(self):
        with patch("services.materials.get_active_connection", side_effect=self.connect), \
             patch("services.materials._update_workspace_item_count"):
            item, _ = import_text_material(content_text="a useful note")
        conn = self.connect()
        updated = item_repository.update_item(conn, item["id"], status="active")
        conn.close()
        self.assertEqual(updated["status"], "active")

    def test_api_vertical_slice_and_url_validation(self):
        with patch("services.materials.get_active_connection", side_effect=self.connect), \
             patch("services.materials._update_workspace_item_count"):
            response = Response()
            created = create_item(MaterialCreate(
                content_text="岗位职责：开发资料系统\n工作地点：上海",
                item_type="auto",
                tags=["求职"],
            ), response)
            self.assertEqual(response.status_code, 201)
            item = created["item"]
            self.assertEqual(item["item_type"], "job")

            listed = list_items(
                q=None, item_type="job", status=None, page=1, page_size=20
            )
            self.assertEqual(listed["total"], 1)

            updated = update_item(item["id"], MaterialUpdate(status="active"))
            self.assertEqual(updated["status"], "active")

            with self.assertRaises(ValidationError):
                MaterialCreate(
                    content_text="unsafe link", source_url="javascript:alert(1)"
                )


if __name__ == "__main__":
    unittest.main()
