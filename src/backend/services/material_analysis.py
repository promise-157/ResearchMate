"""Auditable workflow for explicit AI analysis of one material."""
import hashlib
import json
from typing import Any

from config import get as config_get
from processors.material_ai import (
    PROCESSOR_NAME,
    PROCESSOR_VERSION,
    PROMPT_VERSIONS,
    MaterialAIProvider,
    validate_result,
)
from storage import items as item_repository
from storage import accepted_extractions as accepted_extraction_repository
from storage.workspace import get_active_connection


ALLOWED_INPUT_FIELDS = {
    "title", "content_text", "accepted_extraction", "item_type", "tags", "source_url"
}
CONTENT_TEXT_LIMIT = 12_000
COMPARISON_TEXT_LIMIT = 3_000


def list_material_runs(item_id: int) -> list[dict[str, Any]] | None:
    conn = get_active_connection()
    try:
        if not item_repository.get_item(conn, item_id):
            return None
        return item_repository.list_extraction_runs(conn, item_id)
    finally:
        conn.close()


async def analyze_material(
    item_id: int,
    *,
    analysis_type: str,
    input_fields: list[str],
    provider_client: Any | None = None,
) -> tuple[dict[str, Any] | None, bool]:
    if analysis_type not in PROMPT_VERSIONS:
        raise ValueError("未知分析类型")
    unique_fields = list(dict.fromkeys(input_fields))
    if not unique_fields or any(field not in ALLOWED_INPUT_FIELDS for field in unique_fields):
        raise ValueError("发送范围包含不支持的字段")

    provider = config_get("ai", "api_type") or "openai"
    model = (config_get("ai", "model") or "").strip()
    api_key = (config_get("ai", "api_key") or "").strip()
    if not model or (provider != "ollama" and not api_key):
        raise ValueError("尚未配置可用模型；请先到设置页填写模型和会话 API Key，或选择本地 Ollama")

    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None, False
        selected_input = {
            field: (
                accepted_extraction_repository.get_text(conn, item_id)
                if field == "accepted_extraction"
                else item.get(field)
            )
            for field in unique_fields
        }
        if "content_text" in selected_input:
            selected_input["content_text"] = selected_input["content_text"][:CONTENT_TEXT_LIMIT]
        if "accepted_extraction" in selected_input:
            selected_input["accepted_extraction"] = selected_input["accepted_extraction"][:CONTENT_TEXT_LIMIT]
        input_hash = hashlib.sha256(json.dumps(
            {"analysis_type": analysis_type, "input": selected_input},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        prompt_version = PROMPT_VERSIONS[analysis_type]
        reusable = item_repository.find_reusable_run(
            conn, item_id=item_id, run_kind=analysis_type, input_hash=input_hash,
            processor_version=PROCESSOR_VERSION, prompt_version=prompt_version,
            provider=provider, model=model,
        )
        if reusable:
            return reusable, True
        run = item_repository.create_extraction_run(conn, {
            "item_id": item_id,
            "processor": PROCESSOR_NAME,
            "processor_version": PROCESSOR_VERSION,
            "run_kind": analysis_type,
            "input_hash": input_hash,
            "input_scope": unique_fields,
            "input_item_ids": [item_id],
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
        })
        try:
            raw_result = await (provider_client or MaterialAIProvider()).analyze(
                analysis_type, selected_input
            )
            result = validate_result(analysis_type, raw_result)
        except Exception as exc:
            message = str(exc).strip()[:1000] or "模型分析失败"
            item_repository.complete_extraction_run(
                conn, run["id"], error_message=message
            )
            raise RuntimeError(message) from exc
        completed = item_repository.complete_extraction_run(
            conn, run["id"], result=result
        )
        return completed, False
    finally:
        conn.close()


def list_comparison_runs() -> list[dict[str, Any]]:
    conn = get_active_connection()
    try:
        return item_repository.list_comparison_runs(conn)
    finally:
        conn.close()


async def compare_materials(
    item_ids: list[int], *, input_fields: list[str], provider_client: Any | None = None
) -> tuple[dict[str, Any], bool]:
    unique_ids = list(dict.fromkeys(item_ids))
    unique_fields = list(dict.fromkeys(input_fields))
    if not 2 <= len(unique_ids) <= 20:
        raise ValueError("请选择 2–20 条不同资料")
    if not unique_fields or any(field not in ALLOWED_INPUT_FIELDS for field in unique_fields):
        raise ValueError("发送范围包含不支持的字段")
    provider = config_get("ai", "api_type") or "openai"
    model = (config_get("ai", "model") or "").strip()
    api_key = (config_get("ai", "api_key") or "").strip()
    if not model or (provider != "ollama" and not api_key):
        raise ValueError("尚未配置可用模型；请先到设置页填写模型和会话 API Key，或选择本地 Ollama")
    conn = get_active_connection()
    try:
        items = item_repository.get_items_by_ids(conn, unique_ids)
        if len(items) != len(unique_ids):
            raise ValueError("部分资料不存在，请刷新后重新选择")
        selected = []
        for item in items:
            entry = {"id": item["id"]}
            entry.update({
                field: (
                    accepted_extraction_repository.get_text(conn, item["id"])
                    if field == "accepted_extraction"
                    else item.get(field)
                )
                for field in unique_fields
            })
            if "content_text" in entry:
                entry["content_text"] = entry["content_text"][:COMPARISON_TEXT_LIMIT]
            if "accepted_extraction" in entry:
                entry["accepted_extraction"] = entry["accepted_extraction"][:COMPARISON_TEXT_LIMIT]
            selected.append(entry)
        input_hash = hashlib.sha256(json.dumps(
            {"analysis_type": "compare", "input": selected}, ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        reusable = item_repository.find_reusable_run(
            conn, item_id=unique_ids[0], run_kind="compare", input_hash=input_hash,
            processor_version=PROCESSOR_VERSION, prompt_version=PROMPT_VERSIONS["compare"],
            provider=provider, model=model,
        )
        if reusable:
            return reusable, True
        run = item_repository.create_extraction_run(conn, {
            "item_id": unique_ids[0], "processor": PROCESSOR_NAME,
            "processor_version": PROCESSOR_VERSION, "run_kind": "compare",
            "input_hash": input_hash, "input_scope": unique_fields,
            "input_item_ids": unique_ids, "provider": provider, "model": model,
            "prompt_version": PROMPT_VERSIONS["compare"],
        })
        try:
            raw = await (provider_client or MaterialAIProvider()).analyze("compare", {"items": selected})
            result = validate_result("compare", raw)
        except Exception as exc:
            message = str(exc).strip()[:1000] or "模型比较失败"
            item_repository.complete_extraction_run(conn, run["id"], error_message=message)
            raise RuntimeError(message) from exc
        return item_repository.complete_extraction_run(conn, run["id"], result=result), False
    finally:
        conn.close()
