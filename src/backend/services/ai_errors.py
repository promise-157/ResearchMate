"""Stable user-facing errors for audited AI workflows."""
from processors.ai_provider import AIProviderError


def safe_provider_error(exc: Exception, fallback: str) -> str:
    """Only audited provider errors are safe to expose verbatim."""
    if isinstance(exc, AIProviderError):
        return str(exc).strip()[:1_000] or fallback
    return fallback
