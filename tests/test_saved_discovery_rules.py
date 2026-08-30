import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from crawlers.crossref_discovery import CrossrefResult
from api.routes.discoveries import remove_discovery_rule, replace_discovery_rule
from services.discoveries import (
    delete_discovery_rule, list_discovery_rules, run_all_discovery_rules,
    run_discovery_rule, save_discovery_rule, update_discovery_rule,
)
from storage.workspace import _init_workspace_db
from storage.models import SavedDiscoveryRuleUpdate
from storage.workspace_schema import MATERIAL_SCHEMA_VERSION, ensure_material_schema


QUERY = {
    "intent": "author", "query": "Alice Smith", "scope": "journal",
    "date_from": "2026-01-01", "date_to": "2026-08-30", "date_basis": "published",
    "container_title": None, "issn": None, "sort": "published", "limit": 10,
}


class EmptyCollector:
    def __init__(self):
        self.queries = []

    async def search(self, query):
        self.queries.append(query)
        return CrossrefResult([], 0, 0, False)


class FailingCollector:
    async def search(self, query):
        raise RuntimeError("fixture source unavailable")


class SavedDiscoveryRuleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patch = patch("services.discoveries.get_active_connection", side_effect=self.connect)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    async def test_save_list_manual_run_and_delete_reuse_discovery_lifecycle(self):
        rule = save_discovery_rule("  Alice recent work  ", QUERY)
        self.assertEqual(rule["name"], "Alice recent work")
        self.assertEqual(list_discovery_rules()[0]["query"], QUERY)
        collector = EmptyCollector()
        job, candidates = await run_discovery_rule(rule["id"], collector=collector)
        self.assertEqual(candidates, [])
        self.assertTrue(job["result"]["empty"])
        self.assertEqual(collector.queries, [QUERY])
        self.assertEqual(list_discovery_rules()[0]["query"], QUERY)

        updated = update_discovery_rule(rule["id"], "Alice IEEE", {**QUERY, "limit": 20})
        self.assertEqual(updated["name"], "Alice IEEE")
        self.assertEqual(updated["query"]["limit"], 20)
        delete_discovery_rule(rule["id"])
        self.assertEqual(list_discovery_rules(), [])

    async def test_schema_is_idempotent_and_rule_is_workspace_local(self):
        conn = self.connect()
        ensure_material_schema(conn)
        ensure_material_schema(conn)
        version = conn.execute(
            "SELECT value FROM schema_meta WHERE key='material_schema_version'"
        ).fetchone()[0]
        self.assertEqual(int(version), MATERIAL_SCHEMA_VERSION)
        self.assertIsNotNone(conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='saved_discovery_rules'"
        ).fetchone())
        conn.close()
        with self.assertRaisesRegex(ValueError, "不存在"):
            await run_discovery_rule(999, collector=EmptyCollector())

        body = SavedDiscoveryRuleUpdate(name="missing", query=QUERY)
        with self.assertRaises(HTTPException) as update_error:
            replace_discovery_rule(999, body)
        self.assertEqual(update_error.exception.status_code, 404)
        with self.assertRaises(HTTPException) as delete_error:
            remove_discovery_rule(999)
        self.assertEqual(delete_error.exception.status_code, 404)

    async def test_success_advances_checkpoint_and_next_run_overlaps_two_days(self):
        rule = save_discovery_rule("incremental", QUERY)
        first = EmptyCollector()
        first_now = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)
        await run_discovery_rule(rule["id"], collector=first, now=first_now)
        stored = list_discovery_rules()[0]
        self.assertEqual(stored["last_run_status"], "succeeded")
        self.assertEqual(stored["last_success_at"], first_now.isoformat())
        second = EmptyCollector()
        second_now = datetime(2026, 8, 30, 12, tzinfo=timezone.utc)
        await run_discovery_rule(rule["id"], collector=second, now=second_now)
        self.assertEqual(second.queries[0]["date_from"], "2026-08-18")
        self.assertEqual(second.queries[0]["date_to"], "2026-08-30")
        self.assertEqual(list_discovery_rules()[0]["query"], QUERY)

    async def test_failure_is_visible_does_not_advance_checkpoint_and_batch_continues(self):
        first = save_discovery_rule("first", QUERY)
        save_discovery_rule("second", QUERY)
        checkpoint_now = datetime(2026, 8, 20, tzinfo=timezone.utc)
        await run_discovery_rule(first["id"], collector=EmptyCollector(), now=checkpoint_now)
        with self.assertRaisesRegex(RuntimeError, "fixture source unavailable"):
            await run_discovery_rule(
                first["id"], collector=FailingCollector(),
                now=datetime(2026, 8, 30, tzinfo=timezone.utc),
            )
        failed = next(rule for rule in list_discovery_rules() if rule["id"] == first["id"])
        self.assertEqual(failed["last_run_status"], "failed")
        self.assertEqual(failed["last_success_at"], checkpoint_now.isoformat())
        self.assertIn("fixture source unavailable", failed["last_error"])

        results = await run_all_discovery_rules(
            collector_factory=lambda rule: FailingCollector() if rule["id"] == first["id"] else EmptyCollector(),
            now=datetime(2026, 8, 31, tzinfo=timezone.utc),
        )
        self.assertEqual([result["status"] for result in results], ["failed", "succeeded"])


if __name__ == "__main__":
    unittest.main()
