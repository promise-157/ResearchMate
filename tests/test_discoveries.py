import gzip
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

from api.routes.discoveries import create_arxiv_discovery
from crawlers.arxiv_discovery import (
    ARXIV_API_URL, MAX_RESPONSE_BYTES, ArxivDiscoveryCollector, DiscoveredRecord,
)
from services.discoveries import discover_arxiv, list_collection_jobs
from services.url_imports import accept_candidate
from storage.models import ArxivDiscoveryRequest
from storage.workspace import _init_workspace_db
from storage.workspace_schema import ensure_material_schema


class FixtureDiscovery:
    async def search(self, query, limit):
        return [
            DiscoveredRecord(
                title=f"Fixture Paper {index}",
                content_text=f"Fixture Paper {index}\nAbstract about {query} and local retrieval.",
                summary=f"Abstract {index}",
                source_url=f"https://arxiv.org/abs/2608.0000{index}",
                source_facts={
                    "collector": "arxiv_api", "arxiv_id": f"2608.0000{index}",
                    "suggested_item_type": "paper",
                },
            )
            for index in range(1, min(limit, 2) + 1)
        ]


class FailingDiscovery:
    async def search(self, query, limit):
        raise httpx.ConnectTimeout("fixture timeout")


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patches = [
            patch("services.discoveries.get_active_connection", side_effect=self.connect),
            patch("services.url_imports.get_active_connection", side_effect=self.connect),
            patch("services.url_imports._update_workspace_item_count"),
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

    async def test_persistent_job_yields_multiple_review_candidates(self):
        job, candidates = await discover_arxiv(
            "local retrieval", limit=2, collector=FixtureDiscovery()
        )
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["candidate_count"], 2)
        self.assertEqual(len(candidates), 2)
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
        conn.close()

        _, item, duplicate = accept_candidate(candidates[0]["id"])
        self.assertFalse(duplicate)
        self.assertEqual(item["item_type"], "paper")
        self.assertEqual(item["metadata"]["provenance"]["arxiv_id"], "2608.00001")
        self.assertEqual(list_collection_jobs()[0]["accepted_count"], 1)

    async def test_failure_is_visible_and_offline_atom_parser_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError, "fixture timeout"):
            await discover_arxiv("failure", collector=FailingDiscovery())
        self.assertEqual(list_collection_jobs()[0]["status"], "failed")

        xml = """<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><id>http://arxiv.org/abs/2608.12345</id><published>2026-08-01T00:00:00Z</published>
          <title> Offline   Paper </title><summary> Fixture abstract. </summary>
          <author><name>Alice</name></author><category term="cs.IR" /></entry></feed>"""
        records = ArxivDiscoveryCollector().parse_atom(xml, limit=1)
        self.assertEqual(records[0].source_url, "https://arxiv.org/abs/2608.12345")
        self.assertEqual(records[0].source_facts["authors"], ["Alice"])
        self.assertTrue(records[0].source_facts["fetched_at"].endswith("+00:00"))

    async def test_offline_arxiv_request_is_bounded_and_preserves_provenance(self):
        requests = []
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry><id>https://arxiv.org/abs/2608.54321v2</id>
          <published>2026-08-12T00:00:00Z</published>
          <title> Bounded Fixture </title><summary> Offline abstract. </summary>
          <author><name>Alice</name></author><author><name>Bob</name></author>
          <category term="cs.IR" /></entry></feed>"""

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                headers={"Content-Type": "application/atom+xml; charset=UTF-8"},
                text=xml,
                request=request,
            )

        collector = ArxivDiscoveryCollector(transport=httpx.MockTransport(handler))
        records = await collector.search("local retrieval", 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url.copy_with(query=None)), ARXIV_API_URL)
        self.assertEqual(requests[0].url.params["search_query"], "all:local retrieval")
        self.assertEqual(requests[0].url.params["max_results"], "1")
        self.assertEqual(records[0].source_facts["arxiv_id"], "2608.54321v2")
        self.assertEqual(records[0].source_facts["authors"], ["Alice", "Bob"])
        self.assertEqual(records[0].source_facts["categories"], ["cs.IR"])
        self.assertEqual(records[0].source_facts["published"], "2026-08-12T00:00:00Z")

    async def test_arxiv_http_type_size_encoding_and_xml_failures_are_stable(self):
        fixtures = (
            (503, "application/atom+xml", b"", "HTTP 503"),
            (200, "text/html", b"<html>error</html>", "非 Atom XML"),
            (200, "application/atom+xml", b"\xff\xfe", "UTF-8"),
            (200, "application/atom+xml", b"<feed>", "无效 Atom XML"),
            (
                200,
                "application/atom+xml",
                gzip.compress(b"<feed>" + b"x" * MAX_RESPONSE_BYTES + b"</feed>"),
                "超过 2 MB",
            ),
        )
        for status, content_type, content, error in fixtures:
            def handler(
                request: httpx.Request,
                status=status,
                content_type=content_type,
                content=content,
                error=error,
            ) -> httpx.Response:
                headers = {"Content-Type": content_type}
                if error == "超过 2 MB":
                    headers["Content-Encoding"] = "gzip"
                return httpx.Response(
                    status, headers=headers, content=content, request=request
                )

            collector = ArxivDiscoveryCollector(transport=httpx.MockTransport(handler))
            with self.subTest(error=error), self.assertRaisesRegex(RuntimeError, error):
                await collector.search("fixture", 1)

    async def test_api_returns_job_and_candidates(self):
        expected = ({"id": 1}, [{"id": 2}])
        with patch(
            "api.routes.discoveries.discover_arxiv", new=AsyncMock(return_value=expected)
        ):
            result = await create_arxiv_discovery(
                ArxivDiscoveryRequest(query="retrieval", limit=1)
            )
        self.assertEqual(result, {"job": expected[0], "candidates": expected[1]})

    async def test_m4_single_candidate_schema_migrates_without_data_loss(self):
        conn = self.connect()
        conn.execute("DROP TABLE candidates")
        conn.execute("""CREATE TABLE candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES collection_jobs(id) ON DELETE CASCADE,
            title TEXT NOT NULL, content_text TEXT NOT NULL, summary TEXT,
            source_kind TEXT NOT NULL, source_url TEXT NOT NULL, content_hash TEXT NOT NULL,
            source_facts_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending',
            accepted_item_id INTEGER REFERENCES items(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(job_id)
        )""")
        cursor = conn.execute(
            "INSERT INTO collection_jobs (collector, query_json) VALUES ('single_public_url', '{}')"
        )
        conn.execute(
            """INSERT INTO candidates
               (job_id, title, content_text, source_kind, source_url, content_hash)
               VALUES (?, 'old', 'old body', 'public_url', 'https://example.com/old', 'old-hash')""",
            (cursor.lastrowid,),
        )
        conn.commit()
        ensure_material_schema(conn)
        ensure_material_schema(conn)
        conn.execute(
            """INSERT INTO candidates
               (job_id, title, content_text, source_kind, source_url, content_hash)
               VALUES (?, 'new', 'new body', 'public_url', 'https://example.com/new', 'new-hash')""",
            (cursor.lastrowid,),
        )
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0], 2)
        conn.close()


if __name__ == "__main__":
    unittest.main()
