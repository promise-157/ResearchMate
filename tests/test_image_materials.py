import asyncio
import io
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont
from fastapi import HTTPException, UploadFile


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from processors.image_decoder import (
    MAX_IMAGE_HEIGHT,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_WIDTH,
    decode_image,
)
from api.routes.items import create_ocr_run, import_image as import_image_route
from processors.local_ocr import LocalOCRProcessor
from services.image_materials import (
    MAX_IMAGE_BYTES,
    get_asset_file,
    import_image_material,
    run_local_ocr,
)
from storage import assets as asset_repository
from storage.workspace import _init_workspace_db


def complete_image(format_name="PNG", *, size=(96, 48), color="white"):
    """Build complete, offline PNG/JPEG/WebP fixture bytes."""
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format=format_name, quality=95)
    return output.getvalue()


class FakeOCR:
    def extract(self, image_path):
        self.image_path = image_path
        with Image.open(image_path) as image:
            image.load()
            self.decoded_format = image.format
        return "本地识别文字"


class FailingOCR:
    def extract(self, image_path):
        raise RuntimeError("fixture OCR failure")


class TextOCR:
    def __init__(self, text):
        self.text = text

    def extract(self, image_path):
        return self.text


class ImageMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = str(self.root / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patches = [
            patch("services.image_materials.get_active_connection", side_effect=self.connect),
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

    def database_counts(self):
        conn = self.connect()
        counts = tuple(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("items", "assets", "extraction_runs", "accepted_extractions")
        )
        conn.close()
        return counts

    def asset_files(self):
        root = self.root / "assets"
        return list(root.rglob("*")) if root.exists() else []

    def test_complete_png_jpeg_and_webp_import_preview_and_ocr(self):
        expected_mimes = {
            "PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp",
        }
        for index, format_name in enumerate(expected_mimes):
            with self.subTest(format=format_name):
                data = complete_image(format_name, color=(index * 40, 80, 120))
                item, created = import_image_material(
                    filename=f"fixture-{format_name.lower()}.bin", data=data
                )
                self.assertTrue(created)
                asset, path = get_asset_file(item["assets"][0]["id"])
                self.assertEqual(asset["mime_type"], expected_mimes[format_name])
                self.assertEqual((asset["image_width"], asset["image_height"]), (96, 48))
                self.assertEqual(path.read_bytes(), data)
                self.assertTrue(path.is_relative_to(self.root / "assets"))

                processor = FakeOCR()
                run = run_local_ocr(item["id"], processor=processor)
                self.assertEqual(run["status"], "succeeded")
                self.assertEqual(run["result"]["text"], "本地识别文字")
                self.assertEqual(processor.decoded_format, format_name)

    def test_image_is_deduplicated_after_full_decode(self):
        image = complete_image("PNG")
        item, created = import_image_material(filename="screen.png", data=image)
        duplicate, created_again = import_image_material(filename="copy.png", data=image)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(item["id"], duplicate["id"])
        self.assertEqual(self.database_counts()[:2], (1, 1))

    def test_local_ocr_failure_is_audited_without_accepted_text(self):
        item, _ = import_image_material(filename="other.jpg", data=complete_image("JPEG"))
        with self.assertRaisesRegex(RuntimeError, "fixture OCR failure"):
            run_local_ocr(item["id"], processor=FailingOCR())
        conn = self.connect()
        failed = conn.execute(
            "SELECT status, error_message FROM extraction_runs WHERE item_id = ?", (item["id"],)
        ).fetchone()
        accepted_count = conn.execute("SELECT COUNT(*) FROM accepted_extractions").fetchone()[0]
        conn.close()
        self.assertEqual(failed["status"], "failed")
        self.assertIn("fixture OCR failure", failed["error_message"])
        self.assertEqual(accepted_count, 0)

    def test_explicit_reprocessing_always_creates_a_new_audit_run(self):
        item, _ = import_image_material(filename="repeat.png", data=complete_image("PNG"))

        first = run_local_ocr(item["id"], processor=TextOCR("first result"))
        second = run_local_ocr(item["id"], processor=TextOCR("second result"))

        conn = self.connect()
        runs = conn.execute(
            "SELECT id, status, result_json FROM extraction_runs WHERE item_id = ? ORDER BY id",
            (item["id"],),
        ).fetchall()
        conn.close()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual([run["id"] for run in runs], [first["id"], second["id"]])
        self.assertEqual([run["status"] for run in runs], ["succeeded", "succeeded"])
        self.assertIn("first result", runs[0]["result_json"])
        self.assertIn("second result", runs[1]["result_json"])

    def test_ocr_api_exposes_new_success_and_audited_failure(self):
        item, _ = import_image_material(filename="api.png", data=complete_image("PNG"))
        with patch("services.image_materials.LocalOCRProcessor", return_value=TextOCR("api result")):
            succeeded = create_ocr_run(item["id"])["run"]
        self.assertEqual(succeeded["status"], "succeeded")

        with (
            patch("services.image_materials.LocalOCRProcessor", return_value=FailingOCR()),
            self.assertRaises(HTTPException) as raised,
        ):
            create_ocr_run(item["id"])
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail, "fixture OCR failure")

        conn = self.connect()
        statuses = [row[0] for row in conn.execute(
            "SELECT status FROM extraction_runs WHERE item_id = ? ORDER BY id", (item["id"],)
        ).fetchall()]
        conn.close()
        self.assertEqual(statuses, ["succeeded", "failed"])

    @unittest.skipUnless(shutil.which("tesseract"), "本机未安装 Tesseract")
    def test_real_local_tesseract_reads_offline_english_and_chinese_fixture(self):
        languages = LocalOCRProcessor._available_languages(shutil.which("tesseract"))
        if "eng" not in languages or "chi_sim" not in languages:
            self.skipTest("本机缺少 Tesseract eng/chi_sim 语言包")

        image = Image.new("RGB", (1400, 320), "white")
        draw = ImageDraw.Draw(image)
        latin_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 64
        )
        chinese_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", 72
        )
        draw.text((60, 45), "ResearchMate OCR 2026", fill="black", font=latin_font)
        draw.text((60, 155), "本地图片识别", fill="black", font=chinese_font)
        output = io.BytesIO()
        image.save(output, format="PNG")

        item, _ = import_image_material(filename="bilingual.png", data=output.getvalue())
        run = run_local_ocr(item["id"])
        self.assertEqual(run["status"], "succeeded")
        self.assertIn("ResearchMate OCR 2026", run["result"]["text"])
        self.assertIn("本地图片识别", run["result"]["text"].replace(" ", ""))

    def test_rejects_corrupt_disguised_and_truncated_files_without_residue(self):
        invalid_files = {
            "non-image": b"not an image",
            "disguised": b"\x89PNG\r\n\x1a\nnot-a-real-png",
            "truncated": complete_image("JPEG")[:-24],
        }
        for name, data in invalid_files.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "损坏|伪装|完整解码|PNG"
            ):
                import_image_material(filename=f"{name}.png", data=data)
        self.assertEqual(self.database_counts(), (0, 0, 0, 0))
        self.assertEqual(self.asset_files(), [])

    def test_api_returns_visible_decode_error_without_residue(self):
        upload_file = tempfile.SpooledTemporaryFile()
        upload_file.write(b"\x89PNG\r\n\x1a\nbroken")
        upload_file.seek(0)
        upload = UploadFile(filename="fake.png", file=upload_file)
        with upload_file, self.assertRaises(HTTPException) as raised:
            asyncio.run(import_image_route(file=upload, title=""))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertRegex(raised.exception.detail, "损坏|伪装|完整解码")
        self.assertEqual(self.database_counts(), (0, 0, 0, 0))
        self.assertEqual(self.asset_files(), [])

    def test_rejects_byte_dimension_pixel_and_bomb_limits_without_residue(self):
        with self.assertRaisesRegex(ValueError, "10 MB"):
            import_image_material(filename="large.png", data=b"x" * (MAX_IMAGE_BYTES + 1))

        too_wide = complete_image("PNG", size=(MAX_IMAGE_WIDTH + 1, 1))
        with self.assertRaisesRegex(ValueError, "尺寸"):
            import_image_material(filename="wide.png", data=too_wide)

        too_tall = complete_image("PNG", size=(1, MAX_IMAGE_HEIGHT + 1))
        with self.assertRaisesRegex(ValueError, "尺寸"):
            import_image_material(filename="tall.png", data=too_tall)

        bomb_fixture = complete_image("PNG", size=(101, 100))
        with patch("PIL.Image.MAX_IMAGE_PIXELS", 5_000), self.assertRaisesRegex(
            ValueError, "解压炸弹"
        ):
            decode_image(bomb_fixture)

        self.assertEqual(MAX_IMAGE_PIXELS, 40_000_000)
        self.assertEqual(self.database_counts(), (0, 0, 0, 0))
        self.assertEqual(self.asset_files(), [])

    def test_preview_and_ocr_detect_asset_tampering_and_audit_ocr_failure(self):
        item, _ = import_image_material(filename="screen.webp", data=complete_image("WEBP"))
        asset = item["assets"][0]
        path = asset_repository.resolve_storage_path(asset["storage_path"])
        path.write_bytes(complete_image("PNG"))

        with self.assertRaisesRegex(ValueError, "大小|哈希|格式"):
            get_asset_file(asset["id"])
        with self.assertRaisesRegex(RuntimeError, "大小|哈希|格式"):
            run_local_ocr(item["id"], processor=FakeOCR())

        conn = self.connect()
        failed = conn.execute(
            "SELECT status, error_message FROM extraction_runs WHERE item_id = ?", (item["id"],)
        ).fetchone()
        conn.close()
        self.assertEqual(failed["status"], "failed")

    def test_assets_are_isolated_by_connection_workspace(self):
        first, _ = import_image_material(filename="alpha.png", data=complete_image("PNG"))
        first_path = get_asset_file(first["assets"][0]["id"])[1]

        second_db = str(self.root / "second.db")
        _init_workspace_db(second_db)
        self.db_path = second_db
        self.assertIsNone(get_asset_file(first["assets"][0]["id"]))
        second, _ = import_image_material(
            filename="beta.webp", data=complete_image("WEBP", color="blue")
        )
        second_path = get_asset_file(second["assets"][0]["id"])[1]

        self.assertNotEqual(first_path.parent, second_path.parent)
        self.assertTrue(first_path.is_file())
        self.assertTrue(second_path.is_file())


if __name__ == "__main__":
    unittest.main()
