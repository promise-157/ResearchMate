import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from processors.ai_provider import AIResponse
from services import candidate_insights
from storage import candidates as candidate_repository
from storage.workspace import _init_workspace_db


class FakeBriefProvider:
    def __init__(self, content):
        self.content = content
        self.inputs = []

    async def review(self, selected_input):
        self.inputs.append(selected_input)
        return AIResponse(
            content=json.dumps(self.content, ensure_ascii=False),
            provider_model="fixture-model", input_tokens=12, output_tokens=8,
            duration_ms=5, request_id="fixture-request", finish_reason="stop",
        )


class CandidateInsightTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "workspace.db")
        _init_workspace_db(self.db_path)
        self.connection_patch = patch(
            "services.candidate_insights.get_active_connection", side_effect=self.connect
        )
        self.connection_patch.start()

    def tearDown(self):
        self.connection_patch.stop()
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def candidate(self, title, *, published, seen=False, abstract=""):
        conn = self.connect()
        job = candidate_repository.create_job(conn, collector="crossref_ieee", query={})
        value = candidate_repository.create_candidate(conn, {
            "job_id": job["id"], "title": title, "content_text": title,
            "summary": abstract, "source_kind": "crossref_ieee",
            "source_url": "https://doi.org/10.1109/fixture", "content_hash": title,
            "canonical_id": f"doi:10.1109/{job['id']}",
            "source_facts": {
                "doi": f"10.1109/{job['id']}", "published": published,
                "container_title": "IEEE Robotics and Automation Letters",
                "authors": ["Alice"], "existing_candidate_id": 99 if seen else None,
            },
        })
        conn.commit()
        conn.close()
        return value["id"]

    def configured(self, section, key):
        return {("ai", "api_type"): "openai", ("ai", "model"): "fixture-model",
                ("ai", "api_key"): "fixture-key"}.get((section, key), "")

    async def test_local_ranking_is_stable_explainable_and_offline(self):
        strong = self.candidate(
            "Hermite spline trajectory planning", published="2026-08-20", abstract="Evidence"
        )
        weak = self.candidate("Unrelated legacy work", published="2020-01-01", seen=True)
        ranking = candidate_insights.rank_candidates(
            [weak, strong], focus="Hermite spline", preferred_journal="Robotics",
            today=date(2026, 8, 30),
        )
        self.assertEqual([row["candidate_id"] for row in ranking], [strong, weak])
        self.assertGreater(ranking[0]["score"], ranking[1]["score"])
        self.assertIn("标题包含完整关注词 +45", ranking[0]["reasons"])
        self.assertIn("有可追溯摘要 +10", ranking[0]["reasons"])

    async def test_brief_is_bounded_audited_and_does_not_mutate_candidates(self):
        first = self.candidate("First", published="2026-08-20", abstract="A" * 3000)
        second = self.candidate("Second", published="2026-08-19", abstract="B")
        fake = FakeBriefProvider({
            "overview": "离线总体判断",
            "priorities": [{"candidate_id": first, "reason": "证据较完整"}],
            "caveats": "没有阅读全文",
        })
        conn = self.connect()
        before = conn.execute("SELECT source_facts_json, status FROM candidates ORDER BY id").fetchall()
        conn.close()
        with patch("services.candidate_insights.config_get", side_effect=self.configured):
            run = await candidate_insights.create_candidate_brief(
                [first, second], focus="robotics", provider_client=fake
            )
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["candidate_ids"], [first, second])
        self.assertEqual(len(fake.inputs[0][0]["abstract"]), candidate_insights.ABSTRACT_LIMIT)
        self.assertEqual(candidate_insights.list_candidate_briefs()[0]["result"]["overview"], "离线总体判断")
        conn = self.connect()
        after = conn.execute("SELECT source_facts_json, status FROM candidates ORDER BY id").fetchall()
        self.assertEqual([tuple(row) for row in before], [tuple(row) for row in after])
        conn.close()

    async def test_missing_config_and_out_of_scope_result_are_failed_audits(self):
        first = self.candidate("First", published="2026-08-20")
        second = self.candidate("Second", published="2026-08-19")
        with patch("services.candidate_insights.config_get", return_value=""):
            missing = await candidate_insights.create_candidate_brief([first, second])
        self.assertEqual(missing["status"], "failed")
        self.assertIn("尚未配置", missing["error_message"])
        fake = FakeBriefProvider({
            "overview": "bad", "priorities": [{"candidate_id": 999, "reason": "bad"}],
            "caveats": "bad",
        })
        with patch("services.candidate_insights.config_get", side_effect=self.configured):
            invalid = await candidate_insights.create_candidate_brief(
                [first, second], provider_client=fake
            )
        self.assertEqual(invalid["status"], "failed")
        self.assertIn("输入范围之外", invalid["error_message"])


if __name__ == "__main__":
    unittest.main()
