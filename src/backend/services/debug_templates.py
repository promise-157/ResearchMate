"""Local deterministic Debug extraction rules and compatibility service API."""
import re
from typing import Any

from storage import items as item_repository
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
        if item["item_type"] != TEMPLATE_KEY:
            raise ValueError("只有 Debug 资料可以使用 Debug 模板")
        return extract_debug_template_with_connection(conn, item)
    finally:
        conn.close()


def extract_debug_template_with_connection(
    conn: Any, item: dict[str, Any]
) -> dict[str, Any]:
    from services.template_registry import extract_template_with_connection
    return extract_template_with_connection(conn, item)


def get_debug_template(item_id: int) -> dict[str, Any] | None:
    from services.template_registry import get_template_with_connection
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        if item["item_type"] != TEMPLATE_KEY:
            raise ValueError("只有 Debug 资料可以使用 Debug 模板")
        return get_template_with_connection(conn, item)
    finally:
        conn.close()


def confirm_debug_template(item_id: int, fields: dict[str, str | None]) -> dict[str, Any] | None:
    from services.template_registry import confirm_template_with_connection
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        if item["item_type"] != TEMPLATE_KEY:
            raise ValueError("只有 Debug 资料可以使用 Debug 模板")
        return confirm_template_with_connection(conn, item, fields)
    finally:
        conn.close()
