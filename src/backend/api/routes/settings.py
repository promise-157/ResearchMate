"""全局设置"""
from fastapi import APIRouter
from config import get as config_get

router = APIRouter()


@router.get("/settings")
def get_settings():
    return {
        "theme": "system",
        "ai": {
            "api_type": config_get("ai", "api_type"),
            "api_key": "",  # 不回传 key
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
def update_settings():
    # TODO: 持久化设置到 config.yaml
    return {"ok": True}
