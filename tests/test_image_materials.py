import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from services.image_materials import get_asset_file, import_image_material, run_local_ocr
from storage.workspace import _init_workspace_db


class FakeOCR:
    def extract(self, image_path):
        self.image_path = image_path
        return "本地识别文字"


class FailingOCR:
    def extract(self, image_path):
        raise RuntimeError("fixture OCR failure")


class ImageMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = str(self.root / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patches = [
            patch("services.image_materials.get_active_connection", side_effect=self.connect),
            patch("services.image_materials.get_active_path", return_value=self.db_path),
            patch("services.image_materials._update_workspace_item_count"),
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

    def test_image_is_saved_deduplicated_and_served_from_guarded_path(self):
        image = b"\x89PNG\r\n\x1a\nfixture"
        item, created = import_image_material(filename="screen.png", data=image)
        duplicate, created_again = import_image_material(filename="copy.png", data=image)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(item["id"], duplicate["id"])
        asset, path = get_asset_file(item["assets"][0]["id"])
        self.assertEqual(asset["mime_type"], "image/png")
        self.assertEqual(path.read_bytes(), image)
        self.assertTrue(path.is_relative_to(self.root / "assets"))

    def test_local_ocr_success_and_failure_are_audited(self):
        item, _ = import_image_material(
            filename="screen.png", data=b"\x89PNG\r\n\x1a\nfixture-2"
        )
        run = run_local_ocr(item["id"], processor=FakeOCR())
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["result"]["text"], "本地识别文字")

        other, _ = import_image_material(
            filename="other.jpg", data=b"\xff\xd8\xfffixture"
        )
        with self.assertRaisesRegex(RuntimeError, "fixture OCR failure"):
            run_local_ocr(other["id"], processor=FailingOCR())
        conn = self.connect()
        failed = conn.execute(
            "SELECT status, error_message FROM extraction_runs WHERE item_id = ?",
            (other["id"],),
        ).fetchone()
        conn.close()
        self.assertEqual(failed["status"], "failed")
        self.assertIn("fixture OCR failure", failed["error_message"])

    def test_rejects_non_image_bytes(self):
        with self.assertRaisesRegex(ValueError, "PNG"):
            import_image_material(filename="fake.png", data=b"not an image")


if __name__ == "__main__":
    unittest.main()
