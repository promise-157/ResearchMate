"""Local deterministic Debug template extraction and user confirmation."""
import hashlib
import re
from typing import Any

from storage import items as item_repository
from storage import templates as template_repository
from storage.workspace import get_active_connection


TEMPLATE_KEY = "debug"
SCHEMA_VERSION = 1
EXTRACTOR = "debug_label_rules"
EXTRACTOR_VERSION = "1"
FIELDS = ("error", "environment", "attempts", "root_cause", "solution")
LABELS = {
    "error": ("错误", "错误信息", "报错", "error", "exception"),
    "environment": ("环境", "运行环境", "environment"),
    "attempts": ("尝试", "已尝试", "attempts", "tried"),
    "root_cause": ("根因", "原因", "root cause", "cause"),
    "solution": ("方案", "解决方案", "修复", "solution", "fix"),
}


def extract_debug_fields(text: str) -> dict[str, str]:
    aliases = {
        alias.lower(): field for field, names in LABELS.items() for alias in names
    }
    result: dict[str, str] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^([^:：]{1,30})\s*[:：]\s*(.*)$", line)
        field = aliases.get(match.group(1).strip().lower()) if match else None
        if field:
            current = field
            value = match.group(2).strip()
            if value:
                result[field] = value[:4_000]
        elif current and current in result:
            result[current] = f"{result[current]}\n{line}"[:4_000]
    return result


def extract_debug_template(item_id: int) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        if item["item_type"] != "debug":
            raise ValueError("只有 Debug 资料可以使用 Debug 模板")
        return extract_debug_template_with_connection(conn, item)
    finally:
        conn.close()


def extract_debug_template_with_connection(
    conn: Any, item: dict[str, Any]
) -> dict[str, Any]:
    extracted = extract_debug_fields(item["content_text"])
    input_hash = hashlib.sha256(item["content_text"].encode("utf-8")).hexdigest()
    run = item_repository.create_extraction_run(conn, {
        "item_id": item["id"],
        "processor": EXTRACTOR,
        "processor_version": EXTRACTOR_VERSION,
        "run_kind": "template_extract",
        "input_hash": input_hash,
        "input_scope": ["content_text"],
        "provider": "local",
        "model": "deterministic-rules",
        "prompt_version": "none",
    })
    template = template_repository.save_extracted(
        conn,
        item_id=item["id"],
        template_key=TEMPLATE_KEY,
        schema_version=SCHEMA_VERSION,
        extracted=extracted,
        extractor=EXTRACTOR,
        extractor_version=EXTRACTOR_VERSION,
    )
    item_repository.complete_extraction_run(conn, run["id"], result=extracted)
    return template


def get_debug_template(item_id: int) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        if item["item_type"] != "debug":
            raise ValueError("只有 Debug 资料可以使用 Debug 模板")
        template = template_repository.get_template(conn, item_id)
    finally:
        conn.close()
    return template or {
        "item_id": item_id,
        "template_key": TEMPLATE_KEY,
        "schema_version": SCHEMA_VERSION,
        "extracted": {},
        "confirmed": {},
        "effective": {},
        "persisted": False,
    }


def confirm_debug_template(item_id: int, fields: dict[str, str | None]) -> dict[str, Any] | None:
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        if item["item_type"] != "debug":
            raise ValueError("只有 Debug 资料可以使用 Debug 模板")
        existing = template_repository.get_template(conn, item_id)
        if not existing:
            conn.close()
            return _confirm_after_extract(item_id, fields)
        confirmed = dict(existing["confirmed"])
        for key, value in fields.items():
            if key not in FIELDS:
                continue
            normalized = value.strip() if value is not None else ""
            if normalized:
                confirmed[key] = normalized[:4_000]
            else:
                confirmed.pop(key, None)
        return template_repository.save_confirmed(conn, item_id, confirmed)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _confirm_after_extract(item_id: int, fields: dict[str, str | None]) -> dict[str, Any] | None:
    extract_debug_template(item_id)
    return confirm_debug_template(item_id, fields)
