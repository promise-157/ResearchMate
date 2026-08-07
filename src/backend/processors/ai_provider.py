"""Bounded, backend-only adapters for external AI providers."""
from dataclasses import dataclass
import time
from typing import Any
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class AIResponse:
    content: str
    provider_model: str | None
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: int
    request_id: str | None
    finish_reason: str | None


class AIProviderError(RuntimeError):
    """A safe, user-actionable provider error with no response body or secret."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_openai_compatible_config(base_url: str, model: str) -> tuple[str, str]:
    base_url = base_url.strip().rstrip("/")
    model = model.strip()
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AIProviderError("invalid_config", "API Base URL 必须是有效的 HTTP/HTTPS 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AIProviderError("invalid_config", "API Base URL 不能包含凭据、查询参数或片段")
    if not model:
        raise AIProviderError("invalid_config", "模型名称不能为空")
    return base_url, model


def _http_error(response: httpx.Response) -> AIProviderError:
    status = response.status_code
    provider_code = ""
    provider_message = ""
    try:
        error = response.json().get("error", {})
        if isinstance(error, dict):
            provider_code = str(error.get("code") or "").lower()
            provider_message = str(error.get("message") or "").lower()
    except (ValueError, AttributeError):
        pass
    model_marker = f"{provider_code} {provider_message}"
    if status in {400, 404, 422} and "model" in model_marker and any(
        marker in model_marker for marker in ("not found", "not exist", "unknown", "invalid")
    ):
        return AIProviderError("model_not_found", "模型不存在，请检查设置中的模型名称")
    if status == 400:
        return AIProviderError("invalid_request", "模型请求格式不受支持，请检查服务商、模型和参数")
    if status == 401:
        return AIProviderError("authentication", "模型鉴权失败，请检查会话 API Key")
    if status == 402:
        return AIProviderError("insufficient_balance", "模型账户余额或额度不足，请检查服务商账户")
    if status in {403}:
        return AIProviderError("permission", "模型服务拒绝访问，请检查 Key 权限和账户状态")
    if status in {404}:
        return AIProviderError("model_not_found", "模型或 API 端点不存在，请检查模型名称和 Base URL")
    if status == 422:
        return AIProviderError("invalid_parameters", "模型请求参数无效，请检查模型能力与配置")
    if status == 429:
        return AIProviderError("rate_limit", "模型请求过于频繁，请稍后重试")
    if 500 <= status <= 599:
        return AIProviderError("provider_unavailable", "模型服务暂时不可用，请稍后重试")
    return AIProviderError("http_error", f"模型服务返回 HTTP {status}，请检查配置后重试")


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


class OpenAICompatibleProvider:
    """OpenAI Chat Completions adapter used by named DeepSeek and compatible providers."""

    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 120,
        client: httpx.AsyncClient | None = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.base_url, self.model = validate_openai_compatible_config(base_url, model)
        self.timeout_seconds = timeout_seconds
        self.client = client

    async def complete(
        self,
        prompt: str,
        *,
        structured: bool,
        max_tokens: int = 2048,
        thinking: bool | None = None,
    ) -> AIResponse:
        if self.provider != "ollama" and not self.api_key.strip():
            raise AIProviderError("missing_key", "尚未配置会话 API Key")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3 if structured else 0.7,
            "max_tokens": max_tokens,
        }
        if structured:
            body["response_format"] = {"type": "json_object"}
        if self.provider == "deepseek":
            # DeepSeek V4 defaults to thinking. It is unnecessary for bounded
            # connection checks and can consume the output budget before a
            # strict JSON answer is produced.
            effective_thinking = False if structured and thinking is None else thinking
            if effective_thinking is not None:
                body["thinking"] = {
                    "type": "enabled" if effective_thinking else "disabled"
                }

        started = time.monotonic()
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=body
            )
        except httpx.TimeoutException as exc:
            raise AIProviderError("timeout", "模型请求超时，请稍后重试或缩小输入范围") from exc
        except httpx.HTTPError as exc:
            raise AIProviderError("network", "无法连接模型服务，请检查网络和 API Base URL") from exc
        finally:
            if owns_client:
                await client.aclose()
        duration_ms = max(0, round((time.monotonic() - started) * 1000))
        if response.status_code != 200:
            raise _http_error(response)
        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("invalid_response", "模型响应格式无法解析，请稍后重试") from exc
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise AIProviderError("truncated", "模型响应因长度限制被截断，请缩小输入范围后重试")
        if finish_reason not in {None, "stop"}:
            raise AIProviderError("incomplete", "模型未正常完成响应，请调整输入后重试")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("empty_response", "模型返回空内容，请重试或调整提示词")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        request_id = next((response.headers.get(name) for name in (
            "x-request-id", "x-ds-trace-id", "request-id"
        ) if response.headers.get(name)), None) or (
            data.get("id") if isinstance(data.get("id"), str) else None
        )
        return AIResponse(
            content=content,
            provider_model=data.get("model") if isinstance(data.get("model"), str) else None,
            input_tokens=_optional_int(usage.get("prompt_tokens")),
            output_tokens=_optional_int(usage.get("completion_tokens")),
            duration_ms=duration_ms,
            request_id=request_id,
            finish_reason=finish_reason,
        )
