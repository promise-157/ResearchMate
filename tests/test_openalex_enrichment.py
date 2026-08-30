import json
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

from crawlers.openalex_enrichment import OPENALEX_API_URL, OpenAlexEnrichmentCollector
from crawlers.arxiv_version_enrichment import (
    ArxivVersionCollector, ArxivVersionResult,
)
from crawlers.discovery_models import DiscoveredRecord
from crawlers.semantic_scholar_enrichment import (
    SEMANTIC_SCHOLAR_BATCH_URL, SemanticScholarEnrichmentCollector,
    SemanticScholarResult,
)
from api.routes.discoveries import create_openalex_enrichment
from services.discoveries import enrich_openalex
from storage import candidates as repository
from storage.models import OpenAlexEnrichmentRequest
from storage.workspace import _init_workspace_db


class FailingCollector:
    async def enrich(self, _dois):
        raise httpx.ConnectError("offline fixture failure")


class CountingCollector:
    calls = 0

    async def enrich(self, _dois):
        self.calls += 1
        raise AssertionError("validation must precede transport")


class FixtureArxivVersionCollector:
    async def match(self, candidates):
        candidate = candidates[-1]
        return ArxivVersionResult({candidate["candidate_id"]: {
            "source_record_id": "2511.14335v2", "arxiv_id": "2511.14335v2",
            "source_url": "https://arxiv.org/abs/2511.14335v2",
            "title": candidate["title"], "abstract": "Public preprint abstract",
            "authors": ["Author One"], "published": "2025-11-18T00:00:00Z",
            "fetched_at": "2026-08-30T00:00:00+00:00",
            "match_kind": "exact_title_author", "matched_authors": ["author one"],
            "formal_candidate_id": candidate["candidate_id"],
            "formal_doi": candidate["doi"],
        }})


class EmptyArxivVersionCollector:
    async def match(self, _candidates):
        return ArxivVersionResult({})


class FixtureSemanticScholarCollector:
    async def enrich(self, dois):
        doi = dois[-1]
        return SemanticScholarResult({doi: {
            "source_record_id": "semantic-paper-id",
            "source_url": "https://www.semanticscholar.org/paper/semantic-paper-id",
            "doi": doi, "title": "Independent Semantic Scholar title",
            "abstract": "Semantic Scholar fallback abstract",
            "authors": ["Author One"], "publication_date": "2026-08-01",
            "open_access_pdf_url": None, "open_access_status": "CLOSED",
            "fetched_at": "2026-08-30T00:00:00+00:00",
        }})


class FakeArxivDiscovery:
    def __init__(self, records):
        self.records = records
        self.queries = []

    async def search_query(self, query, limit):
        self.queries.append((query, limit))
        return self.records


class OpenAlexEnrichmentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patch = patch("services.discoveries.get_active_connection", side_effect=self.connect)
        self.patch.start()
        conn = self.connect()
        job = repository.create_job(conn, collector="crossref_ieee", query={"query": "fixture"})
        self.ids = []
        for index, doi in enumerate(("10.1109/lra.2026.3681187", "10.1109/lra.2026.3713731"), 1):
            candidate = repository.create_candidate(conn, {
                "job_id": job["id"], "title": f"Crossref title {index}",
                "content_text": f"Crossref body {index}", "summary": f"Crossref summary {index}",
                "source_kind": "crossref_ieee", "source_url": f"https://doi.org/{doi}",
                "canonical_id": f"doi:{doi}", "content_hash": f"hash-{index}",
                "source_facts": {"doi": doi, "collector": "crossref_ieee",
                                 "authors": ["Author One"]},
            })
            self.ids.append(candidate["id"])
        repository.complete_job(conn, job["id"], candidate_count=2)
        conn.close()

    def tearDown(self):
        self.patch.stop()
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def collector(self, requests, *, partial=True):
        fixture = json.loads((ROOT / "tests/fixtures/openalex_enrichment.json").read_text())
        if partial:
            fixture["results"] = fixture["results"][:1]

        def handler(request):
            requests.append(request)
            return httpx.Response(200, headers={"Content-Type": "application/json"}, json=fixture, request=request)

        return OpenAlexEnrichmentCollector(transport=httpx.MockTransport(handler))

    async def test_missing_abstract_remains_explicit_without_fabrication(self):
        result = await self.collector([], partial=False).enrich([
            "10.1109/lra.2026.3681187", "10.1109/lra.2026.3713731",
        ])
        second = result.records_by_doi["10.1109/lra.2026.3713731"]
        self.assertEqual(second["abstract"], "")
        self.assertFalse(second["is_open_access"])
        self.assertIsNone(second["best_open_url"])

    async def test_one_bounded_batch_parses_independent_facts_and_partial_result(self):
        requests = []
        job, candidates = await enrich_openalex(
            self.ids, collector=self.collector(requests),
            arxiv_collector=FixtureArxivVersionCollector(),
        )
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url.copy_with(query=None)), OPENALEX_API_URL)
        self.assertIn("10.1109/lra.2026.3681187", requests[0].url.params["filter"])
        self.assertEqual(job["result"], {
            "requested_count": 2, "succeeded_count": 1, "failed_count": 1,
            "partial": True, "arxiv_checked_count": 1,
            "arxiv_succeeded_count": 1, "arxiv_failed_count": 0,
            "semantic_checked_count": 0, "semantic_succeeded_count": 0,
            "semantic_failed_count": 0,
        })
        first, second = candidates
        self.assertEqual(first["title"], "Crossref title 1")
        self.assertEqual(first["summary"], "Crossref summary 1")
        record = first["source_records"][0]
        self.assertEqual(record["facts"]["abstract"], "Independent abstract evidence")
        self.assertEqual(record["facts"]["institutions"], ["Robotics Lab"])
        self.assertEqual(record["facts"]["cited_by_count"], 7)
        self.assertTrue(record["facts"]["is_open_access"])
        openalex_record = next(
            record for record in second["source_records"]
            if record["source_kind"] == "openalex"
        )
        self.assertEqual(openalex_record["status"], "failed")
        self.assertIn("未返回", openalex_record["error_message"])
        arxiv_record = next(
            record for record in second["source_records"]
            if record["source_kind"] == "arxiv_version"
        )
        self.assertEqual(arxiv_record["facts"]["abstract"], "Public preprint abstract")
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
        conn.close()

    async def test_missing_abstract_falls_back_by_doi_without_overwriting_candidate(self):
        job, candidates = await enrich_openalex(
            self.ids, collector=self.collector([], partial=False),
            arxiv_collector=EmptyArxivVersionCollector(),
            semantic_collector=FixtureSemanticScholarCollector(),
        )
        self.assertEqual(job["result"]["semantic_checked_count"], 1)
        self.assertEqual(job["result"]["semantic_succeeded_count"], 1)
        second = candidates[1]
        self.assertEqual(second["title"], "Crossref title 2")
        self.assertEqual(second["summary"], "Crossref summary 2")
        source_records = {record["source_kind"]: record for record in second["source_records"]}
        self.assertEqual(source_records["arxiv_version"]["status"], "failed")
        semantic = source_records["semantic_scholar"]
        self.assertEqual(semantic["facts"]["abstract"], "Semantic Scholar fallback abstract")
        self.assertEqual(semantic["facts"]["open_access_status"], "CLOSED")
        self.assertIsNone(semantic["facts"]["open_access_pdf_url"])

    async def test_validation_happens_before_job_and_transport(self):
        collector = CountingCollector()
        with self.assertRaisesRegex(ValueError, "重复"):
            await enrich_openalex([self.ids[0], self.ids[0]], collector=collector)
        conn = self.connect()
        before = conn.execute("SELECT COUNT(*) FROM collection_jobs").fetchone()[0]
        arxiv_job = repository.create_job(conn, collector="arxiv_api", query={})
        arxiv = repository.create_candidate(conn, {
            "job_id": arxiv_job["id"], "title": "arXiv", "content_text": "body",
            "summary": "", "source_kind": "arxiv_api", "source_url": "https://arxiv.org/abs/1",
            "content_hash": "arxiv", "source_facts": {"doi": "10.1/no"},
        })
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(ValueError, "不是可补全"):
            await enrich_openalex([arxiv["id"]], collector=collector)
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM collection_jobs").fetchone()[0], before + 1)
        conn.close()
        self.assertEqual(collector.calls, 0)
        with self.assertRaises(ValueError):
            OpenAlexEnrichmentRequest(candidate_ids=[1, 1])

    async def test_transport_failure_leaves_failed_job_without_fake_records(self):
        with self.assertRaisesRegex(RuntimeError, "offline fixture failure"):
            await enrich_openalex(
                self.ids, collector=FailingCollector(),
                arxiv_collector=EmptyArxivVersionCollector(),
            )
        conn = self.connect()
        job = repository.list_jobs(conn)[0]
        self.assertEqual(job["collector"], "openalex_enrichment")
        self.assertEqual(job["status"], "failed")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM candidate_source_records").fetchone()[0], 0)
        conn.close()

    async def test_route_preserves_exact_confirmed_candidate_ids(self):
        service = AsyncMock(return_value=(
            {"id": 9, "status": "succeeded", "result": {"succeeded_count": 1}},
            [{"id": self.ids[0]}],
        ))
        body = OpenAlexEnrichmentRequest(candidate_ids=[self.ids[0]])
        with patch("api.routes.discoveries.enrich_openalex", service):
            response = await create_openalex_enrichment(body)
        service.assert_awaited_once_with([self.ids[0]])
        self.assertEqual(response["candidates"], [{"id": self.ids[0]}])

    async def test_arxiv_version_requires_exact_title_and_shared_author(self):
        record = DiscoveredRecord(
            title="Formal Paper: A Result", content_text="Formal Paper: A Result\n\nAbstract",
            summary="Abstract", source_url="https://arxiv.org/abs/2607.00001v2",
            source_facts={"arxiv_id": "2607.00001v2", "authors": ["Alice Smith"],
                          "published": "2026-07-01T00:00:00Z", "fetched_at": "now"},
        )
        discovery = FakeArxivDiscovery([record])
        collector = ArxivVersionCollector(discovery=discovery)
        result = await collector.match([{
            "candidate_id": 7, "doi": "10.1109/test", "title": "Formal Paper — A Result",
            "authors": ["Alice Smith", "Bob Jones"],
        }])
        match = result.records_by_candidate_id[7]
        self.assertEqual(match["arxiv_id"], "2607.00001v2")
        self.assertEqual(match["match_kind"], "exact_title_author")
        self.assertIn('ti:"Formal Paper — A Result"', discovery.queries[0][0])

        discovery.records[0] = DiscoveredRecord(
            title=record.title, content_text=record.content_text, summary=record.summary,
            source_url=record.source_url,
            source_facts={**record.source_facts, "authors": ["Different Person"]},
        )
        unmatched = await collector.match([{
            "candidate_id": 8, "doi": "10.1109/test2", "title": record.title,
            "authors": ["Alice Smith"],
        }])
        self.assertEqual(unmatched.records_by_candidate_id, {})

    async def test_semantic_scholar_uses_one_doi_batch_and_keeps_closed_status(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(200, headers={"Content-Type": "application/json"}, json=[{
                "paperId": "abc123", "externalIds": {"DOI": "10.1109/example.2026.1"},
                "title": "Exact DOI record", "abstract": "Licensed source abstract",
                "authors": [{"name": "Alice Smith"}], "publicationDate": "2026-08-01",
                "openAccessPdf": {"url": "", "status": "CLOSED"},
            }, None], request=request)

        result = await SemanticScholarEnrichmentCollector(
            transport=httpx.MockTransport(handler)
        ).enrich(["10.1109/example.2026.1", "10.1109/example.2026.2"])
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url.copy_with(query=None)), SEMANTIC_SCHOLAR_BATCH_URL)
        self.assertEqual(
            json.loads(requests[0].content),
            {"ids": ["DOI:10.1109/example.2026.1", "DOI:10.1109/example.2026.2"]},
        )
        record = result.records_by_doi["10.1109/example.2026.1"]
        self.assertEqual(record["abstract"], "Licensed source abstract")
        self.assertEqual(record["open_access_status"], "CLOSED")
        self.assertIsNone(record["open_access_pdf_url"])


if __name__ == "__main__":
    unittest.main()
