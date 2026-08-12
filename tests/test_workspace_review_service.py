import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from processors.ai_provider import AIProviderError, AIResponse
from processors.workspace_review import validate_result
from services import workspace_review
from storage.workspace import _init_workspace_db
from api.routes.workspace_reviews import (
    WorkspaceReviewRequest,
    create_workspace_review as create_workspace_review_route,
    list_workspace_reviews as list_workspace_reviews_route,
)
from fastapi import HTTPException


class FakeReviewProvider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def review(self, selected_input):
        self.calls.append(selected_input)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class WorkspaceReviewServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "workspace.db")
        _init_workspace_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def configured(section, key=None):
        if section == "crawler":
            return 30
        return {
            "api_type": "deepseek",
            "api_key": "offline-fixture-key",
            "api_base_url": "https://fixture.invalid",
            "model": "fixture-configured-model",
        }.get(key)

    def insert_paper(self, suffix, *, title=None, abstract=None):
        conn = self.connect()
        cursor = conn.execute(
            """INSERT INTO papers
               (title, authors, abstract, journal_name, publish_year, arxiv_id,
                paper_url, has_code, code_url, auto_keywords, in_cart)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title or f"来源标题 {suffix}",
                json.dumps([f"Author {suffix}"]),
                abstract or f"来源摘要 {suffix}",
                "fixture",
                2026,
                f"fixture.{suffix}",
                f"https://example.test/{suffix}",
                1,
                f"https://example.test/code/{suffix}",
                json.dumps(["source-fact"]),
                0,
            ),
        )
        conn.commit()
        paper_id = cursor.lastrowid
        conn.close()
        return paper_id

    def successful_response(self, paper_ids):
        return AIResponse(
            content=json.dumps(
                {
                    "hot_topics": "离线热门方向",
                    "recommendations": [
                        {"paper_id": paper_ids[0], "reason": "证据完整"}
                    ],
                    "tech_trends": "离线技术趋势",
                },
                ensure_ascii=False,
            ),
            provider_model="fixture-returned-model",
            input_tokens=123,
            output_tokens=45,
            duration_ms=67,
            request_id="req-review-fixture",
            finish_reason="stop",
        )

    async def test_success_is_one_audited_run_and_never_mutates_source_or_legacy(self):
        first = self.insert_paper(
            "one",
            title="T" * (workspace_review.TITLE_LIMIT + 20),
            abstract="A" * (workspace_review.ABSTRACT_LIMIT + 20),
        )
        second = self.insert_paper("two")
        conn = self.connect()
        before = [
            dict(row)
            for row in conn.execute("SELECT * FROM papers ORDER BY id").fetchall()
        ]
        conn.close()
        fake = FakeReviewProvider(self.successful_response([first, second]))

        with patch(
            "services.workspace_review.get_active_connection",
            side_effect=self.connect,
        ), patch(
            "services.workspace_review.config_get", side_effect=self.configured
        ):
            run = await workspace_review.create_review(
                [second, first], provider_client=fake
            )
            history = workspace_review.list_review_history()

        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["run_kind"], "workspace_review")
        self.assertIsNone(run["paper_id"])
        self.assertEqual(run["paper_ids"], [second, first])
        self.assertEqual(run["input_scope"], ["title:300", "abstract:2000"])
        self.assertRegex(run["input_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(run["processor"], "workspace_review")
        self.assertEqual(run["processor_version"], "1")
        self.assertEqual(run["prompt_version"], "workspace-review-v1")
        self.assertEqual(run["provider"], "deepseek")
        self.assertEqual(run["model"], "fixture-configured-model")
        self.assertEqual(run["provider_model"], "fixture-returned-model")
        self.assertEqual(run["input_tokens"], 123)
        self.assertEqual(run["output_tokens"], 45)
        self.assertEqual(run["duration_ms"], 67)
        self.assertEqual(run["request_id"], "req-review-fixture")
        self.assertEqual(run["result"]["hot_topics"], "离线热门方向")
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual([entry["paper_id"] for entry in fake.calls[0]], [second, first])
        self.assertEqual(len(fake.calls[0][1]["title"]), workspace_review.TITLE_LIMIT)
        self.assertEqual(
            len(fake.calls[0][1]["abstract"]), workspace_review.ABSTRACT_LIMIT
        )
        self.assertEqual(history["runs"][0]["id"], run["id"])
        self.assertEqual(history["limits"]["min_papers"], 2)

        conn = self.connect()
        after = [
            dict(row)
            for row in conn.execute("SELECT * FROM papers ORDER BY id").fetchall()
        ]
        self.assertEqual(after, before)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM workspace_reviews").fetchone()[0], 0
        )
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM paper_ai_runs").fetchone()[0], 1
        )
        conn.close()

    async def test_all_ids_are_validated_before_run_or_provider_call(self):
        first = self.insert_paper("one")
        fake = FakeReviewProvider(self.successful_response([first]))
        with patch(
            "services.workspace_review.get_active_connection",
            side_effect=self.connect,
        ), patch(
            "services.workspace_review.config_get", side_effect=self.configured
        ):
            with self.assertRaisesRegex(ValueError, "不存在于当前工作区"):
                await workspace_review.create_review(
                    [first, 999_999], provider_client=fake
                )
        self.assertEqual(fake.calls, [])
        conn = self.connect()
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM paper_ai_runs").fetchone()[0], 0
        )
        conn.close()

    async def test_duplicate_and_count_boundaries_fail_before_provider(self):
        first = self.insert_paper("one")
        fake = FakeReviewProvider(self.successful_response([first]))
        with patch(
            "services.workspace_review.get_active_connection",
            side_effect=self.connect,
        ), patch(
            "services.workspace_review.config_get", side_effect=self.configured
        ):
            for selection, message in (
                ([first], "2–20"),
                ([first, first], "重复"),
            ):
                with self.subTest(selection=selection):
                    with self.assertRaisesRegex(ValueError, message):
                        await workspace_review.create_review(
                            selection, provider_client=fake
                        )
        self.assertEqual(fake.calls, [])

    async def test_provider_failure_is_sanitized_and_persisted(self):
        first = self.insert_paper("one")
        second = self.insert_paper("two")
        fake = FakeReviewProvider(
            AIProviderError("timeout", "模型请求超时，请稍后重试或缩小输入范围")
        )
        with patch(
            "services.workspace_review.get_active_connection",
            side_effect=self.connect,
        ), patch(
            "services.workspace_review.config_get", side_effect=self.configured
        ):
            run = await workspace_review.create_review(
                [first, second], provider_client=fake
            )
        self.assertEqual(run["status"], "failed")
        self.assertEqual(run["error_message"], "模型请求超时，请稍后重试或缩小输入范围")
        self.assertNotIn("offline-fixture-key", run["error_message"])
        self.assertIsNone(run["result"])

    def test_result_rejects_out_of_scope_and_legacy_is_read_only(self):
        with self.assertRaisesRegex(ValueError, "输入范围之外"):
            validate_result(
                json.dumps(
                    {
                        "hot_topics": "方向",
                        "recommendations": [{"paper_id": 99, "reason": "越界"}],
                        "tech_trends": "趋势",
                    },
                    ensure_ascii=False,
                ),
                [1, 2],
            )
        conn = self.connect()
        conn.execute(
            "INSERT INTO workspace_reviews (task_ids, ai_review) VALUES (?, ?)",
            (json.dumps([]), json.dumps({"hot_topics": "旧综述"}, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
        with patch(
            "services.workspace_review.get_active_connection",
            side_effect=self.connect,
        ):
            history = workspace_review.list_review_history()
        self.assertEqual(history["runs"], [])
        self.assertEqual(history["legacy_reviews"][0]["compatibility"], "legacy_read_only")
        self.assertEqual(history["legacy_reviews"][0]["review"]["hot_topics"], "旧综述")

    async def test_http_boundary_delegates_and_maps_validation_errors(self):
        succeeded = {"id": 8, "status": "succeeded", "paper_ids": [1, 2]}
        with patch(
            "api.routes.workspace_reviews.review_service.create_review",
            return_value=succeeded,
        ) as create_mock:
            response = await create_workspace_review_route(
                WorkspaceReviewRequest(paper_ids=[1, 2])
            )
        self.assertEqual(response, {"ok": True, "run": succeeded})
        create_mock.assert_awaited_once_with([1, 2])

        history = {"runs": [succeeded], "legacy_reviews": [], "limits": {}}
        with patch(
            "api.routes.workspace_reviews.review_service.list_review_history",
            return_value=history,
        ):
            self.assertEqual(list_workspace_reviews_route(), history)

        with patch(
            "api.routes.workspace_reviews.review_service.create_review",
            side_effect=ValueError("fixture 无效范围"),
        ):
            with self.assertRaises(HTTPException) as raised:
                await create_workspace_review_route(
                    WorkspaceReviewRequest(paper_ids=[1, 2])
                )
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail, "fixture 无效范围")


if __name__ == "__main__":
    unittest.main()
