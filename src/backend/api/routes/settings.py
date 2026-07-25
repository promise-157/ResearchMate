"""全局设置"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from config import get as config_get, update_ai_config

router = APIRouter()


class AISettingsUpdate(BaseModel):
    api_type: Optional[str] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    model: Optional[str] = None


class SettingsUpdate(BaseModel):
    ai: Optional[AISettingsUpdate] = None


@router.get("/settings")
def get_settings():
    return {
        "theme": "system",
        "ai": {
            "api_type": config_get("ai", "api_type"),
            "api_key": "",  # 不回传 key
            "has_key": bool(config_get("ai", "api_key")),
            "api_base_url": config_get("ai", "api_base_url"),
            "model": config_get("ai", "model"),
        },
        "crawl": {
            "max_papers_per_source": config_get("crawler", "max_papers_per_source"),
            "request_interval": config_get("crawler", "request_interval"),
            "timeout": config_get("crawler", "timeout"),
        },
    }


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    if body.ai:
        update_ai_config(
            api_type=body.ai.api_type,
            api_key=body.ai.api_key,
            api_base_url=body.ai.api_base_url,
            model=body.ai.model,
        )
    return {"ok": True}
