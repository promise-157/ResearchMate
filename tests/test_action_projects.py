import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes.action_projects import (
    create_project as create_project_route,
    get_project as get_project_route,
    replace_project_materials as replace_project_materials_route,
    update_project as update_project_route,
)
from services.action_projects import (
    create_action_project,
    get_action_project,
    list_action_projects,
    replace_action_project_materials,
    update_action_project,
)
from storage import assets, workspace
from storage.models import (
    ActionProjectCreate,
    ActionProjectMaterialsUpdate,
    ActionProjectUpdate,
)
from storage.workspace import _init_workspace_db
from storage.workspace_schema import MATERIAL_SCHEMA_VERSION, ensure_material_schema


class ActionProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = str(self.root / "alpha.db")
        _init_workspace_db(self.db_path)
        self.service_patch = patch(
            "services.action_projects.get_active_connection", side_effect=self.connect
        )
        self.service_patch.start()

    def tearDown(self):
        self.service_patch.stop()
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def create_items(self, count=3):
        conn = self.connect()
        ids = []
        for index in range(count):
            ids.append(conn.execute(
                """INSERT INTO items
                   (title, content_text, summary, source_kind, content_hash, status)
                   VALUES (?, ?, ?, 'text_import', ?, 'active')""",
                (
                    f"Evidence {index + 1}",
                    f"immutable source {index + 1}",
                    f"summary {index + 1}",
                    f"evidence-{index + 1}",
                ),
            ).lastrowid)
        conn.commit()
        conn.close()
        return ids

    def test_create_update_and_ordered_replacement_preserve_material_facts(self):
        item_ids = self.create_items()
        conn = self.connect()
        before = [tuple(row) for row in conn.execute(
            "SELECT id, title, content_text, source_kind, content_hash FROM items ORDER BY id"
        )]
        conn.close()

        project = create_action_project({
            "title": "Choose retrieval design",
            "objective": "Make an evidence-backed decision",
            "notes": "User-authored starting note",
            "next_action": "Compare operational costs",
            "item_ids": [item_ids[2], item_ids[0]],
        })
        self.assertEqual(
            [material["id"] for material in project["materials"]],
            [item_ids[2], item_ids[0]],
        )
        self.assertEqual(project["status"], "active")

        updated = update_action_project(project["id"], {
            "notes": "User conclusion: keep LIKE for now",
            "next_action": "Measure again at 50k records",
            "status": "completed",
        })
        self.assertEqual(updated["status"], "completed")
        self.assertIn("keep LIKE", updated["notes"])

        replaced = replace_action_project_materials(
            project["id"], [item_ids[1], item_ids[2], item_ids[0]]
        )
        self.assertEqual(
            [material["id"] for material in replaced["materials"]], item_ids[1:2] + [item_ids[2], item_ids[0]]
        )
        conn = self.connect()
        after = [tuple(row) for row in conn.execute(
            "SELECT id, title, content_text, source_kind, content_hash FROM items ORDER BY id"
        )]
        conn.close()
        self.assertEqual(after, before)

    def test_invalid_evidence_is_atomic_and_workspace_isolated(self):
        item_ids = self.create_items(2)
        with self.assertRaisesRegex(ValueError, "重复"):
            create_action_project({
                "title": "duplicate",
                "objective": "",
                "notes": "",
                "next_action": "",
                "item_ids": [item_ids[0], item_ids[0]],
            })
        with self.assertRaisesRegex(ValueError, "标题"):
            create_action_project({
                "title": "   ",
                "objective": "",
                "notes": "",
                "next_action": "",
                "item_ids": item_ids,
            })
        with self.assertRaisesRegex(ValueError, "当前工作区"):
            create_action_project({
                "title": "missing",
                "objective": "",
                "notes": "",
                "next_action": "",
                "item_ids": [999],
            })
        self.assertEqual(list_action_projects(), [])

        project = create_action_project({
            "title": "alpha",
            "objective": "",
            "notes": "",
            "next_action": "",
            "item_ids": item_ids,
        })
        with self.assertRaisesRegex(ValueError, "当前工作区"):
            replace_action_project_materials(project["id"], [item_ids[0], 999])
        self.assertEqual(
            [item["id"] for item in get_action_project(project["id"])["materials"]],
            item_ids,
        )

        second_db = str(self.root / "beta.db")
        _init_workspace_db(second_db)
        self.db_path = second_db
        self.assertEqual(list_action_projects(), [])
        self.assertIsNone(get_action_project(project["id"]))

    def test_api_shapes_and_clear_scope(self):
        item_ids = self.create_items(1)
        created = create_project_route(ActionProjectCreate(
            title="API project",
            objective="Ship a useful workflow",
            notes="",
            next_action="Write browser coverage",
            item_ids=item_ids,
        ))["project"]
        fetched = get_project_route(created["id"])["project"]
        self.assertEqual(fetched["title"], "API project")
        updated = update_project_route(
            created["id"], ActionProjectUpdate(status="completed")
        )["project"]
        self.assertEqual(updated["status"], "completed")
        replaced = replace_project_materials_route(
            created["id"], ActionProjectMaterialsUpdate(item_ids=item_ids)
        )["project"]
        self.assertEqual(replaced["material_count"], 1)

        with (
            patch.object(workspace, "_active_db_path", self.db_path),
            patch.object(workspace, "_workspace_leases", {}),
            patch.object(assets, "DATA_DIR", self.root),
            patch.object(assets, "ASSET_ROOT", self.root / "assets"),
        ):
            workspace.clear_workspace()
        conn = self.connect()
        counts = tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
            "action_project_items", "action_projects", "items"
        ))
        conn.close()
        self.assertEqual(counts, (0, 0, 0))

    def test_schema_migration_is_idempotent(self):
        conn = self.connect()
        conn.execute("DROP TABLE action_project_items")
        conn.execute("DROP TABLE action_projects")
        conn.execute(
            "UPDATE schema_meta SET value = '11' WHERE key = 'material_schema_version'"
        )
        conn.commit()
        ensure_material_schema(conn)
        ensure_material_schema(conn)
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        version = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'material_schema_version'"
        ).fetchone()[0]
        conn.close()
        self.assertIn("action_projects", tables)
        self.assertIn("action_project_items", tables)
        self.assertEqual(version, str(MATERIAL_SCHEMA_VERSION))


if __name__ == "__main__":
    unittest.main()
