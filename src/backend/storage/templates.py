"""Repository for versioned domain-template data."""
import json
import sqlite3
from typing import Any


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    value = dict(row)
    for source, target in (("extracted_json", "extracted"), ("confirmed_json", "confirmed")):
        raw = value.pop(source, "{}")
        try:
            value[target] = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            value[target] = {}
    value["effective"] = {**value["extracted"], **value["confirmed"]}
    return value


def get_template(conn: sqlite3.Connection, item_id: int) -> dict[str, Any] | None:
    return _decode(conn.execute(
        "SELECT * FROM item_template_data WHERE item_id = ?", (item_id,)
    ).fetchone())


def save_extracted(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    template_key: str,
    schema_version: int,
    extracted: dict[str, Any],
    extractor: str,
    extractor_version: str,
) -> dict[str, Any]:
    conn.execute(
        """INSERT INTO item_template_data
           (item_id, template_key, schema_version, extracted_json, extractor,
            extractor_version, extracted_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(item_id) DO UPDATE SET
             template_key = excluded.template_key,
             schema_version = excluded.schema_version,
             extracted_json = excluded.extracted_json,
             extractor = excluded.extractor,
             extractor_version = excluded.extractor_version,
             extracted_at = datetime('now'), updated_at = datetime('now')""",
        (
            item_id, template_key, schema_version,
            json.dumps(extracted, ensure_ascii=False), extractor, extractor_version,
        ),
    )
    conn.commit()
    return get_template(conn, item_id)


def save_confirmed(
    conn: sqlite3.Connection, item_id: int, confirmed: dict[str, Any]
) -> dict[str, Any] | None:
    conn.execute(
        """UPDATE item_template_data SET confirmed_json = ?,
           confirmed_at = datetime('now'), updated_at = datetime('now')
           WHERE item_id = ?""",
        (json.dumps(confirmed, ensure_ascii=False), item_id),
    )
    conn.commit()
    return get_template(conn, item_id)
