"""全局设置"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional
from config import (
    ConfigSaveError,
    get as config_get,
    get_ai_key_source,
    get_config_path,
    update_ai_config,
    update_crawler_config,
)
from processors.ai_provider import AIProviderError
from services.ai_settings import test_ai_connection
from services.runtime_info import get_runtime_info

router = APIRouter()


def _public_ai_settings():
    return {
        "api_type": config_get("ai", "api_type"),
        "api_key": "",
        "has_key": bool(config_get("ai", "api_key")),
        "key_source": get_ai_key_source(),
        "key_storage_mode": config_get("ai", "key_storage_mode") or "session",
        "config_path": get_config_path(),
        "api_base_url": config_get("ai", "api_base_url"),
        "model": config_get("ai", "model"),
    }


class AISettingsUpdate(BaseModel):
    api_type: Optional[Literal["openai", "claude", "deepseek", "ollama", "custom"]] = None
    api_key: Optional[str] = Field(None, max_length=10_000)
    key_storage_mode: Optional[Literal["session", "config"]] = None
    api_base_url: Optional[str] = Field(None, max_length=2_000)
    model: Optional[str] = Field(None, max_length=200)
    clear_api_key: bool = False


class CrawlSettingsUpdate(BaseModel):
    max_papers_per_source: Optional[int] = Field(None, ge=1, le=200)
    request_interval: Optional[int] = Field(None, ge=1, le=60)
    timeout: Optional[int] = Field(None, ge=5, le=180)


class SettingsUpdate(BaseModel):
    ai: Optional[AISettingsUpdate] = None
    crawl: Optional[CrawlSettingsUpdate] = None


@router.get("/settings")
def get_settings():
    return {
        "theme": "system",
        "ai": _public_ai_settings(),
        "crawl": {
            "max_papers_per_source": config_get("crawler", "max_papers_per_source"),
            "request_interval": config_get("crawler", "request_interval"),
            "timeout": config_get("crawler", "timeout"),
        },
        "runtime": get_runtime_info(),
    }


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    try:
        if body.ai:
            update_ai_config(
                api_type=body.ai.api_type,
                api_key="" if body.ai.clear_api_key else body.ai.api_key,
                key_storage_mode=body.ai.key_storage_mode,
                api_base_url=body.ai.api_base_url,
                model=body.ai.model,
            )
        if body.crawl:
            update_crawler_config(
                max_papers_per_source=body.crawl.max_papers_per_source,
                request_interval=body.crawl.request_interval,
                timeout=body.crawl.timeout,
            )
    except (ConfigSaveError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "ai": _public_ai_settings()}


@router.post("/settings/ai/test")
async def test_ai_settings():
    """Make exactly one explicit, minimal provider request."""
    try:
        return await test_ai_connection()
    except (AIProviderError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
