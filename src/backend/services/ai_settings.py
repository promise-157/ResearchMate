"""Explicit AI connection checks; never called automatically."""
from typing import Any

from config import get as config_get
from processors.ai_provider import AIResponse, OpenAICompatibleProvider


async def test_ai_connection(provider_client: Any | None = None) -> dict[str, Any]:
    provider = config_get("ai", "api_type") or "openai"
    if provider == "claude":
        raise ValueError("当前连接测试支持 DeepSeek、OpenAI、Ollama 和兼容接口")
    client = provider_client or OpenAICompatibleProvider(
        provider=provider,
        api_key=config_get("ai", "api_key") or "",
        base_url=config_get("ai", "api_base_url") or "",
        model=config_get("ai", "model") or "",
        timeout_seconds=min(config_get("crawler", "timeout") or 30, 30),
    )
    response = await client.complete(
        "这是一次用户明确发起的连接测试。请只回复 OK。",
        structured=False,
        max_tokens=64,
        thinking=False if provider == "deepseek" else None,
    )
    if not isinstance(response, AIResponse):
        raise RuntimeError("连接测试未返回有效元数据")
    return {
        "ok": True,
        "provider": provider,
        "configured_model": config_get("ai", "model"),
        "provider_model": response.provider_model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "duration_ms": response.duration_ms,
        "request_id": response.request_id,
    }
