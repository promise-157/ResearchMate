"""Read-only description of the current source or desktop installation."""

from __future__ import annotations

import json
import os
from pathlib import Path


RUNTIME_INFO_ENV = "RESEARCHMATE_RUNTIME_INFO_JSON"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def get_runtime_info() -> dict:
    raw = os.environ.get(RUNTIME_INFO_ENV, "")
    if raw:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if _is_valid_payload(payload):
            return payload

    return {
        "schema_version": 1,
        "platform": "source",
        "platform_label": "源码 / 浏览器模式",
        "paths": [
            {
                "label": "ResearchMate 源码",
                "path": str(PROJECT_ROOT),
                "ownership": "user",
            },
            {
                "label": "前端依赖",
                "path": str(PROJECT_ROOT / "src" / "frontend" / "node_modules"),
                "ownership": "rebuildable",
            },
            {
                "label": "前端构建",
                "path": str(PROJECT_ROOT / "src" / "frontend" / "dist"),
                "ownership": "rebuildable",
            },
            {
                "label": "工作区与用户资产",
                "path": str(PROJECT_ROOT / "src" / "data"),
                "ownership": "user_data",
            },
        ],
        "uninstall": {
            "available": False,
            "summary": "当前由源码启动，没有检测到桌面宿主；请按 README 手工移除环境。",
            "guide_path": "",
        },
    }


def _is_valid_payload(payload: object) -> bool:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return False
    if not isinstance(payload.get("platform"), str):
        return False
    if not isinstance(payload.get("platform_label"), str):
        return False
    paths = payload.get("paths")
    uninstall = payload.get("uninstall")
    if not isinstance(paths, list) or len(paths) > 20 or not isinstance(uninstall, dict):
        return False
    for entry in paths:
        if not isinstance(entry, dict):
            return False
        if not all(isinstance(entry.get(key), str) for key in ("label", "path", "ownership")):
            return False
    return (
        isinstance(uninstall.get("available"), bool)
        and isinstance(uninstall.get("summary"), str)
        and isinstance(uninstall.get("guide_path"), str)
    )
