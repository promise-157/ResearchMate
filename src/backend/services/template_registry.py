"""Shared dispatch for versioned deterministic domain templates."""
import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from services.debug_templates import extract_debug_fields
from services.job_templates import extract_job_fields
from storage import items as item_repository
from storage import templates as template_repository
from storage.workspace import get_active_connection


@dataclass(frozen=True)
class TemplateSpec:
    key: str
    schema_version: int
    extractor: str
    extractor_version: str
    fields: tuple[str, ...]
    extract: Callable[[str], dict[str, str]]


TEMPLATE_SPECS = {
    "debug": TemplateSpec(
        key="debug",
        schema_version=1,
        extractor="debug_label_rules",
        extractor_version="1",
        fields=("error", "environment", "attempts", "root_cause", "solution"),
        extract=extract_debug_fields,
    ),
    "job": TemplateSpec(
        key="job",
        schema_version=1,
        extractor="job_label_rules",
        extractor_version="1",
        fields=(
            "company", "role", "location", "salary", "skills", "experience",
            "application_status",
        ),
        extract=extract_job_fields,
    ),
}


def get_template_spec(item_type: str) -> TemplateSpec | None:
    return TEMPLATE_SPECS.get(item_type)


def _require_spec(item: dict[str, Any]) -> TemplateSpec:
    spec = get_template_spec(item["item_type"])
    if not spec:
        raise ValueError("该资料类型没有可用模板")
    return spec


def extract_template_with_connection(
    conn: Any, item: dict[str, Any]
) -> dict[str, Any]:
    spec = _require_spec(item)
    input_hash = hashlib.sha256(item["content_text"].encode("utf-8")).hexdigest()
    run = item_repository.create_extraction_run(conn, {
        "item_id": item["id"],
        "processor": spec.extractor,
        "processor_version": spec.extractor_version,
        "run_kind": "template_extract",
        "input_hash": input_hash,
        "input_scope": ["content_text"],
        "provider": "local",
        "model": "deterministic-rules",
        "prompt_version": "none",
    })
    try:
        extracted = spec.extract(item["content_text"])
        template = template_repository.save_extracted(
            conn,
            item_id=item["id"],
            template_key=spec.key,
            schema_version=spec.schema_version,
            extracted=extracted,
            extractor=spec.extractor,
            extractor_version=spec.extractor_version,
        )
    except Exception as exc:
        item_repository.complete_extraction_run(conn, run["id"], error_message=str(exc))
        raise RuntimeError(f"本地模板提取失败：{exc}") from exc
    item_repository.complete_extraction_run(conn, run["id"], result=extracted)
    return template


def extract_item_template(item_id: int) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        return extract_template_with_connection(conn, item)
    finally:
        conn.close()


def get_template_with_connection(
    conn: Any, item: dict[str, Any]
) -> dict[str, Any]:
    spec = _require_spec(item)
    template = template_repository.get_template(conn, item["id"])
    return template or {
        "item_id": item["id"],
        "template_key": spec.key,
        "schema_version": spec.schema_version,
        "extracted": {},
        "confirmed": {},
        "effective": {},
        "persisted": False,
    }


def get_item_template(item_id: int) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        return get_template_with_connection(conn, item)
    finally:
        conn.close()


def confirm_template_with_connection(
    conn: Any, item: dict[str, Any], fields: dict[str, str | None]
) -> dict[str, Any]:
    spec = _require_spec(item)
    unknown = sorted(set(fields) - set(spec.fields))
    if unknown:
        raise ValueError(f"未知模板字段：{', '.join(unknown)}")
    existing = template_repository.get_template(conn, item["id"])
    if not existing:
        existing = extract_template_with_connection(conn, item)
    confirmed = dict(existing["confirmed"])
    for key, value in fields.items():
        normalized = value.strip() if value is not None else ""
        if len(normalized) > 4_000:
            raise ValueError(f"字段 {key} 不能超过 4000 个字符")
        if normalized:
            confirmed[key] = normalized
        else:
            confirmed.pop(key, None)
    return template_repository.save_confirmed(conn, item["id"], confirmed)


def confirm_item_template(
    item_id: int, fields: dict[str, str | None]
) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        return confirm_template_with_connection(conn, item, fields)
    finally:
        conn.close()
