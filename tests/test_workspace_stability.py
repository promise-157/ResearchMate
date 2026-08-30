import asyncio
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from processors.ai_provider import AIResponse
from services import paper_analysis
from storage import paper_ai_runs
from storage import assets
from storage import workspace


class BlockingPaperProvider:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def analyze(self, selected_input):
        self.started.set()
        await self.release.wait()
        return AIResponse(
            content=json.dumps({
                "has_code": False,
                "code_url": None,
                "innovation": "固定工作区连接",
                "technologies": ["SQLite"],
            }, ensure_ascii=False),
            provider_model="fixture-model",
            input_tokens=10,
            output_tokens=5,
            duration_ms=20,
            request_id="req-workspace-lease",
            finish_reason="stop",
        )


class WorkspaceStabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.active_patch = patch.object(workspace, "_active_db_path", None)
        self.root_patch = patch.object(workspace, "WORKSPACE_DIR", self.root)
        self.lease_patch = patch.object(workspace, "_workspace_leases", {})
        self.active_patch.start()
        self.root_patch.start()
        self.lease_patch.start()
        self.alpha = workspace.create_workspace("alpha")
        self.beta = workspace.create_workspace("beta")

    def tearDown(self):
        self.lease_patch.stop()
        self.root_patch.stop()
        self.active_patch.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def configured(section, key=None):
        if section == "crawler":
            return 30
        return {
            "api_type": "deepseek",
            "api_key": "fixture-key",
            "api_base_url": "https://fixture.invalid",
            "model": "fixture-model",
        }.get(key)

    def insert_cart_paper(self, db_path: str, title: str) -> int:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            """INSERT INTO papers
               (title, authors, abstract, arxiv_id, paper_url, in_cart)
               VALUES (?, '[]', 'fixture abstract', ?, ?, 1)""",
            (title, f"fixture.{title}", f"https://example.invalid/{title}"),
        )
        conn.commit()
        conn.close()
        return cursor.lastrowid

    async def test_inflight_analysis_stays_on_starting_workspace_after_switch(self):
        paper_id = self.insert_cart_paper(self.alpha, "alpha-paper")
        workspace.switch_workspace(self.alpha)
        provider = BlockingPaperProvider()

        with patch("services.paper_analysis.config_get", side_effect=self.configured):
            task = asyncio.create_task(
                paper_analysis.analyze_cart_papers(
                    [paper_id], provider_client=provider
                )
            )
            await provider.started.wait()
            with self.assertRaises(workspace.WorkspaceBusyError):
                workspace.clear_workspace()
            self.assertTrue(workspace.switch_workspace(self.beta))
            with self.assertRaises(workspace.WorkspaceBusyError):
                workspace.delete_workspace_file(self.alpha)
            provider.release.set()
            result = await task

        self.assertTrue(result["ok"])
        alpha_conn = sqlite3.connect(self.alpha)
        beta_conn = sqlite3.connect(self.beta)
        self.assertEqual(
            alpha_conn.execute("SELECT COUNT(*) FROM paper_ai_runs").fetchone()[0], 1
        )
        self.assertEqual(
            beta_conn.execute("SELECT COUNT(*) FROM paper_ai_runs").fetchone()[0], 0
        )
        alpha_conn.close()
        beta_conn.close()

    def test_clear_keeps_database_and_asset_target_pinned_during_switch(self):
        asset_root = self.root / "assets"
        workspace.switch_workspace(self.alpha)
        with patch.object(assets, "ASSET_ROOT", asset_root):
            alpha_assets = assets.workspace_asset_dir(self.alpha)
            beta_assets = assets.workspace_asset_dir(self.beta)
            (alpha_assets / "alpha.txt").write_text("alpha", encoding="utf-8")
            (beta_assets / "beta.txt").write_text("beta", encoding="utf-8")
            for db_path, label in ((self.alpha, "alpha"), (self.beta, "beta")):
                conn = sqlite3.connect(db_path)
                item_id = conn.execute(
                    """INSERT INTO items(title, content_text, content_hash)
                       VALUES (?, ?, ?)""",
                    (label, label, f"{label}-hash"),
                ).lastrowid
                conn.execute(
                    """INSERT INTO assets
                       (item_id, asset_kind, original_name, storage_path, mime_type,
                        content_hash, size_bytes)
                       VALUES (?, 'image', ?, ?, 'image/png', ?, 1)""",
                    (item_id, f"{label}.png", f"assets/{label}.png", f"{label}-asset"),
                )
                conn.commit()
                conn.close()

            reached_delete = threading.Event()
            release_delete = threading.Event()
            errors = []
            original_execute = workspace._LeasedWorkspaceConnection.execute

            def blocking_execute(conn, statement, *args, **kwargs):
                if statement == "DELETE FROM item_relations":
                    reached_delete.set()
                    release_delete.wait(timeout=2)
                return original_execute(conn, statement, *args, **kwargs)

            def clear_in_thread():
                try:
                    workspace.clear_workspace()
                except Exception as exc:  # pragma: no cover - asserted below
                    errors.append(exc)

            with patch.object(
                workspace._LeasedWorkspaceConnection,
                "execute",
                new=blocking_execute,
            ):
                thread = threading.Thread(target=clear_in_thread)
                thread.start()
                self.assertTrue(reached_delete.wait(timeout=2))
                self.assertTrue(workspace.switch_workspace(self.beta))
                release_delete.set()
                thread.join(timeout=2)

            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertFalse(alpha_assets.exists())
            self.assertTrue((beta_assets / "beta.txt").is_file())
            alpha_conn = sqlite3.connect(self.alpha)
            beta_conn = sqlite3.connect(self.beta)
            self.assertEqual(alpha_conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
            self.assertEqual(alpha_conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 0)
            self.assertEqual(beta_conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)
            self.assertEqual(beta_conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 1)
            alpha_conn.close()
            beta_conn.close()

    def test_clear_removes_radar_jobs_candidates_and_external_identities(self):
        workspace.switch_workspace(self.alpha)
        conn = workspace.get_active_connection()
        item_id = conn.execute(
            "INSERT INTO items(title, content_text, content_hash) VALUES ('radar', 'radar', 'radar-clear')"
        ).lastrowid
        conn.execute(
            "INSERT INTO item_external_identities(item_id, identity_type, normalized_value) VALUES (?, 'doi', '10.1109/clear')",
            (item_id,),
        )
        job_id = conn.execute(
            "INSERT INTO collection_jobs(collector, query_json) VALUES ('crossref_ieee', '{}')"
        ).lastrowid
        candidate_id = conn.execute(
            """INSERT INTO candidates(job_id, title, content_text, source_kind, source_url,
               content_hash, canonical_id) VALUES (?, 'radar', 'radar', 'crossref_ieee',
               'https://doi.org/10.1109/clear', 'candidate-clear', 'doi:10.1109/clear')""",
            (job_id,),
        ).lastrowid
        conn.execute(
            """INSERT INTO candidate_source_records
               (candidate_id, job_id, source_kind, status, facts_json)
               VALUES (?, ?, 'openalex', 'succeeded', '{}')""",
            (candidate_id, job_id),
        )
        conn.execute(
            "INSERT INTO saved_discovery_rules(name, source_kind, query_json) VALUES ('rule', 'crossref_ieee', '{}')"
        )
        conn.execute(
            """INSERT INTO candidate_ai_runs
               (candidate_ids_json, input_scope_json, input_hash, processor,
                processor_version, prompt_version)
               VALUES (?, '[]', 'clear-hash', 'candidate_brief', '1', 'candidate-brief-v1')""",
            (f"[{candidate_id}]",),
        )
        conn.commit()
        conn.close()
        workspace.clear_workspace()
        conn = sqlite3.connect(self.alpha)
        for table in (
            "collection_jobs", "candidates", "candidate_source_records",
            "saved_discovery_rules", "candidate_ai_runs", "item_external_identities", "items",
        ):
            self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)
        conn.close()

    def test_delete_removes_only_target_database_and_assets(self):
        asset_root = self.root / "assets"
        workspace.switch_workspace(self.beta)
        with patch.object(assets, "ASSET_ROOT", asset_root):
            alpha_assets = assets.workspace_asset_dir(self.alpha)
            beta_assets = assets.workspace_asset_dir(self.beta)
            (alpha_assets / "alpha.png").write_bytes(b"alpha")
            (beta_assets / "beta.png").write_bytes(b"beta")

            workspace.delete_workspace_file(self.alpha)

            self.assertFalse(Path(self.alpha).exists())
            self.assertFalse(alpha_assets.exists())
            self.assertTrue(Path(self.beta).is_file())
            self.assertEqual((beta_assets / "beta.png").read_bytes(), b"beta")

    def test_startup_recovery_and_generic_run_kind_query(self):
        paper_id = self.insert_cart_paper(self.alpha, "recovery-paper")
        conn = sqlite3.connect(self.alpha)
        conn.row_factory = sqlite3.Row
        item_id = conn.execute(
            """INSERT INTO items(title, content_text, content_hash)
               VALUES ('interrupted item', 'fixture', 'interrupted-item')"""
        ).lastrowid
        running_extraction_id = conn.execute(
            """INSERT INTO extraction_runs
               (item_id, processor, processor_version, run_kind, status, input_hash)
               VALUES (?, 'material_ai', '2', 'classify', 'running', 'running-input')""",
            (item_id,),
        ).lastrowid
        terminal_extraction_id = conn.execute(
            """INSERT INTO extraction_runs
               (item_id, processor, processor_version, run_kind, status, input_hash,
                result_json)
               VALUES (?, 'local_tesseract', '1', 'ocr', 'succeeded',
                       'terminal-input', '{"text":"kept"}')""",
            (item_id,),
        ).lastrowid
        session_id = conn.execute(
            "INSERT INTO chat_sessions(title) VALUES ('running')"
        ).lastrowid
        conn.execute(
            "INSERT INTO chat_turns(session_id, user_message) VALUES (?, 'hello')",
            (session_id,),
        )
        review_run = paper_ai_runs.create_run(
            conn,
            paper_id=None,
            paper_ids=[paper_id],
            run_kind="workspace_review",
            input_scope=["title", "abstract"],
            input_hash="fixture-hash",
            processor="workspace_review",
            processor_version="1",
            prompt_version="workspace-review-v1",
            provider="deepseek",
            model="fixture-model",
        )
        running_job_id = conn.execute(
            """INSERT INTO collection_jobs(collector, query_json, status)
               VALUES ('arxiv_api', '{"query":"fixture"}', 'running')"""
        ).lastrowid
        terminal_job_id = conn.execute(
            """INSERT INTO collection_jobs(collector, query_json, status, candidate_count)
               VALUES ('arxiv_api', '{"query":"done"}', 'succeeded', 1)"""
        ).lastrowid
        conn.commit()
        conn.close()

        beta_conn = sqlite3.connect(self.beta)
        beta_item_id = beta_conn.execute(
            """INSERT INTO items(title, content_text, content_hash)
               VALUES ('beta interrupted item', 'fixture', 'beta-interrupted-item')"""
        ).lastrowid
        beta_extraction_id = beta_conn.execute(
            """INSERT INTO extraction_runs
               (item_id, processor, processor_version, run_kind, status, input_hash)
               VALUES (?, 'material_ai', '2', 'compare', 'running', 'beta-running-input')""",
            (beta_item_id,),
        ).lastrowid
        beta_conn.commit()
        beta_conn.close()

        self.assertEqual(workspace.recover_interrupted_runs(self.root), 5)
        self.assertEqual(workspace.recover_interrupted_runs(self.root), 0)

        conn = sqlite3.connect(self.alpha)
        conn.row_factory = sqlite3.Row
        turn = conn.execute("SELECT * FROM chat_turns").fetchone()
        self.assertEqual(turn["status"], "failed")
        self.assertIn("中断", turn["error_message"])
        runs = paper_ai_runs.list_runs(
            conn, run_kind="workspace_review", limit=10
        )
        self.assertEqual([run["id"] for run in runs], [review_run["id"]])
        self.assertEqual(runs[0]["paper_ids"], [paper_id])
        self.assertEqual(runs[0]["status"], "failed")
        running_job = conn.execute(
            "SELECT status, candidate_count, error_message FROM collection_jobs WHERE id = ?",
            (running_job_id,),
        ).fetchone()
        terminal_job = conn.execute(
            "SELECT status, candidate_count, error_message FROM collection_jobs WHERE id = ?",
            (terminal_job_id,),
        ).fetchone()
        self.assertEqual((running_job["status"], running_job["candidate_count"]), ("failed", 0))
        self.assertIn("中断", running_job["error_message"])
        self.assertEqual(tuple(terminal_job), ("succeeded", 1, None))
        interrupted_extraction = conn.execute(
            "SELECT status, result_json, error_message FROM extraction_runs WHERE id = ?",
            (running_extraction_id,),
        ).fetchone()
        terminal_extraction = conn.execute(
            "SELECT status, result_json, error_message FROM extraction_runs WHERE id = ?",
            (terminal_extraction_id,),
        ).fetchone()
        self.assertEqual(interrupted_extraction["status"], "failed")
        self.assertIsNone(interrupted_extraction["result_json"])
        self.assertIn("中断", interrupted_extraction["error_message"])
        self.assertEqual(tuple(terminal_extraction), ("succeeded", '{"text":"kept"}', None))
        conn.close()

        beta_conn = sqlite3.connect(self.beta)
        beta_conn.row_factory = sqlite3.Row
        beta_extraction = beta_conn.execute(
            "SELECT status, error_message FROM extraction_runs WHERE id = ?",
            (beta_extraction_id,),
        ).fetchone()
        beta_conn.close()
        self.assertEqual(beta_extraction["status"], "failed")
        self.assertIn("中断", beta_extraction["error_message"])


if __name__ == "__main__":
    unittest.main()
