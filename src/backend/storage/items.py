"""Repository for generic material items."""
import json
import sqlite3
from typing import Any, Optional

def _decode(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    item = dict(row)
    for source, target, fallback in (
        ("tags_json", "tags", []),
        ("metadata_json", "metadata", {}),
    ):
        raw = item.pop(source, None)
        try:
            item[target] = json.loads(raw) if raw else fallback
        except (json.JSONDecodeError, TypeError):
            item[target] = fallback
    return item


def find_by_hash(conn: sqlite3.Connection, content_hash: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM items WHERE content_hash = ?", (content_hash,)
    ).fetchone()
    return _decode(row)


def create_item(
    conn: sqlite3.Connection, data: dict[str, Any], *, commit: bool = True
) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO items
           (item_type, title, content_text, summary, source_kind, source_url,
            status, tags_json, metadata_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["item_type"], data["title"], data["content_text"], data["summary"],
            data["source_kind"], data.get("source_url"), data["status"],
            json.dumps(data.get("tags", []), ensure_ascii=False),
            json.dumps(data.get("metadata", {}), ensure_ascii=False),
            data["content_hash"],
        ),
    )
    if commit:
        conn.commit()
    return get_item(conn, cursor.lastrowid)


def get_item(conn: sqlite3.Connection, item_id: int) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return _decode(row)


