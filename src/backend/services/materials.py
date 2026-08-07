"""Application workflow for importing and organizing text materials."""
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from storage import items as item_repository
from storage import assets as asset_repository
from storage import accepted_extractions as accepted_extraction_repository
from storage.database import get_connection as get_main_connection
from storage.workspace import get_active_connection, get_active_path


CLASSIFIER_VERSION = "rules-v1"


@dataclass(frozen=True)
class Classification:
    item_type: str
    signals: list[str]


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    compact: list[str] = []
    for line in lines:
        if line or (compact and compact[-1]):
            compact.append(line)
    return "\n".join(compact).strip()


def classify_text(text: str) -> Classification:
    sample = text[:12000].lower()
    rules = {
        "debug": ("traceback", "exception", "stack trace", "报错", "错误信息", "error:"),
        "job": ("岗位职责", "任职要求", "招聘", "薪资", "工作地点", "job description"),
        "paper": ("abstract", "摘要", "arxiv", "doi:", "references", "关键词"),
    }
    scores = {
        item_type: [signal for signal in signals if signal in sample]
        for item_type, signals in rules.items()
    }
    winner = max(scores, key=lambda key: len(scores[key]))
    if not scores[winner]:
        return Classification("general", [])
    return Classification(winner, scores[winner])


def _derive_title(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "未命名资料")
    return first_line[:120]


def _derive_summary(text: str) -> str:
    one_line = re.sub(r"\s+", " ", text).strip()
    return one_line[:240]


def import_text_material(
    *,
    content_text: str,
    title: Optional[str] = None,
    item_type: str = "auto",
    source_url: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> tuple[dict, bool]:
    normalized = normalize_text(content_text)
    if not normalized:
        raise ValueError("资料正文不能为空")
    content_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    classification = classify_text(normalized)
    resolved_type = classification.item_type if item_type == "auto" else item_type
    normalized_tags = sorted({tag.strip() for tag in (tags or []) if tag.strip()})

    conn = get_active_connection()
    try:
        duplicate = item_repository.find_by_hash(conn, content_hash)
        if duplicate:
            return duplicate, False
        item = item_repository.create_item(conn, {
            "item_type": resolved_type,
            "title": (title or "").strip()[:300] or _derive_title(normalized),
            "content_text": normalized,
            "summary": _derive_summary(normalized),
            "source_kind": "text_import",
            "source_url": source_url,
            "status": "inbox",
            "tags": normalized_tags,
            "metadata": {
                "classification": {
                    "method": CLASSIFIER_VERSION,
                    "suggested_type": classification.item_type,
                    "signals": classification.signals,
                    "user_selected_type": None if item_type == "auto" else item_type,
                }
            },
            "content_hash": content_hash,
        })
        if item["item_type"] in {"debug", "job"}:
            from services.template_registry import extract_template_with_connection
            extract_template_with_connection(conn, item)
        _update_workspace_item_count(
            conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        )
        return item, True
    finally:
        conn.close()


def list_materials(**filters) -> dict:
    conn = get_active_connection()
    try:
        return item_repository.list_items(conn, **filters)
    finally:
        conn.close()


def get_material(item_id: int) -> Optional[dict]:
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if item:
            item["assets"] = asset_repository.list_assets(conn, item_id)
            from storage import templates as template_repository
            item["template"] = template_repository.get_template(conn, item_id)
            item["accepted_extractions"] = accepted_extraction_repository.get_for_item(
                conn, item_id
            )
        return item
    finally:
        conn.close()


def update_material(
    item_id: int,
    *,
    title: Optional[str] = None,
    item_type: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> Optional[dict]:
    normalized_title = title.strip() if title is not None else None
    if title is not None and not normalized_title:
        raise ValueError("标题不能为空")
    normalized_tags = None
    if tags is not None:
        normalized_tags = sorted({tag.strip() for tag in tags if tag.strip()})
    conn = get_active_connection()
    try:
        return item_repository.update_item(
            conn,
            item_id,
            title=normalized_title,
            item_type=item_type,
            status=status,
            tags=normalized_tags,
        )
    finally:
        conn.close()


def _update_workspace_item_count(item_count: int) -> None:
    main_conn = get_main_connection()
    try:
        main_conn.execute(
            "UPDATE workspaces SET item_count = ? WHERE db_path = ?",
            (item_count, get_active_path()),
        )
        main_conn.commit()
    finally:
        main_conn.close()
