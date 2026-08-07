import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from crawlers.single_url import CollectedPage, SinglePublicURLCollector, validate_public_url
from api.routes.url_imports import create_url_import
from services.url_imports import (
    accept_candidate,
    import_public_url,
    list_candidates,
    list_url_imports,
    reject_candidate,
)
from storage.workspace import _init_workspace_db
from storage.models import PublicURLImportRequest


class FixtureCollector:
    async def collect(self, url):
        return CollectedPage(
            title="Fixture 页面",
            content_text="岗位职责：维护离线 fixture 服务",
            source_url="https://example.com/final",
            source_facts={"collector": "fixture", "http_status": 200},
        )


class FailingCollector:
    async def collect(self, url):
        raise RuntimeError("fixture timeout")


class URLImportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patches = [
            patch("services.url_imports.get_active_connection", side_effect=self.connect),
            patch("services.url_imports._update_workspace_item_count"),
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

    async def test_candidate_is_separate_until_explicit_idempotent_accept(self):
        job, candidate = await import_public_url(
            "https://example.com/start", collector=FixtureCollector()
        )
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(candidate["status"], "pending")
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
        conn.close()

        accepted, item, duplicate = accept_candidate(candidate["id"])
        self.assertFalse(duplicate)
        self.assertEqual(accepted["accepted_item_id"], item["id"])
        self.assertEqual(item["source_kind"], "public_url")
        self.assertEqual(item["metadata"]["provenance"]["collector"], "fixture")

        accepted_again, same_item, reused = accept_candidate(candidate["id"])
        self.assertTrue(reused)
        self.assertEqual(accepted_again["id"], accepted["id"])
        self.assertEqual(same_item["id"], item["id"])

    async def test_failure_is_persisted_and_reject_is_visible(self):
        with self.assertRaisesRegex(RuntimeError, "fixture timeout"):
            await import_public_url(
                "https://example.com/fail", collector=FailingCollector()
            )
        jobs = list_url_imports()
        self.assertEqual(jobs[0]["status"], "failed")
        self.assertIn("fixture timeout", jobs[0]["error_message"])

        _, candidate = await import_public_url(
            "https://example.com/reject", collector=FixtureCollector()
        )
        rejected = reject_candidate(candidate["id"])
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(list_candidates(status="rejected")[0]["id"], candidate["id"])
        with self.assertRaisesRegex(ValueError, "已拒绝"):
            accept_candidate(candidate["id"])

    async def test_public_address_policy_and_offline_html_fixture(self):
        async def public_resolver(host, port):
            return ["93.184.216.34"]

        async def private_resolver(host, port):
            return ["127.0.0.1"]

        with self.assertRaisesRegex(ValueError, "私有"):
            await validate_public_url("https://example.com/page", resolver=private_resolver)
        with self.assertRaisesRegex(ValueError, "认证"):
            await validate_public_url(
                "https://user:pass@example.com/page", resolver=public_resolver
            )

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /", request=request)
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                text="<html><title>离线标题</title><body><main><h1>标题</h1><p>正文内容</p></main><script>secret</script></body></html>",
                request=request,
            )

        collector = SinglePublicURLCollector(
            resolver=public_resolver, transport=httpx.MockTransport(handler)
        )
        page = await collector.collect("https://example.com/page")
        self.assertEqual(page.title, "离线标题")
        self.assertIn("正文内容", page.content_text)
        self.assertNotIn("secret", page.content_text)

    async def test_robots_denial_is_not_bypassed(self):
        async def public_resolver(host, port):
            return ["93.184.216.34"]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, text="User-agent: *\nDisallow: /", request=request
            )

        collector = SinglePublicURLCollector(
            resolver=public_resolver, transport=httpx.MockTransport(handler)
        )
        with self.assertRaisesRegex(RuntimeError, "robots"):
            await collector.collect("https://example.com/private")

    async def test_api_returns_persisted_job_and_candidate_shape(self):
        expected_job = {"id": 1, "status": "succeeded"}
        expected_candidate = {"id": 2, "status": "pending"}
        with patch(
            "api.routes.url_imports.import_public_url",
            new=AsyncMock(return_value=(expected_job, expected_candidate)),
        ):
            result = await create_url_import(
                PublicURLImportRequest(url="https://example.com/page")
            )
        self.assertEqual(result, {
            "job": expected_job, "candidate": expected_candidate,
        })


if __name__ == "__main__":
    unittest.main()
