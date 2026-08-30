import gzip
import json
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes.discoveries import create_crossref_discovery
from crawlers.crossref_discovery import (
    CROSSREF_API_URL, MAX_RESPONSE_BYTES, CrossrefDiscoveryCollector,
    CrossrefResult, normalize_doi,
)
from crawlers.discovery_models import DiscoveredRecord
from services.discoveries import discover_crossref
from services.url_imports import accept_candidate
from storage.models import CrossrefDiscoveryRequest
from storage.workspace import _init_workspace_db
from storage.workspace_schema import MATERIAL_SCHEMA_VERSION, ensure_material_schema


QUERY = {
    "intent": "topic", "query": "Hermite spline trajectory planning", "scope": "journal",
    "date_from": "2026-01-01", "date_to": "2026-08-29",
    "date_basis": "indexed",
    "container_title": None, "issn": None, "sort": "relevance", "limit": 2,
}


class FixtureCollector:
    calls = 0

    async def search(self, query):
        self.calls += 1
        records = []
        for suffix, text in (("3681187", "first body"), ("3713731", "second body")):
            doi = f"10.1109/LRA.2026.{suffix}"
            records.append(DiscoveredRecord(
                title=f"Fixture {suffix}", content_text=text, summary="",
                source_url=f"https://doi.org/{doi.lower()}",
                source_facts={"canonical_id": f"doi:{doi.lower()}", "doi": doi.lower(),
                              "collector": "crossref_ieee", "suggested_item_type": "paper"},
            ))
        return CrossrefResult(records, 12, 1, True)


class CrossrefDiscoveryTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_offline_fixture_bounds_query_parses_facts_and_deduplicates_doi(self):
        fixture = json.loads((ROOT / "tests/fixtures/crossref_ieee_page.json").read_text())
        requests = []

        def handler(request):
            requests.append(request)
            payload = fixture if len(requests) == 1 else {
                "message": {"total-results": 4, "items": [], "next-cursor": ""}
            }
            return httpx.Response(200, headers={"Content-Type": "application/json"}, json=payload, request=request)

        result = await CrossrefDiscoveryCollector(transport=httpx.MockTransport(handler)).search(QUERY)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].source_facts["doi"], "10.1109/lra.2026.3681187")
        self.assertEqual(result.records[0].source_facts["container_title"], "IEEE Robotics and Automation Letters")
        self.assertFalse(result.records[0].source_facts["has_abstract"])
        self.assertIn("Hermite & Spline", result.records[0].title)
        self.assertEqual(str(requests[0].url.copy_with(query=None)), CROSSREF_API_URL)
        self.assertIn("prefix:10.1109", requests[0].url.params["filter"])
        self.assertIn("from-index-date:2026-01-01", requests[0].url.params["filter"])
        self.assertEqual(requests[0].url.params["rows"], "2")
        self.assertLessEqual(len(requests), 5)

    async def test_search_intents_map_to_source_queries_without_new_lifecycle(self):
        fixture = json.loads((ROOT / "tests/fixtures/crossref_ieee_page.json").read_text())
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200, headers={"Content-Type": "application/json"},
                json=fixture, request=request,
            )

        collector = CrossrefDiscoveryCollector(transport=httpx.MockTransport(handler))
        journal_query = {
            **QUERY, "intent": "journal_latest", "query": "",
            "container_title": "IEEE Robotics and Automation Letters",
            "issn": "23773766", "sort": "indexed",
        }
        await collector.search(journal_query)
        params = requests[0].url.params
        self.assertNotIn("query.bibliographic", params)
        self.assertIn("issn:23773766", params["filter"])
        self.assertEqual(params["query.container-title"], journal_query["container_title"])

        requests.clear()
        await collector.search({**QUERY, "intent": "exact"})
        params = requests[0].url.params
        self.assertEqual(params["query.title"], QUERY["query"])
        self.assertNotIn("from-index-date", params["filter"])

        requests.clear()
        await collector.search({**QUERY, "intent": "author", "query": "Alice Smith"})
        params = requests[0].url.params
        self.assertEqual(params["query.author"], "Alice Smith")
        self.assertNotIn("query.bibliographic", params)

    async def test_exact_doi_uses_one_bounded_record_request(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/crossref_ieee_indexed_record.json").read_text()
        )
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(
                200, headers={"Content-Type": "application/json"},
                json={"message": fixture["message"]["items"][0]}, request=request,
            )

        result = await CrossrefDiscoveryCollector(
            transport=httpx.MockTransport(handler)
        ).search({
            **QUERY, "intent": "exact", "query": "https://doi.org/10.1109/LRA.2026.3713731",
            "date_from": None, "date_to": None, "limit": 1,
        })
        self.assertEqual(len(requests), 1)
        self.assertTrue(str(requests[0].url).endswith("10.1109%2Flra.2026.3713731"))
        self.assertEqual(result.records[0].source_facts["doi"], "10.1109/lra.2026.3713731")

    async def test_service_persists_result_and_identity_acceptance_reuses_item(self):
        _, first = await discover_crossref(QUERY, collector=FixtureCollector())
        job, second = await discover_crossref(QUERY, collector=FixtureCollector())
        self.assertTrue(job["result"]["truncated"])
        self.assertEqual(job["result"]["skipped_count"], 1)
        self.assertEqual(second[0]["source_facts"]["existing_candidate_id"], first[0]["id"])
        _, item, duplicate = accept_candidate(first[0]["id"])
        self.assertFalse(duplicate)
        _, same, duplicate = accept_candidate(second[0]["id"])
        self.assertTrue(duplicate)
        self.assertEqual(same["id"], item["id"])
        _, third = await discover_crossref(QUERY, collector=FixtureCollector())
        self.assertEqual(third[0]["source_facts"]["existing_candidate_status"], "accepted")
        self.assertEqual(third[0]["source_facts"]["existing_item_id"], item["id"])
        self.assertEqual(third[0]["source_facts"]["existing_candidate_item_id"], item["id"])
        conn = self.connect()
        identity = conn.execute("SELECT identity_type, normalized_value FROM item_external_identities").fetchone()
        self.assertEqual(tuple(identity), ("doi", "10.1109/lra.2026.3681187"))
        conn.close()

    async def test_concurrent_accepts_of_same_doi_have_one_identity_owner(self):
        _, first = await discover_crossref(QUERY, collector=FixtureCollector())
        _, second = await discover_crossref(QUERY, collector=FixtureCollector())
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                accept_candidate, (first[0]["id"], second[0]["id"])
            ))
        item_ids = {result[1]["id"] for result in results}
        self.assertEqual(len(item_ids), 1)
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM item_external_identities").fetchone()[0], 1
        )
        accepted_ids = {
            row[0] for row in conn.execute(
                "SELECT accepted_item_id FROM candidates WHERE id IN (?, ?)",
                (first[0]["id"], second[0]["id"]),
            )
        }
        self.assertEqual(accepted_ids, item_ids)
        conn.close()

    async def test_empty_failure_retry_and_response_guards_are_visible(self):
        empty = CrossrefResult([], 0, 0, False)
        collector = AsyncMock()
        collector.search.return_value = empty
        job, candidates = await discover_crossref(QUERY, collector=collector)
        self.assertEqual(candidates, [])
        self.assertTrue(job["result"]["empty"])

        cases = (("text/html", b"{}", "非 JSON"),
                 ("application/json", b"{", "无效 UTF-8 JSON"),
                 ("application/json", b"x" * (MAX_RESPONSE_BYTES + 1), "超过 2 MB"))
        for content_type, content, error in cases:
            def handler(request, content_type=content_type, content=content):
                return httpx.Response(200, headers={"Content-Type": content_type}, content=content, request=request)
            with self.subTest(error=error), self.assertRaisesRegex(RuntimeError, error):
                await CrossrefDiscoveryCollector(transport=httpx.MockTransport(handler)).search(QUERY)

        attempts = 0
        def limited(request):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return httpx.Response(429, headers={"Retry-After": "0"}, request=request)
            return httpx.Response(200, headers={"Content-Type": "application/json"}, json={"message": {"total-results": 0, "items": []}}, request=request)
        with patch("crawlers.crossref_discovery.asyncio.sleep", new=AsyncMock()) as sleep:
            await CrossrefDiscoveryCollector(transport=httpx.MockTransport(limited)).search(QUERY)
        self.assertEqual(attempts, 3)
        self.assertEqual(sleep.await_count, 2)

    async def test_compressed_json_is_decoded_once_and_still_size_bounded(self):
        payload = json.dumps({
            "message": {"total-results": 0, "items": []}
        }).encode()

        def handler(request):
            return httpx.Response(
                200,
                headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
                content=gzip.compress(payload),
                request=request,
            )

        result = await CrossrefDiscoveryCollector(
            transport=httpx.MockTransport(handler)
        ).search(QUERY)
        self.assertEqual(result.records, [])

    async def test_real_shape_fixture_keeps_indexed_and_future_publication_distinct(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/crossref_ieee_indexed_record.json").read_text()
        )

        def handler(request):
            return httpx.Response(
                200, headers={"Content-Type": "application/json"},
                json=fixture, request=request,
            )

        result = await CrossrefDiscoveryCollector(
            transport=httpx.MockTransport(handler)
        ).search(QUERY)
        facts = result.records[0].source_facts
        self.assertEqual(facts["doi"], "10.1109/lra.2026.3713731")
        self.assertEqual(facts["published"], "2026-10")
        self.assertEqual(facts["indexed"], "2026-08-19T05:28:01Z")
        self.assertFalse(facts["has_abstract"])

    async def test_route_and_idempotent_schema_migration(self):
        body = CrossrefDiscoveryRequest(**QUERY)
        expected = ({"id": 1}, [{"id": 2}])
        with patch("api.routes.discoveries.discover_crossref", new=AsyncMock(return_value=expected)):
            result = await create_crossref_discovery(body)
        self.assertEqual(result["job"], expected[0])
        conn = self.connect()
        ensure_material_schema(conn)
        ensure_material_schema(conn)
        self.assertIn("canonical_id", {row[1] for row in conn.execute("PRAGMA table_info(candidates)")})
        self.assertEqual(
            conn.execute(
                "SELECT value FROM schema_meta WHERE key='material_schema_version'"
            ).fetchone()[0],
            str(MATERIAL_SCHEMA_VERSION),
        )
        self.assertEqual(normalize_doi("HTTPS://DOI.ORG/10.1109/ABC"), "10.1109/abc")
        conn.close()

    async def test_request_model_validates_each_search_intent(self):
        CrossrefDiscoveryRequest(**QUERY)
        CrossrefDiscoveryRequest(**{
            **QUERY, "intent": "journal_latest", "query": None,
            "container_title": "IEEE Access",
        })
        CrossrefDiscoveryRequest(**{
            **QUERY, "intent": "exact", "query": "10.1109/example",
            "date_from": None, "date_to": None,
        })
        with self.assertRaisesRegex(ValueError, "期刊名称或 ISSN"):
            CrossrefDiscoveryRequest(**{
                **QUERY, "intent": "journal_latest", "query": None,
                "container_title": None, "issn": None,
            })


if __name__ == "__main__":
    unittest.main()