def list_items(
    conn: sqlite3.Connection,
    *,
    query: str | None = None,
    item_type: str | None = None,
    status: str | None = None,
    debug_error: str | None = None,
    job_company: str | None = None,
    job_role: str | None = None,
    job_application_status: str | None = None,
    include_accepted_extractions: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    clauses = ["1 = 1"]
    params: list[Any] = []
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_clauses = ["title LIKE ? ESCAPE '\\'", "content_text LIKE ? ESCAPE '\\'"]
        params.extend([f"%{escaped}%", f"%{escaped}%"])
        if include_accepted_extractions:
            search_clauses.append(
                "EXISTS (SELECT 1 FROM accepted_extractions ae "
                "WHERE ae.item_id = items.id AND ae.text_value LIKE ? ESCAPE '\\')"
            )
            params.append(f"%{escaped}%")
        clauses.append(f"({' OR '.join(search_clauses)})")
    if item_type:
        clauses.append("item_type = ?")
        params.append(item_type)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if debug_error:
        escaped = debug_error.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append(
            "items.item_type = 'debug' AND lower(COALESCE("
            "NULLIF(json_extract(item_template_data.confirmed_json, '$.error'), ''), "
            "json_extract(item_template_data.extracted_json, '$.error'), '')) "
            "LIKE lower(?) ESCAPE '\\'"
        )
        params.append(f"%{escaped}%")
    for field, value in (
        ("company", job_company),
        ("role", job_role),
        ("application_status", job_application_status),
    ):
        if not value:
            continue
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append(
            "items.item_type = 'job' AND item_template_data.template_key = 'job' "
            "AND lower(COALESCE(NULLIF(json_extract("
            f"item_template_data.confirmed_json, '$.{field}'), ''), "
            f"json_extract(item_template_data.extracted_json, '$.{field}'), '')) "
            "LIKE lower(?) ESCAPE '\\'"
        )
        params.append(f"%{escaped}%")

    where = " AND ".join(clauses)
    source = "items LEFT JOIN item_template_data ON item_template_data.item_id = items.id"
    total = conn.execute(f"SELECT COUNT(*) FROM {source} WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT items.*, EXISTS(SELECT 1 FROM accepted_extractions ae "
        f"WHERE ae.item_id = items.id) AS has_accepted_extraction "
        f"FROM {source} WHERE {where} ORDER BY items.created_at DESC, items.id DESC LIMIT ? OFFSET ?",
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return {
        "items": [_decode(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def list_all_except(conn: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM items WHERE id != ?", (item_id,)).fetchall()
    return [_decode(row) for row in rows]


def replace_similarity_relations(
    conn: sqlite3.Connection, item_id: int, matches: list[dict[str, Any]]
) -> None:
    conn.execute(
        "DELETE FROM item_relations WHERE from_item_id = ? AND relation_type = 'near_text'",
        (item_id,),
    )
    for match in matches:
        conn.execute(
            """INSERT INTO item_relations
               (from_item_id, to_item_id, relation_type, score, evidence_json)
               VALUES (?, ?, 'near_text', ?, ?)""",
            (item_id, match["item"]["id"], match["score"], json.dumps(match["evidence"], ensure_ascii=False)),
        )
    conn.commit()


def update_item(
    conn: sqlite3.Connection,
    item_id: int,
    *,
    title: str | None = None,
    item_type: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
) -> Optional[dict[str, Any]]:
    fields = []
    params: list[Any] = []
    for column, value in (("title", title), ("item_type", item_type), ("status", status)):
        if value is not None:
            fields.append(f"{column} = ?")
            params.append(value)
    if tags is not None:
        fields.append("tags_json = ?")
        params.append(json.dumps(tags, ensure_ascii=False))
    if not fields:
        return get_item(conn, item_id)
    fields.append("updated_at = datetime('now')")
    params.append(item_id)
    conn.execute(f"UPDATE items SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    return get_item(conn, item_id)


def _decode_run(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    run = dict(row)
    for source, target, fallback in (
        ("input_scope_json", "input_scope", []),
        ("input_item_ids_json", "input_item_ids", []),
        ("result_json", "result", None),
    ):
        raw = run.pop(source, None)
        try:
            run[target] = json.loads(raw) if raw else fallback
        except (json.JSONDecodeError, TypeError):
            run[target] = fallback
    return run


def find_reusable_run(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    run_kind: str,
    input_hash: str,
    processor_version: str,
    prompt_version: str,
    provider: str,
    model: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        """SELECT * FROM extraction_runs
           WHERE item_id = ? AND run_kind = ? AND input_hash = ?
             AND processor_version = ? AND prompt_version = ?
             AND provider = ? AND model = ? AND status = 'succeeded'
           ORDER BY id DESC LIMIT 1""",
        (
            item_id, run_kind, input_hash, processor_version, prompt_version,
            provider, model,
        ),
    ).fetchone()
    return _decode_run(row)


def create_extraction_run(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO extraction_runs
           (item_id, processor, processor_version, run_kind, status, input_hash,
            input_scope_json, input_item_ids_json, provider, model, prompt_version)
           VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?)""",
        (
            data["item_id"], data["processor"], data["processor_version"],
            data["run_kind"], data["input_hash"],
            json.dumps(data["input_scope"], ensure_ascii=False),
            json.dumps(data.get("input_item_ids", [data["item_id"]])), data["provider"], data["model"],
            data["prompt_version"],
        ),
    )
    conn.commit()
    return get_extraction_run(conn, cursor.lastrowid)


def get_extraction_run(
    conn: sqlite3.Connection, run_id: int
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM extraction_runs WHERE id = ?", (run_id,)
    ).fetchone()
    return _decode_run(row)


def complete_extraction_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = "succeeded" if error_message is None else "failed"
    conn.execute(
        """UPDATE extraction_runs
           SET status = ?, result_json = ?, error_message = ?,
               provider_model = ?, input_tokens = ?, output_tokens = ?,
               duration_ms = ?, request_id = ?
           WHERE id = ?""",
        (
            status,
            json.dumps(result, ensure_ascii=False) if result is not None else None,
            error_message,
            provider_metadata.get("provider_model") if provider_metadata else None,
            provider_metadata.get("input_tokens") if provider_metadata else None,
            provider_metadata.get("output_tokens") if provider_metadata else None,
            provider_metadata.get("duration_ms") if provider_metadata else None,
            provider_metadata.get("request_id") if provider_metadata else None,
            run_id,
        ),
    )
    conn.commit()
    return get_extraction_run(conn, run_id)


def fail_running_extraction_runs(
    conn: sqlite3.Connection,
    error_message: str = "上次应用退出时资料处理被中断，请重新执行",
) -> int:
    cursor = conn.execute(
        """UPDATE extraction_runs
           SET status = 'failed', error_message = ?
           WHERE status = 'running'""",
        (error_message,),
    )
    conn.commit()
    return cursor.rowcount


def list_extraction_runs(
    conn: sqlite3.Connection, item_id: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM extraction_runs WHERE item_id = ? ORDER BY id DESC",
        (item_id,),
    ).fetchall()
    return [_decode_run(row) for row in rows]


def list_comparison_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM extraction_runs WHERE run_kind = 'compare' ORDER BY id DESC"
    ).fetchall()
    return [_decode_run(row) for row in rows]


def get_items_by_ids(conn: sqlite3.Connection, item_ids: list[int]) -> list[dict[str, Any]]:
    if not item_ids:
        return []
    placeholders = ",".join("?" for _ in item_ids)
    rows = conn.execute(
        f"SELECT * FROM items WHERE id IN ({placeholders})", item_ids
    ).fetchall()
    by_id = {row["id"]: _decode(row) for row in rows}
    return [by_id[item_id] for item_id in item_ids if item_id in by_id]
