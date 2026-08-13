import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi import HTTPException

from api.routes.cart import (
    CartAnalyzeRequest,
    analyze_all_cart,
    analyze_cart_papers as analyze_cart_papers_route,
)
from processors.ai_provider import AIProviderError, AIResponse
from processors.paper_ai import validate_result
from services import paper_analysis
from storage.workspace import _init_workspace_db, _migrate_workspace_db, clear_workspace
from storage.workspace_schema import MATERIAL_SCHEMA_VERSION


def successful_response(
    *,
    innovation: str = "用离线证据改进方法",
    request_id: str = "req-paper-fixture",
) -> AIResponse:
    return AIResponse(
        content=json.dumps(
            {
                "has_code": True,
                "code_url": "https://example.com/fixture-code",
                "innovation": innovation,
                "technologies": ["Transformer", "离线评估"],
            },
            ensure_ascii=False,
        ),
        provider_model="deepseek-fixture-returned",
        input_tokens=47,
        output_tokens=19,
        duration_ms=86,
        request_id=request_id,
        finish_reason="stop",
    )


class FakePaperProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def analyze(self, selected_input):
        self.calls.append(selected_input)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class PaperAnalysisServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "papers.db")
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
        values = {
            "api_type": "deepseek",
            "api_key": "fixture-key-never-networked",
            "api_base_url": "https://fixture.invalid",
            "model": "deepseek-fixture-configured",
        }
        return values.get(key)

    def insert_paper(
        self,
        *,
        title="来源论文",
        abstract="来源摘要",
        in_cart=True,
        suffix="1",
    ):
        conn = self.connect()
        cursor = conn.execute(
            """INSERT INTO papers
               (task_id, source_id, title, authors, abstract, journal_name,
                publish_year, arxiv_id, paper_url, has_code, code_url,
                auto_keywords, auto_technologies, ai_innovation,
                ai_technologies, ai_code_url, ai_analyzed, in_cart,
                cart_ai_analyzed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                None,
                17,
                title,
                json.dumps(["Alice", "Bob"], ensure_ascii=False),
                abstract,
                "cs.AI",
                2026,
                f"fixture.{suffix}",
                f"https://arxiv.org/abs/fixture.{suffix}",
                1,
                "https://source.example/code",
                json.dumps(["source-keyword"], ensure_ascii=False),
                json.dumps(["source-technology"], ensure_ascii=False),
                "旧创新展示值",
                json.dumps(["旧 AI 技术"], ensure_ascii=False),
                "https://legacy.example/ai-code",
                1,
                int(in_cart),
                1,
            ),
        )
        conn.commit()
        paper_id = cursor.lastrowid
        conn.close()
        return paper_id

    def run_count(self):
        conn = self.connect()
        count = conn.execute("SELECT COUNT(*) FROM paper_ai_runs").fetchone()[0]
        conn.close()
        return count

    async def test_success_audits_metadata_without_mutating_any_paper_field(self):
        paper_id = self.insert_paper()
        conn = self.connect()
        before = dict(
            conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        )
        conn.close()
        fake = FakePaperProvider([successful_response()])

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            summary = await paper_analysis.analyze_cart_papers(
                [paper_id], provider_client=fake
            )
            restored = paper_analysis.list_cart_papers()

        self.assertEqual(summary["ok"], True)
        self.assertEqual(summary["overall_status"], "succeeded")
        self.assertEqual(summary["requested"], 1)
        self.assertEqual(summary["succeeded"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["analyzed"], 1)
        self.assertEqual(summary["message"], "已完成 1/1 篇论文分析")
        self.assertEqual(len(summary["runs"]), 1)

        run = summary["runs"][0]
        self.assertEqual(run["paper_id"], paper_id)
        self.assertEqual(run["paper_ids"], [paper_id])
        self.assertEqual(run["input_scope"], ["title", "abstract"])
        self.assertRegex(run["input_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(run["processor"], "paper_ai")
        self.assertEqual(run["processor_version"], "1")
        self.assertEqual(run["run_kind"], "paper_analysis")
        self.assertEqual(run["prompt_version"], "paper-analysis-v1")
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["provider"], "deepseek")
        self.assertEqual(run["model"], "deepseek-fixture-configured")
        self.assertEqual(run["provider_model"], "deepseek-fixture-returned")
        self.assertEqual(run["input_tokens"], 47)
        self.assertEqual(run["output_tokens"], 19)
        self.assertEqual(run["duration_ms"], 86)
        self.assertEqual(run["request_id"], "req-paper-fixture")
        self.assertEqual(
            run["result"],
            {
                "has_code": True,
                "code_url": "https://example.com/fixture-code",
                "innovation": "用离线证据改进方法",
                "technologies": ["Transformer", "离线评估"],
            },
        )
        self.assertIsNone(run["error_message"])
        self.assertIsNotNone(run["created_at"])
        self.assertIsNotNone(run["completed_at"])

        self.assertEqual(fake.calls, [{"title": "来源论文", "abstract": "来源摘要"}])
        self.assertEqual(restored[0]["analysis_runs"][0]["id"], run["id"])
        conn = self.connect()
        after = dict(
            conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        )
        conn.close()
        self.assertEqual(after, before)

    async def test_partial_failure_is_not_reported_as_batch_success_and_continues(self):
        failed_id = self.insert_paper(title="失败论文", suffix="partial-1")
        succeeded_id = self.insert_paper(title="成功论文", suffix="partial-2")
        fake = FakePaperProvider(
            [
                AIProviderError("timeout", "模型请求超时，请稍后重试或缩小输入范围"),
                successful_response(request_id="req-after-failure"),
            ]
        )

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            summary = await paper_analysis.analyze_cart_papers(
                [failed_id, succeeded_id], provider_client=fake
            )

        self.assertFalse(summary["ok"])
        self.assertEqual(summary["overall_status"], "partial")
        self.assertEqual(summary["requested"], 2)
        self.assertEqual(summary["succeeded"], 1)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["analyzed"], 1)
        self.assertTrue(summary["message"])
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual(len(summary["runs"]), 2)
        by_paper = {run["paper_id"]: run for run in summary["runs"]}
        self.assertEqual(by_paper[failed_id]["status"], "failed")
        self.assertIn("超时", by_paper[failed_id]["error_message"])
        self.assertIsNone(by_paper[failed_id]["result"])
        self.assertIsNotNone(by_paper[failed_id]["completed_at"])
        self.assertEqual(by_paper[succeeded_id]["status"], "succeeded")
        self.assertEqual(by_paper[succeeded_id]["request_id"], "req-after-failure")

    async def test_invalid_model_result_is_failed_with_actionable_validation_error(self):
        paper_id = self.insert_paper(suffix="invalid-result")
        fake = FakePaperProvider(
            [
                AIResponse(
                    content=json.dumps(
                        {
                            "has_code": "yes",
                            "code_url": None,
                            "innovation": "类型不严格",
                            "technologies": [],
                        },
                        ensure_ascii=False,
                    ),
                    provider_model="fixture-returned",
                    input_tokens=5,
                    output_tokens=3,
                    duration_ms=8,
                    request_id="req-invalid",
                    finish_reason="stop",
                )
            ]
        )

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            summary = await paper_analysis.analyze_cart_papers(
                [paper_id], provider_client=fake
            )

        self.assertFalse(summary["ok"])
        self.assertEqual(summary["overall_status"], "failed")
        self.assertEqual(summary["succeeded"], 0)
        self.assertEqual(summary["failed"], 1)
        self.assertEqual(summary["analyzed"], 0)
        run = summary["runs"][0]
        self.assertEqual(run["status"], "failed")
        self.assertIn("结构校验", run["error_message"])
        self.assertIsNone(run["result"])
        self.assertEqual(run["provider_model"], "fixture-returned")
        self.assertEqual(run["request_id"], "req-invalid")

    async def test_unknown_exception_is_redacted_from_summary_and_persisted_run(self):
        private_abstract = "PRIVATE-ABSTRACT-DO-NOT-LEAK"
        paper_id = self.insert_paper(
            title="PRIVATE-TITLE-DO-NOT-LEAK",
            abstract=private_abstract,
            suffix="redaction",
        )
        fake = FakePaperProvider(
            [
                RuntimeError(
                    "fixture-key-never-networked PRIVATE-ABSTRACT-DO-NOT-LEAK "
                    "raw provider response"
                )
            ]
        )

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            summary = await paper_analysis.analyze_cart_papers(
                [paper_id], provider_client=fake
            )

        self.assertEqual(summary["overall_status"], "failed")
        persisted_error = summary["runs"][0]["error_message"]
        combined = f"{summary['message']} {persisted_error}"
        self.assertTrue(persisted_error)
        self.assertNotIn("fixture-key-never-networked", combined)
        self.assertNotIn("PRIVATE-ABSTRACT-DO-NOT-LEAK", combined)
        self.assertNotIn("PRIVATE-TITLE-DO-NOT-LEAK", combined)
        self.assertNotIn("raw provider response", combined)

    async def test_provider_value_error_is_redacted(self):
        paper_id = self.insert_paper(suffix="provider-value-error")
        fake = FakePaperProvider([ValueError("fixture-key private provider response")])
        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            summary = await paper_analysis.analyze_cart_papers(
                [paper_id], provider_client=fake
            )

        error = summary["runs"][0]["error_message"]
        self.assertEqual(error, "论文分析失败，请稍后重试")
        self.assertNotIn("fixture-key", error)

    async def test_missing_model_configuration_is_actionable_and_audited(self):
        paper_id = self.insert_paper(suffix="missing-config")
        fake = FakePaperProvider([successful_response()])

        def unconfigured(section, key=None):
            if section == "crawler":
                return 30
            return {"api_type": "deepseek", "api_key": "", "model": ""}.get(key)

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=unconfigured
        ):
            summary = await paper_analysis.analyze_cart_papers(
                [paper_id], provider_client=fake
            )

        self.assertFalse(summary["ok"])
        self.assertEqual(summary["overall_status"], "failed")
        self.assertIn("设置页", summary["runs"][0]["error_message"])
        self.assertEqual(fake.calls, [])
        self.assertEqual(self.run_count(), 1)

    async def test_title_and_abstract_are_bounded_before_provider_call(self):
        title = "T" * 350
        abstract = "A" * 3_200
        paper_id = self.insert_paper(
            title=title, abstract=abstract, suffix="bounded-input"
        )
        fake = FakePaperProvider([successful_response()])

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            summary = await paper_analysis.analyze_cart_papers(
                [paper_id], provider_client=fake
            )

        self.assertTrue(summary["ok"])
        self.assertEqual(fake.calls[0]["title"], title[:300])
        self.assertEqual(fake.calls[0]["abstract"], abstract[:3_000])
        self.assertEqual(set(fake.calls[0]), {"title", "abstract"})
        self.assertEqual(summary["runs"][0]["input_scope"], ["title", "abstract"])

    async def test_exactly_twenty_distinct_cart_papers_are_allowed(self):
        paper_ids = [
            self.insert_paper(title=f"论文 {index}", suffix=f"limit-{index}")
            for index in range(20)
        ]
        fake = FakePaperProvider(
            [successful_response(request_id=f"req-{index}") for index in range(20)]
        )

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            summary = await paper_analysis.analyze_cart_papers(
                paper_ids, provider_client=fake
            )

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["requested"], 20)
        self.assertEqual(summary["succeeded"], 20)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(self.run_count(), 20)

    async def test_invalid_selections_are_rejected_before_any_run_or_provider_call(self):
        cart_id = self.insert_paper(suffix="valid-cart")
        non_cart_id = self.insert_paper(in_cart=False, suffix="not-cart")
        extra_ids = [
            self.insert_paper(title=f"额外论文 {index}", suffix=f"extra-{index}")
            for index in range(20)
        ]
        fake = FakePaperProvider([successful_response()] * 30)
        invalid_selections = (
            [],
            [0],
            [True],
            [cart_id, cart_id],
            [999_999],
            [non_cart_id],
            [cart_id, *extra_ids],
        )

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            for selection in invalid_selections:
                with self.subTest(selection=selection), self.assertRaises(ValueError) as ctx:
                    await paper_analysis.analyze_cart_papers(
                        selection, provider_client=fake
                    )
                self.assertTrue(str(ctx.exception))

        self.assertEqual(fake.calls, [])
        self.assertEqual(self.run_count(), 0)

    async def test_runs_are_isolated_even_when_workspaces_reuse_paper_ids(self):
        first_id = self.insert_paper(title="第一工作区", suffix="workspace-one")
        second_path = os.path.join(self.temp_dir.name, "second.db")
        _init_workspace_db(second_path)

        def second_connect():
            conn = sqlite3.connect(second_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        conn = second_connect()
        second_id = conn.execute(
            """INSERT INTO papers
               (title, authors, abstract, arxiv_id, paper_url, in_cart)
               VALUES (?, '[]', ?, ?, ?, 1)""",
            (
                "第二工作区",
                "隔离摘要",
                "fixture.workspace-two",
                "https://arxiv.org/abs/fixture.workspace-two",
            ),
        ).lastrowid
        conn.commit()
        conn.close()
        self.assertEqual(first_id, second_id)

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            await paper_analysis.analyze_cart_papers(
                [first_id], provider_client=FakePaperProvider([successful_response()])
            )

        with patch(
            "services.paper_analysis.get_active_connection", side_effect=second_connect
        ):
            second_cart = paper_analysis.list_cart_papers()
        self.assertEqual(second_cart[0]["title"], "第二工作区")
        self.assertEqual(second_cart[0]["analysis_runs"], [])
        conn = second_connect()
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM paper_ai_runs").fetchone()[0], 0
        )
        conn.close()

    async def test_clear_workspace_removes_paper_analysis_runs(self):
        paper_id = self.insert_paper(suffix="clear")
        with patch(
            "services.paper_analysis.get_active_connection", side_effect=self.connect
        ), patch(
            "services.paper_analysis.config_get", side_effect=self.configured
        ):
            await paper_analysis.analyze_cart_papers(
                [paper_id], provider_client=FakePaperProvider([successful_response()])
            )
        self.assertEqual(self.run_count(), 1)

        with patch(
            "storage.workspace.get_active_connection", side_effect=self.connect
        ), patch("storage.workspace.get_active_path", return_value=self.db_path):
            clear_workspace()

        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM paper_ai_runs").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0], 0)
        conn.close()


class PaperAnalysisValidationTests(unittest.TestCase):
    def test_strict_structure_url_and_types_are_rejected(self):
        invalid_results = {
            "missing required field": {
                "has_code": False,
                "code_url": None,
                "technologies": [],
            },
            "extra field": {
                "has_code": False,
                "code_url": None,
                "innovation": "有效创新",
                "technologies": [],
                "unexpected": "must fail",
            },
            "credential url": {
                "has_code": True,
                "code_url": "https://user:password@example.com/code",
                "innovation": "有效创新",
                "technologies": [],
            },
            "non http url": {
                "has_code": True,
                "code_url": "file:///tmp/private",
                "innovation": "有效创新",
                "technologies": [],
            },
            "url contradicts flag": {
                "has_code": False,
                "code_url": "https://example.com/code",
                "innovation": "有效创新",
                "technologies": [],
            },
            "coerced bool": {
                "has_code": 1,
                "code_url": None,
                "innovation": "有效创新",
                "technologies": [],
            },
            "non string technology": {
                "has_code": False,
                "code_url": None,
                "innovation": "有效创新",
                "technologies": [7],
            },
        }
        for label, value in invalid_results.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                validate_result(json.dumps(value, ensure_ascii=False))

    def test_valid_result_is_normalized_without_changing_types(self):
        result = validate_result(
            json.dumps(
                {
                    "has_code": True,
                    "code_url": " https://example.com/code ",
                    "innovation": " 核心创新 ",
                    "technologies": [" Transformer ", "RAG"],
                },
                ensure_ascii=False,
            )
        )
        self.assertEqual(
            result,
            {
                "has_code": True,
                "code_url": "https://example.com/code",
                "innovation": "核心创新",
                "technologies": ["Transformer", "RAG"],
            },
        )


class PaperAnalysisMigrationTests(unittest.TestCase):
    def test_v9_workspace_migrates_idempotently_without_losing_paper_ai_or_chat(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "legacy-v9.db")
            _init_workspace_db(db_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            item_id = conn.execute(
                """INSERT INTO items
                   (item_type, title, content_text, source_kind, content_hash)
                   VALUES ('paper', '旧资料', '旧正文', 'text_import', 'legacy-hash')"""
            ).lastrowid
            paper_id = conn.execute(
                """INSERT INTO papers
                   (title, authors, abstract, arxiv_id, paper_url, has_code,
                    code_url, ai_innovation, ai_technologies, ai_code_url,
                    ai_analyzed, cart_ai_analyzed, item_id, in_cart)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    "旧论文",
                    '["Legacy Author"]',
                    "旧来源摘要",
                    "legacy.1",
                    "https://arxiv.org/abs/legacy.1",
                    1,
                    "https://source.example/legacy-code",
                    "旧 AI 创新",
                    '["旧技术"]',
                    "https://legacy.example/ai-code",
                    1,
                    1,
                    item_id,
                ),
            ).lastrowid
            extraction_id = conn.execute(
                """INSERT INTO extraction_runs
                   (item_id, processor, processor_version, run_kind, status,
                    input_hash, result_json, provider, model, prompt_version)
                   VALUES (?, 'material_ai', '2', 'extract', 'succeeded',
                           'legacy-run-hash', ?, 'deepseek', 'legacy-model', 'legacy-v1')""",
                (item_id, '{"summary":"旧通用 AI 结果"}'),
            ).lastrowid
            session_id = conn.execute(
                "INSERT INTO chat_sessions(title) VALUES ('旧会话')"
            ).lastrowid
            turn_id = conn.execute(
                """INSERT INTO chat_turns
                   (session_id, user_message, assistant_message, status,
                    paper_ids_json, input_scope_json, history_turn_ids_json,
                    provider, model, provider_model, request_id, prompt_version,
                    completed_at)
                   VALUES (?, '旧问题', '旧回答', 'succeeded', ?, ?, '[]',
                           'deepseek', 'legacy-model', 'legacy-returned',
                           'legacy-request', 'paper-chat-v1', datetime('now'))""",
                (session_id, json.dumps([paper_id]), json.dumps(["paper_metadata"])),
            ).lastrowid
            conn.execute("DROP TABLE paper_ai_runs")
            conn.execute(
                "UPDATE schema_meta SET value = '9' WHERE key = 'material_schema_version'"
            )
            conn.commit()

            _migrate_workspace_db(conn)
            _migrate_workspace_db(conn)

            self.assertEqual(
                conn.execute(
                    "SELECT value FROM schema_meta WHERE key = 'material_schema_version'"
                ).fetchone()[0],
                str(MATERIAL_SCHEMA_VERSION),
            )
            paper = conn.execute(
                """SELECT title, abstract, has_code, code_url, ai_innovation,
                          ai_technologies, ai_code_url, ai_analyzed,
                          cart_ai_analyzed, item_id
                   FROM papers WHERE id = ?""",
                (paper_id,),
            ).fetchone()
            self.assertEqual(
                tuple(paper),
                (
                    "旧论文",
                    "旧来源摘要",
                    1,
                    "https://source.example/legacy-code",
                    "旧 AI 创新",
                    '["旧技术"]',
                    "https://legacy.example/ai-code",
                    1,
                    1,
                    item_id,
                ),
            )
            extraction = conn.execute(
                "SELECT status, result_json FROM extraction_runs WHERE id = ?",
                (extraction_id,),
            ).fetchone()
            self.assertEqual(tuple(extraction), ("succeeded", '{"summary":"旧通用 AI 结果"}'))
            turn = conn.execute(
                """SELECT user_message, assistant_message, status, request_id
                   FROM chat_turns WHERE id = ?""",
                (turn_id,),
            ).fetchone()
            self.assertEqual(
                tuple(turn), ("旧问题", "旧回答", "succeeded", "legacy-request")
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM paper_ai_runs").fetchone()[0], 0
            )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(paper_ai_runs)")
            }
            self.assertTrue(
                {
                    "paper_id",
                    "paper_ids_json",
                    "input_scope_json",
                    "input_hash",
                    "processor",
                    "processor_version",
                    "run_kind",
                    "status",
                    "provider",
                    "model",
                    "provider_model",
                    "input_tokens",
                    "output_tokens",
                    "duration_ms",
                    "request_id",
                    "prompt_version",
                    "result_json",
                    "error_message",
                    "created_at",
                    "completed_at",
                }.issubset(columns)
            )
            conn.close()


class PaperAnalysisRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_and_all_routes_return_service_summary_shape(self):
        selected_summary = {
            "ok": False,
            "overall_status": "partial",
            "requested": 2,
            "succeeded": 1,
            "failed": 1,
            "analyzed": 1,
            "runs": [
                {"paper_id": 3, "status": "succeeded"},
                {"paper_id": 4, "status": "failed"},
            ],
            "message": "1 篇分析失败",
        }
        all_summary = {
            **selected_summary,
            "overall_status": "succeeded",
            "ok": True,
            "requested": 2,
            "succeeded": 2,
            "failed": 0,
            "analyzed": 2,
            "message": "已完成 2/2 篇论文分析",
        }
        analyze_mock = AsyncMock(side_effect=[selected_summary, all_summary])
        with patch(
            "api.routes.cart.paper_analysis_service.analyze_cart_papers",
            analyze_mock,
        ), patch(
            "api.routes.cart.paper_analysis_service.list_cart_paper_ids",
            return_value=[8, 9],
        ):
            selected = await analyze_cart_papers_route(
                CartAnalyzeRequest(paper_ids=[3, 4])
            )
            all_result = await analyze_all_cart()

        self.assertEqual(selected, selected_summary)
        self.assertEqual(all_result, all_summary)
        self.assertEqual(analyze_mock.await_args_list[0].args, ([3, 4],))
        self.assertEqual(analyze_mock.await_args_list[1].args, ([8, 9],))

    async def test_service_validation_errors_are_mapped_to_422(self):
        with patch(
            "api.routes.cart.paper_analysis_service.analyze_cart_papers",
            new=AsyncMock(side_effect=ValueError("论文必须属于当前购物车")),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await analyze_cart_papers_route(CartAnalyzeRequest(paper_ids=[7]))
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "论文必须属于当前购物车")


if __name__ == "__main__":
    unittest.main()
