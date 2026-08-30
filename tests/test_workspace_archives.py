import asyncio
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes.workspaces import import_workspace as import_workspace_route
from services.action_projects import create_action_project
from services.image_materials import get_asset_file, import_image_material, run_local_ocr
from services.workspace_archives import (
    WorkspaceArchiveError,
    create_workspace_archive,
    import_workspace_upload,
)
from storage import assets, workspace


def complete_image(format_name="PNG", *, color="white"):
    output = io.BytesIO()
    Image.new("RGB", (80, 40), color).save(output, format=format_name, quality=95)
    return output.getvalue()


class FakeOCR:
    def extract(self, image_path):
        with Image.open(image_path) as image:
            image.load()
        return "portable OCR fixture"


class WorkspaceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace_dir = self.root / "workspaces"
        self.main_db = self.root / "main.db"
        self.patches = [
            patch.object(workspace, "WORKSPACE_DIR", self.workspace_dir),
            patch.object(assets, "DATA_DIR", self.root),
            patch.object(assets, "ASSET_ROOT", self.root / "assets"),
            patch("services.image_materials._update_workspace_item_count"),
            patch("api.routes.workspaces.get_main_conn", side_effect=self.main_connect),
        ]
        for active_patch in self.patches:
            active_patch.start()
        workspace._active_db_path = None
        workspace._workspace_leases.clear()
        self.alpha = workspace.create_workspace("alpha")
        workspace.switch_workspace(self.alpha)
        conn = self.main_connect()
        conn.execute("""CREATE TABLE workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            db_path TEXT NOT NULL, paper_count INTEGER DEFAULT 0,
            item_count INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')),
            opened_at TEXT DEFAULT (datetime('now'))
        )""")
        conn.commit()
        conn.close()

    def tearDown(self):
        workspace._active_db_path = None
        workspace._workspace_leases.clear()
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def main_connect(self):
        conn = sqlite3.connect(self.main_db)
        conn.row_factory = sqlite3.Row
        return conn

    def create_three_assets(self):
        items = []
        for index, format_name in enumerate(("PNG", "JPEG", "WEBP")):
            item, _ = import_image_material(
                filename=f"fixture-{format_name.lower()}",
                data=complete_image(format_name, color=(index * 50, 90, 130)),
            )
            items.append(item)
        return items

    def archive_copy(self) -> tuple[Path, bytes]:
        exported = create_workspace_archive()
        data = exported.path.read_bytes()
        exported.path.unlink()
        upload = self.root / "portable.zip"
        upload.write_bytes(data)
        return upload, data

    def rewrite_archive(self, source: bytes, mutate) -> Path:
        target = self.root / f"mutated-{len(list(self.root.glob('mutated-*')))}.zip"
        with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(
            target, "w", compression=zipfile.ZIP_DEFLATED
        ) as rewritten:
            entries = {info.filename: original.read(info) for info in original.infolist()}
            mutate(entries, rewritten)
            for name, data in entries.items():
                rewritten.writestr(name, data)
        return target

    def test_png_jpeg_webp_round_trip_preserves_database_ocr_and_isolation(self):
        items = self.create_three_assets()
        conn = workspace.get_active_connection()
        conn.execute(
            "INSERT INTO item_external_identities(item_id, identity_type, normalized_value) VALUES (?, 'doi', '10.1109/fixture')",
            (items[0]["id"],),
        )
        job_id = conn.execute(
            "INSERT INTO collection_jobs(collector, query_json, status, result_json) VALUES ('crossref_ieee', '{}', 'succeeded', '{\"truncated\":true}')"
        ).lastrowid
        candidate_id = conn.execute(
            """INSERT INTO candidates(job_id, title, content_text, source_kind, source_url,
               content_hash, canonical_id) VALUES (?, 'Radar fixture', 'fixture', 'crossref_ieee',
               'https://doi.org/10.1109/fixture', 'radar-fixture', 'doi:10.1109/fixture')""",
            (job_id,),
        ).lastrowid
        conn.execute(
            """INSERT INTO candidate_source_records
               (candidate_id, job_id, source_kind, source_record_id, status, facts_json)
               VALUES (?, ?, 'openalex', 'W123', 'succeeded', '{"doi":"10.1109/fixture"}')""",
            (candidate_id, job_id),
        )
        conn.execute(
            """INSERT INTO saved_discovery_rules(name, source_kind, query_json)
               VALUES ('Portable IEEE rule', 'crossref_ieee', '{"intent":"topic","query":"robotics"}')"""
        )
        conn.execute(
            """INSERT INTO candidate_ai_runs
               (candidate_ids_json, status, input_scope_json, input_hash, processor,
                processor_version, prompt_version, result_json)
               VALUES (?, 'succeeded', '["title:300"]', 'brief-hash',
                       'candidate_brief', '1', 'candidate-brief-v1', '{"overview":"fixture"}')""",
            (json.dumps([candidate_id]),),
        )
        conn.commit()
        conn.close()
        project = create_action_project({
            "title": "Portable evidence project",
            "objective": "Keep ordered evidence through archive import",
            "notes": "User-authored conclusion",
            "next_action": "Verify imported images",
            "item_ids": [items[2]["id"], items[0]["id"]],
        })
        ocr_run = run_local_ocr(items[0]["id"], processor=FakeOCR())
        conn = workspace.get_active_connection()
        conn.execute(
            """INSERT INTO accepted_extractions(item_id, extraction_kind, run_id, text_value)
               VALUES (?, 'ocr', ?, 'portable OCR fixture')""",
            (items[0]["id"], ocr_run["id"]),
        )
        conn.commit()
        conn.close()
        source_asset_dir = assets.workspace_asset_path(self.alpha)

        upload, _ = self.archive_copy()
        with zipfile.ZipFile(upload) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"manifest.json", "workspace.db", "assets/1.png", "assets/2.jpg", "assets/3.webp"},
            )
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["format"], "researchmate-workspace")
            self.assertEqual(manifest["version"], 1)
            self.assertEqual(len(manifest["assets"]), 3)

        imported = import_workspace_upload(upload, "alpha.researchmate.zip")
        self.assertNotEqual(imported.db_path, self.alpha)
        self.assertTrue(workspace.switch_workspace(imported.db_path))
        imported_asset_dir = assets.workspace_asset_path(imported.db_path)
        self.assertNotEqual(source_asset_dir, imported_asset_dir)
        self.assertEqual(len(list(imported_asset_dir.iterdir())), 3)

        for item in items:
            conn = workspace.get_active_connection()
            asset = conn.execute(
                "SELECT * FROM assets WHERE item_id = ?", (item["id"],)
            ).fetchone()
            conn.close()
            stored, path = get_asset_file(asset["id"])
            self.assertEqual((stored["image_width"], stored["image_height"]), (80, 40))
            self.assertTrue(path.is_relative_to(imported_asset_dir))
        conn = workspace.get_active_connection()
        accepted = conn.execute(
            "SELECT text_value FROM accepted_extractions WHERE item_id = ?", (items[0]["id"],)
        ).fetchone()[0]
        imported_project = conn.execute(
            "SELECT title, objective, notes, next_action, status FROM action_projects WHERE id = ?",
            (project["id"],),
        ).fetchone()
        imported_identity = conn.execute(
            "SELECT identity_type, normalized_value FROM item_external_identities"
        ).fetchone()
        imported_radar = conn.execute(
            "SELECT canonical_id FROM candidates WHERE job_id = ?", (job_id,)
        ).fetchone()
        imported_source = conn.execute(
            "SELECT source_kind, source_record_id, facts_json FROM candidate_source_records"
        ).fetchone()
        imported_rule = conn.execute(
            "SELECT name, source_kind, query_json FROM saved_discovery_rules"
        ).fetchone()
        imported_brief = conn.execute(
            "SELECT candidate_ids_json, status, result_json FROM candidate_ai_runs"
        ).fetchone()
        imported_evidence = [row[0] for row in conn.execute(
            "SELECT item_id FROM action_project_items WHERE project_id = ? ORDER BY position",
            (project["id"],),
        ).fetchall()]
        conn.close()
        self.assertEqual(accepted, "portable OCR fixture")
        self.assertEqual(tuple(imported_project), (
            "Portable evidence project",
            "Keep ordered evidence through archive import",
            "User-authored conclusion",
            "Verify imported images",
            "active",
        ))
        self.assertEqual(imported_evidence, [items[2]["id"], items[0]["id"]])
        self.assertEqual(tuple(imported_identity), ("doi", "10.1109/fixture"))
        self.assertEqual(imported_radar[0], "doi:10.1109/fixture")
        self.assertEqual(tuple(imported_source), (
            "openalex", "W123", '{"doi":"10.1109/fixture"}',
        ))
        self.assertEqual(tuple(imported_rule), (
            "Portable IEEE rule", "crossref_ieee", '{"intent":"topic","query":"robotics"}',
        ))
        self.assertEqual(imported_brief[1], "succeeded")
        self.assertEqual(json.loads(imported_brief[0]), [candidate_id])
        self.assertEqual(run_local_ocr(items[0]["id"], processor=FakeOCR())["status"], "succeeded")
        self.assertEqual(len(list(source_asset_dir.iterdir())), 3)

    def test_route_import_registers_switches_and_rejects_bad_upload_visibly(self):
        self.create_three_assets()
        upload, archive_data = self.archive_copy()
        upload_file = tempfile.SpooledTemporaryFile()
        upload_file.write(archive_data)
        upload_file.seek(0)
        response = asyncio.run(import_workspace_route(
            UploadFile(filename="portable.researchmate.zip", file=upload_file)
        ))
        upload_file.close()
        self.assertTrue(response["ok"])
        self.assertFalse(response["legacy_database_only"])
        self.assertEqual(workspace.get_active_path(), response["db_path"])
        conn = self.main_connect()
        registered = conn.execute(
            "SELECT name, db_path FROM workspaces WHERE db_path = ?", (response["db_path"],)
        ).fetchone()
        conn.close()
        self.assertEqual(tuple(registered), (response["name"], response["db_path"]))

        bad_file = tempfile.SpooledTemporaryFile()
        bad_file.write(b"not a workspace")
        bad_file.seek(0)
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(import_workspace_route(
                UploadFile(filename="broken.zip", file=bad_file)
            ))
        bad_file.close()
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("完整归档", raised.exception.detail)

    def test_export_rejects_missing_or_tampered_asset(self):
        item = self.create_three_assets()[0]
        asset = item["assets"][0]
        path = assets.resolve_storage_path(asset["storage_path"])
        original = path.read_bytes()
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(WorkspaceArchiveError, "大小|哈希"):
            create_workspace_archive()
        path.write_bytes(original)
        path.unlink()
        with self.assertRaisesRegex(WorkspaceArchiveError, "缺失"):
            create_workspace_archive()

    def test_import_rejects_traversal_missing_extra_tampered_and_version(self):
        self.create_three_assets()
        _, source = self.archive_copy()
        baseline_databases = set(self.workspace_dir.glob("*.db"))
        baseline_asset_dirs = set((self.root / "assets").iterdir())

        def traversal(entries, archive):
            archive.writestr("../escape", b"escape")

        def missing(entries, archive):
            entries.pop("assets/1.png")

        def extra(entries, archive):
            archive.writestr("assets/orphan.png", complete_image())

        def tampered(entries, archive):
            entries["assets/1.png"] = complete_image("PNG", color="red")

        def version(entries, archive):
            manifest = json.loads(entries["manifest.json"])
            manifest["version"] = 999
            entries["manifest.json"] = json.dumps(manifest).encode()

        cases = (
            (traversal, "非法路径"),
            (missing, "缺失|未声明"),
            (extra, "未声明"),
            (tampered, "大小|哈希"),
            (version, "不支持"),
        )
        for mutate, error in cases:
            archive = self.rewrite_archive(source, mutate)
            with self.subTest(error=error), self.assertRaisesRegex(
                WorkspaceArchiveError, error
            ):
                import_workspace_upload(archive, "invalid.zip")
        self.assertEqual(set(self.workspace_dir.glob("*.db")), baseline_databases)
        self.assertEqual(set((self.root / "assets").iterdir()), baseline_asset_dirs)
        self.assertFalse((self.root / "escape").exists())

    def test_import_rejects_symlink_and_bounded_uncompressed_size(self):
        self.create_three_assets()
        _, source = self.archive_copy()

        def symlink(entries, archive):
            info = zipfile.ZipInfo("assets/link.png")
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            archive.writestr(info, b"assets/1.png")

        archive = self.rewrite_archive(source, symlink)
        with self.assertRaisesRegex(WorkspaceArchiveError, "符号链接"):
            import_workspace_upload(archive, "symlink.zip")

        valid = self.root / "portable.zip"
        with patch("services.workspace_archives.MAX_UNCOMPRESSED_BYTES", 100):
            with self.assertRaisesRegex(WorkspaceArchiveError, "解压后"):
                import_workspace_upload(valid, "bomb.zip")

    def test_legacy_database_only_import_and_asset_record_rejection(self):
        legacy = self.root / "legacy.db"
        workspace._init_workspace_db(str(legacy))
        imported = import_workspace_upload(legacy, "legacy.db")
        self.assertTrue(imported.legacy_database_only)
        self.assertTrue(Path(imported.db_path).is_file())

        self.create_three_assets()
        raw_with_assets = self.root / "with-assets.db"
        source = sqlite3.connect(self.alpha)
        target = sqlite3.connect(raw_with_assets)
        source.backup(target)
        target.close()
        source.close()
        with self.assertRaisesRegex(WorkspaceArchiveError, "完整 .zip"):
            import_workspace_upload(raw_with_assets, "with-assets.db")


if __name__ == "__main__":
    unittest.main()
