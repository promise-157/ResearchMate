import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes.settings import test_ai_settings
from processors.ai_provider import AIProviderError, AIResponse, OpenAICompatibleProvider
from services.ai_settings import test_ai_connection


class DeepSeekProviderTests(unittest.IsolatedAsyncioTestCase):
    def provider(self, handler):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return OpenAICompatibleProvider(
            provider="deepseek",
            api_key="fixture-secret",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-pro",
            client=client,
        ), client

    async def test_json_output_and_response_metadata(self):
        captured = {}

        def handler(request):
            captured.update(json.loads(request.content))
            self.assertEqual(request.url.path, "/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer fixture-secret")
            return httpx.Response(200, headers={"x-request-id": "req-fixture"}, json={
                "id": "completion-fixture",
                "model": "deepseek-v4-pro-202608",
                "choices": [{
                    "message": {"content": '{"summary":"ok"}'},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16},
            })

        provider, client = self.provider(handler)
        try:
            result = await provider.complete("return json", structured=True)
        finally:
            await client.aclose()
        self.assertEqual(captured["response_format"], {"type": "json_object"})
        self.assertEqual(captured["thinking"], {"type": "disabled"})
        self.assertEqual(result.provider_model, "deepseek-v4-pro-202608")
        self.assertEqual(result.input_tokens, 11)
        self.assertEqual(result.output_tokens, 5)
        self.assertEqual(result.request_id, "req-fixture")

    async def test_deepseek_open_chat_keeps_provider_thinking_default(self):
        captured = {}

        def handler(request):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            })

        provider, client = self.provider(handler)
        try:
            await provider.complete("chat", structured=False)
        finally:
            await client.aclose()
        self.assertNotIn("thinking", captured)

    async def test_compatible_provider_does_not_receive_deepseek_thinking_parameter(self):
        captured = {}

        def handler(request):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            })

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = OpenAICompatibleProvider(
            provider="custom",
            api_key="fixture-secret",
            base_url="https://compatible.example/v1",
            model="fixture-model",
            client=client,
        )
        try:
            await provider.complete("chat", structured=False, thinking=False)
        finally:
            await client.aclose()
        self.assertNotIn("thinking", captured)

    async def test_safe_http_error_mapping(self):
        cases = {
            401: "鉴权失败", 402: "余额或额度不足", 404: "模型或 API 端点不存在",
            429: "过于频繁", 500: "暂时不可用",
        }
        for status, message in cases.items():
            with self.subTest(status=status):
                provider, client = self.provider(lambda request, status=status: httpx.Response(
                    status, text='{"error":"fixture-secret private prompt"}'
                ))
                try:
                    with self.assertRaisesRegex(AIProviderError, message) as raised:
                        await provider.complete("private prompt", structured=False)
                finally:
                    await client.aclose()
                self.assertNotIn("fixture-secret", str(raised.exception))
                self.assertNotIn("private prompt", str(raised.exception))

    async def test_model_not_found_is_mapped_without_echoing_body(self):
        provider, client = self.provider(lambda request: httpx.Response(400, json={
            "error": {"code": "invalid_model", "message": "Model Not Exist fixture-private"}
        }))
        try:
            with self.assertRaisesRegex(AIProviderError, "模型不存在") as raised:
                await provider.complete("fixture", structured=False)
        finally:
            await client.aclose()
        self.assertNotIn("fixture-private", str(raised.exception))

    async def test_timeout_is_actionable(self):
        def timeout(request):
            raise httpx.ConnectTimeout("fixture timeout", request=request)

        provider, client = self.provider(timeout)
        try:
            with self.assertRaisesRegex(AIProviderError, "请求超时"):
                await provider.complete("fixture", structured=False)
        finally:
            await client.aclose()

    async def test_empty_truncated_and_invalid_response_fail(self):
        fixtures = [
            ({"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]}, "空内容"),
            ({"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]}, "截断"),
            ({"unexpected": True}, "无法解析"),
        ]
        for payload, message in fixtures:
            with self.subTest(message=message):
                provider, client = self.provider(
                    lambda request, payload=payload: httpx.Response(200, json=payload)
                )
                try:
                    with self.assertRaisesRegex(AIProviderError, message):
                        await provider.complete("fixture", structured=True)
                finally:
                    await client.aclose()

    async def test_connection_service_returns_metadata_without_content(self):
        response = AIResponse(
            content="OK", provider_model="deepseek-v4-pro", input_tokens=8,
            output_tokens=1, duration_ms=23, request_id="req-1", finish_reason="stop",
        )
        client = AsyncMock()
        client.complete.return_value = response
        with patch("services.ai_settings.config_get", side_effect=lambda section, key=None: {
            "api_type": "deepseek", "model": "deepseek-v4-pro"
        }.get(key)):
            result = await test_ai_connection(client)
        self.assertNotIn("content", result)
        self.assertEqual(result["request_id"], "req-1")
        client.complete.assert_awaited_once_with(
            "这是一次用户明确发起的连接测试。请只回复 OK。",
            structured=False,
            max_tokens=64,
            thinking=False,
        )

    async def test_api_exposes_only_safe_connection_error(self):
        with patch(
            "api.routes.settings.test_ai_connection",
            new=AsyncMock(side_effect=AIProviderError("authentication", "模型鉴权失败，请检查会话 API Key")),
        ):
            with self.assertRaises(HTTPException) as raised:
                await test_ai_settings()
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail, "模型鉴权失败，请检查会话 API Key")

    async def test_api_returns_safe_connection_metadata(self):
        expected = {
            "ok": True, "provider": "deepseek", "provider_model": "fixture",
            "input_tokens": 8, "output_tokens": 1, "duration_ms": 20,
            "request_id": "req-fixture",
        }
        with patch(
            "api.routes.settings.test_ai_connection",
            new=AsyncMock(return_value=expected),
        ):
            self.assertEqual(await test_ai_settings(), expected)


if __name__ == "__main__":
    unittest.main()
