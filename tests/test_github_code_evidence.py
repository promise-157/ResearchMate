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

from crawlers.github_code_evidence import (
    GITHUB_SEARCH_URL, GitHubCodeEvidenceCollector, GitHubCodeEvidenceResult,
)
from api.routes.discoveries import create_code_evidence
from services.discoveries import check_code_evidence
from storage import candidates as repository
from storage.models import CodeEvidenceRequest
from storage.workspace import _init_workspace_db


def repo(full_name, *, stars=3):
    return {
        "full_name": full_name, "html_url": f"https://github.com/{full_name}",
        "description": "Public implementation", "stargazers_count": stars,
        "updated_at": "2026-08-29T00:00:00Z", "archived": False,
        "license": {"spdx_id": "MIT"},
    }


class FixtureCollector:
    async def check(self, papers):
        first, second = papers
        now = "2026-08-30T00:00:00+00:00"
        return GitHubCodeEvidenceResult({first["candidate_id"]: {
            "source_record_id": f"candidate:{first['candidate_id']}",
            "source_url": "https://github.com/search", "query": first["title"],
            "declared_repository_count": 0, "checked_repository_count": 3,
            "repositories": [{
                "repository_url": "https://github.com/lab/official-code",
                "full_name": "lab/official-code", "description": "Implementation",
                "stars": 8, "updated_at": "2026-08-29T00:00:00Z",
                "archived": False, "license_spdx": "MIT",
                "level": "strong_identifier", "matched_fields": ["doi"],
            }], "fetched_at": now,
        }}, {second["candidate_id"]: "GitHub API 已限流"})


class GitHubCodeEvidenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "workspace.db")
        _init_workspace_db(self.db_path)
        self.patch = patch("services.discoveries.get_active_connection", side_effect=self.connect)
        self.patch.start()
        conn = self.connect()
        job = repository.create_job(conn, collector="crossref_ieee", query={"query": "code"})
        self.ids = []
        for index in range(2):
            doi = f"10.1109/example.2026.{index + 1}"
            candidate = repository.create_candidate(conn, {
                "job_id": job["id"], "title": f"Recent Paper {index + 1}",
                "content_text": f"Recent Paper {index + 1}", "summary": "",
                "source_kind": "crossref_ieee", "source_url": f"https://doi.org/{doi}",
                "canonical_id": f"doi:{doi}", "content_hash": f"hash-{index}",
                "source_facts": {"doi": doi, "authors": ["Alice Smith"]},
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

    async def test_declared_repository_is_not_reclassified_by_readme(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path.endswith("/readme"):
                return httpx.Response(200, text="unrelated readme", request=request)
            return httpx.Response(200, headers={"Content-Type": "application/json"},
                                  json=repo("lab/declared"), request=request)

        result = await GitHubCodeEvidenceCollector(
            transport=httpx.MockTransport(handler)
        ).check([{
            "candidate_id": 7, "title": "Paper", "doi": "10.1109/test.1",
            "arxiv_id": None, "authors": ["Alice"],
            "evidence_texts": ["Code: https://github.com/lab/declared."],
        }])
        record = result.records_by_candidate_id[7]
        self.assertEqual(record["repositories"][0]["level"], "paper_declared")
        self.assertEqual(len(requests), 2)
        self.assertNotEqual(str(requests[0].url.copy_with(query=None)), GITHUB_SEARCH_URL)

    async def test_search_checks_only_three_readmes_and_filters_weak_matches(self):
        requests = []
        title = "A Distinctive Recent Robotics Paper"

        def handler(request):
            requests.append(request)
            if request.url.path == "/search/repositories":
                return httpx.Response(200, headers={"Content-Type": "application/json"},
                                      json={"items": [repo("lab/doi"), repo("user/title"), repo("noise/other")]}, request=request)
            readmes = {
                "/repos/lab/doi/readme": "Paper DOI 10.1109/example.2026.1",
                "/repos/user/title/readme": f"Unofficial implementation of {title} by Alice Smith",
                "/repos/noise/other/readme": "A different project",
            }
            return httpx.Response(200, text=readmes[request.url.path], request=request)

        result = await GitHubCodeEvidenceCollector(
            transport=httpx.MockTransport(handler)
        ).check([{
            "candidate_id": 8, "title": title, "doi": "10.1109/example.2026.1",
            "arxiv_id": "2608.12345v1", "authors": ["Alice Smith"],
            "evidence_texts": [],
        }])
        repositories = result.records_by_candidate_id[8]["repositories"]
        self.assertEqual(len(requests), 4)
        self.assertEqual([item["level"] for item in repositories], [
            "strong_identifier", "title_author_match",
        ])
        self.assertNotIn("readme_content", json.dumps(result.records_by_candidate_id[8]).lower())

    async def test_method_acronym_is_used_for_one_search_and_declared_404_is_retained(self):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(404, request=request)

        result = await GitHubCodeEvidenceCollector(
            transport=httpx.MockTransport(handler)
        ).check([{
            "candidate_id": 9, "title": "MIGHTY: A Long Paper Title",
            "doi": "10.1109/example", "arxiv_id": None, "authors": [],
            "evidence_texts": ["Code https://github.com/lab/removed"],
        }])
        evidence = result.records_by_candidate_id[9]["repositories"][0]
        self.assertFalse(evidence["available"])
        self.assertEqual(evidence["level"], "paper_declared")
        self.assertEqual(len(requests), 1)
        self.assertEqual(
            GitHubCodeEvidenceCollector._search_query({
                "title": "MIGHTY: A Long Paper Title", "doi": None,
                "arxiv_id": None,
            }),
            "MIGHTY a long paper title in:readme",
        )

    async def test_service_persists_found_and_independent_failure_without_mutation(self):
        job, candidates = await check_code_evidence(self.ids, collector=FixtureCollector())
        self.assertEqual(job["result"], {
            "requested_count": 2, "succeeded_count": 1, "failed_count": 1,
            "found_count": 1, "not_found_count": 0, "partial": True,
        })
        self.assertEqual(candidates[0]["title"], "Recent Paper 1")
        self.assertEqual(candidates[0]["status"], "pending")
        records = {candidate["id"]: candidate["source_records"][0] for candidate in candidates}
        self.assertEqual(records[self.ids[0]]["facts"]["repositories"][0]["level"], "strong_identifier")
        self.assertEqual(records[self.ids[1]]["status"], "failed")
        self.assertIn("限流", records[self.ids[1]]["error_message"])
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
        conn.close()

    async def test_validation_precedes_job_and_transport(self):
        with self.assertRaises(ValueError):
            CodeEvidenceRequest(candidate_ids=[1, 1])
        with self.assertRaisesRegex(ValueError, "重复"):
            await check_code_evidence([self.ids[0], self.ids[0]], collector=FixtureCollector())

    async def test_route_preserves_confirmed_candidate_ids(self):
        service = AsyncMock(return_value=({"id": 8}, [{"id": self.ids[0]}]))
        body = CodeEvidenceRequest(candidate_ids=[self.ids[0]])
        with patch("api.routes.discoveries.check_code_evidence", service):
            response = await create_code_evidence(body)
        service.assert_awaited_once_with([self.ids[0]])
        self.assertEqual(response["candidates"], [{"id": self.ids[0]}])


if __name__ == "__main__":
    unittest.main()
