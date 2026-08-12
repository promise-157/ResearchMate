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

from api.routes.chat import (
    ChatRequest,
    ChatSessionCreate,
    create_chat_session,
    create_chat_turn as create_chat_turn_route,
    get_chat_session,
    list_chat_sessions,
)
from processors.ai_provider import AIProviderError, AIResponse
from services import chat_service
from storage.workspace import _init_workspace_db, clear_workspace


class FakeChatProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete_messages(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response(content="fixture reply", request_id="req-chat"):
    return AIResponse(
        content=content,
        provider_model="deepseek-v4-pro-fixture",
        input_tokens=31,
        output_tokens=12,
        duration_ms=45,
        request_id=request_id,
        finish_reason="stop",
    )


class ChatServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "chat.db")
        _init_workspace_db(self.db_path)
        conn = self.connect()
        conn.executemany(
            """INSERT INTO papers
               (title, authors, abstract, journal_name, publish_year, arxiv_id, paper_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                ("Selected", "[]", "selected abstract", "arXiv", 2026, "fixture.1", "https://arxiv.org/abs/1"),
                ("Not selected", "[]", "private abstract", "arXiv", 2026, "fixture.2", "https://arxiv.org/abs/2"),
            ],
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def configured(section, key=None):
        values = {
            "api_type": "deepseek",
            "api_key": "fixture-key",
            "api_base_url": "https://fixture.invalid",
            "model": "deepseek-v4-pro",
        }
        if section == "crawler":
            return 30
        return values.get(key)

    async def test_success_persists_scope_metadata_and_only_selected_paper(self):
        fake = FakeChatProvider([response()])
        with patch("services.chat_service.get_active_connection", side_effect=self.connect), \
             patch("services.chat_service.config_get", side_effect=self.configured):
            session = chat_service.create_session()
            turn = await chat_service.create_turn(
                session["id"], message="summarize", paper_ids=[1], provider_client=fake
            )
            restored = chat_service.get_session(session["id"])

        self.assertEqual(turn["status"], "succeeded")
        self.assertEqual(turn["paper_ids"], [1])
        self.assertEqual(turn["input_scope"], ["message", "chat_history", "paper_metadata"])
        self.assertEqual(turn["provider_model"], "deepseek-v4-pro-fixture")
        self.assertEqual(turn["input_tokens"], 31)
        self.assertEqual(turn["request_id"], "req-chat")
        self.assertEqual(turn["prompt_version"], "paper-chat-v1")
        prompt = json.dumps(fake.calls[0][0], ensure_ascii=False)
        self.assertIn("Selected", prompt)
        self.assertIn("selected abstract", prompt)
        self.assertNotIn("Not selected", prompt)
        self.assertNotIn("private abstract", prompt)
        self.assertEqual(restored["turns"][0]["assistant_message"], "fixture reply")

    async def test_history_is_bounded_audited_and_failure_is_persisted(self):
        fake = FakeChatProvider([
            response("first answer", "req-1"),
            AIProviderError("timeout", "模型请求超时，请稍后重试"),
        ])
        with patch("services.chat_service.get_active_connection", side_effect=self.connect), \
             patch("services.chat_service.config_get", side_effect=self.configured):
            session = chat_service.create_session()
            first = await chat_service.create_turn(
                session["id"], message="first", paper_ids=[], provider_client=fake
            )
            failed = await chat_service.create_turn(
                session["id"], message="second", paper_ids=[], provider_client=fake
            )
            restored = chat_service.get_session(session["id"])

        self.assertEqual(first["paper_ids"], [])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["history_turn_ids"], [first["id"]])
        self.assertEqual(failed["error_message"], "模型请求超时，请稍后重试")
        second_messages = fake.calls[1][0]
        self.assertEqual([message["role"] for message in second_messages], [
            "system", "user", "assistant", "user"
        ])
        self.assertEqual(len(restored["turns"]), 2)

    async def test_unknown_provider_exception_is_redacted(self):
        fake = FakeChatProvider([RuntimeError("fixture-key private prompt response")])
        with patch("services.chat_service.get_active_connection", side_effect=self.connect), \
             patch("services.chat_service.config_get", side_effect=self.configured):
            session = chat_service.create_session()
            turn = await chat_service.create_turn(
                session["id"], message="private prompt", paper_ids=[], provider_client=fake
            )
        self.assertEqual(turn["status"], "failed")
        self.assertNotIn("fixture-key", turn["error_message"])
        self.assertNotIn("private prompt", turn["error_message"])

    async def test_provider_value_error_and_invalid_ids_are_not_leaked_or_sent(self):
        fake = FakeChatProvider([ValueError("fixture-key private provider body")])
        with patch("services.chat_service.get_active_connection", side_effect=self.connect), \
             patch("services.chat_service.config_get", side_effect=self.configured):
            session = chat_service.create_session()
            turn = await chat_service.create_turn(
                session["id"], message="private prompt", paper_ids=[], provider_client=fake
            )
            for invalid_ids in ([0], [True], [1, 1]):
                with self.subTest(paper_ids=invalid_ids), self.assertRaises(ValueError):
                    await chat_service.create_turn(
                        session["id"], message="hello", paper_ids=invalid_ids,
                        provider_client=fake,
                    )

        self.assertEqual(turn["status"], "failed")
        self.assertEqual(turn["error_message"], "模型聊天失败，请稍后重试")
        self.assertNotIn("fixture-key", turn["error_message"])
        self.assertEqual(len(fake.calls), 1)

    async def test_history_uses_only_ten_most_recent_successful_turns(self):
        fake = FakeChatProvider([response(f"answer {index}", f"req-{index}") for index in range(12)])
        with patch("services.chat_service.get_active_connection", side_effect=self.connect), \
             patch("services.chat_service.config_get", side_effect=self.configured):
            session = chat_service.create_session()
            turns = []
            for index in range(12):
                turns.append(await chat_service.create_turn(
                    session["id"], message=f"question {index}", paper_ids=[], provider_client=fake
                ))
        self.assertEqual(len(turns[-1]["history_turn_ids"]), 10)
        self.assertNotIn(turns[0]["id"], turns[-1]["history_turn_ids"])
        self.assertEqual(len(fake.calls[-1][0]), 22)  # system + 10 pairs + current user

    def test_single_oversized_history_turn_is_strictly_truncated(self):
        messages, turn_ids = chat_service._history_messages([{
            "id": 1,
            "status": "succeeded",
            "user_message": "u" * 10_000,
            "assistant_message": "a" * 10_000,
        }])
        self.assertEqual(turn_ids, [1])
        self.assertEqual(sum(len(message["content"]) for message in messages), 12_000)

    def test_sessions_are_isolated_by_workspace_database(self):
        second_path = os.path.join(self.temp_dir.name, "other.db")
        _init_workspace_db(second_path)

        def second_connect():
            conn = sqlite3.connect(second_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        with patch("services.chat_service.get_active_connection", side_effect=self.connect):
            chat_service.create_session("first workspace")
            self.assertEqual(len(chat_service.list_sessions()), 1)
        with patch("services.chat_service.get_active_connection", side_effect=second_connect):
            self.assertEqual(chat_service.list_sessions(), [])

    def test_workspace_clear_removes_chat_sessions_and_turns(self):
        conn = self.connect()
        session_id = conn.execute(
            "INSERT INTO chat_sessions(title) VALUES ('fixture')"
        ).lastrowid
        conn.execute(
            "INSERT INTO chat_turns(session_id, user_message) VALUES (?, 'hello')",
            (session_id,),
        )
        conn.commit()
        conn.close()
        with patch("storage.workspace.get_active_connection", side_effect=self.connect), \
             patch("storage.workspace.get_active_path", return_value=self.db_path):
            clear_workspace()
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM chat_turns").fetchone()[0], 0)
        conn.close()

    async def test_api_boundary_returns_persistent_session_and_turn_shapes(self):
        session = {"id": 7, "title": "fixture"}
        turn = {"id": 9, "session_id": 7, "status": "succeeded"}
        with patch("api.routes.chat.chat_service.list_sessions", return_value=[session]), \
             patch("api.routes.chat.chat_service.create_session", return_value=session), \
             patch("api.routes.chat.chat_service.get_session", return_value={
                 **session, "turns": [turn]
             }), \
             patch("api.routes.chat.chat_service.create_turn", return_value=turn):
            self.assertEqual(list_chat_sessions(), [session])
            self.assertEqual(create_chat_session(ChatSessionCreate()), session)
            self.assertEqual(get_chat_session(7)["turns"], [turn])
            routed = await create_chat_turn_route(
                7, ChatRequest(message="hello", paper_ids=[1])
            )
            self.assertEqual(routed, turn)


if __name__ == "__main__":
    unittest.main()
