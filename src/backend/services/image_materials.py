"""Import user images and run auditable local OCR."""
import hashlib
import uuid
from pathlib import Path
from typing import Any

from processors.image_decoder import decode_image
from processors.local_ocr import LocalOCRProcessor, PROCESSOR_NAME, PROCESSOR_VERSION
from services.materials import _update_workspace_item_count
from storage import assets as asset_repository
from storage import items as item_repository
from storage.workspace import get_active_connection


MAX_IMAGE_BYTES = 10 * 1024 * 1024


def import_image_material(*, filename: str, data: bytes, title: str | None = None) -> tuple[dict, bool]:
    if not data:
        raise ValueError("图片不能为空")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("图片不能超过 10 MB")
    decoded = decode_image(data)
    content_hash = hashlib.sha256(data).hexdigest()
    conn = get_active_connection()
    written_path: Path | None = None
    try:
        duplicate = item_repository.find_by_hash(conn, content_hash)
        if duplicate:
            duplicate["assets"] = asset_repository.list_assets(conn, duplicate["id"])
            return duplicate, False
        safe_original = Path(filename or f"image{decoded.suffix}").name[:255]
        workspace_path = _connection_workspace_path(conn)
        asset_dir = asset_repository.workspace_asset_dir(workspace_path)
        written_path = asset_dir / f"{uuid.uuid4().hex}{decoded.suffix}"
        with open(written_path, "xb") as output:
            output.write(data)
        cursor = conn.execute(
            """INSERT INTO items
               (item_type, title, content_text, summary, source_kind, status,
                tags_json, metadata_json, content_hash)
               VALUES ('general', ?, '', ?, 'image_import', 'inbox', '[]', '{}', ?)""",
            ((title or "").strip()[:300] or safe_original, "用户导入图片", content_hash),
        )
        item_id = cursor.lastrowid
        asset_repository.create_asset(conn, {
            "item_id": item_id, "asset_kind": "image", "original_name": safe_original,
            "storage_path": asset_repository.relative_storage_path(written_path),
            "mime_type": decoded.mime_type, "content_hash": content_hash,
            "size_bytes": len(data), "image_width": decoded.width,
            "image_height": decoded.height,
        })
        conn.commit()
        item = item_repository.get_item(conn, item_id)
        item["assets"] = asset_repository.list_assets(conn, item_id)
        _update_workspace_item_count(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])
        return item, True
    except Exception:
        conn.rollback()
        if written_path and written_path.exists():
            written_path.unlink()
        raise
    finally:
        conn.close()


def get_asset_file(asset_id: int) -> tuple[dict[str, Any], Path] | None:
    conn = get_active_connection()
    try:
        asset = asset_repository.get_asset(conn, asset_id)
        if not asset:
            return None
        path = _resolve_workspace_asset(asset["storage_path"], _connection_workspace_path(conn))
        if asset["mime_type"] not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("不支持的资产类型")
        if not path.is_file():
            raise FileNotFoundError("资产文件缺失")
        _validate_stored_asset(asset, path)
        return asset, path
    finally:
        conn.close()


def run_local_ocr(item_id: int, processor: Any | None = None) -> dict[str, Any] | None:
    """Create a new audited OCR run for each explicit user request."""
    conn = get_active_connection()
    try:
        item = item_repository.get_item(conn, item_id)
        if not item:
            return None
        assets = asset_repository.list_assets(conn, item_id)
        if not assets:
            raise ValueError("该资料没有可 OCR 的图片")
        asset = assets[0]
        run = item_repository.create_extraction_run(conn, {
            "item_id": item_id, "processor": PROCESSOR_NAME,
            "processor_version": PROCESSOR_VERSION, "run_kind": "ocr",
            "input_hash": asset["content_hash"], "input_scope": ["asset"],
            "input_item_ids": [item_id], "provider": "local", "model": "tesseract",
            "prompt_version": "none",
        })
        try:
            path = _resolve_workspace_asset(
                asset["storage_path"], _connection_workspace_path(conn)
            )
            _validate_stored_asset(asset, path)
            text = (processor or LocalOCRProcessor()).extract(str(path))
            result = {"text": text, "character_count": len(text)}
            return item_repository.complete_extraction_run(conn, run["id"], result=result)
        except Exception as exc:
            message = str(exc).strip()[:1000] or "本地 OCR 失败"
            item_repository.complete_extraction_run(conn, run["id"], error_message=message)
            raise RuntimeError(message) from exc
    finally:
        conn.close()


def _connection_workspace_path(conn) -> str:
    return conn.execute("PRAGMA database_list").fetchone()[2]


def _resolve_workspace_asset(storage_path: str, workspace_path: str) -> Path:
    path = asset_repository.resolve_storage_path(storage_path)
    workspace_root = asset_repository.workspace_asset_path(workspace_path).resolve()
    if not path.is_relative_to(workspace_root):
        raise ValueError("资产不属于当前工作区")
    return path


def _validate_stored_asset(asset: dict[str, Any], path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError("资产文件缺失")
    with open(path, "rb") as source:
        data = source.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES or len(data) != asset["size_bytes"]:
        raise ValueError("图片资产大小与导入记录不一致")
    if hashlib.sha256(data).hexdigest() != asset["content_hash"]:
        raise ValueError("图片资产哈希与导入记录不一致")
    decoded = decode_image(data)
    if decoded.mime_type != asset["mime_type"]:
        raise ValueError("图片资产格式与导入记录不一致")
    if asset.get("image_width") is not None and decoded.width != asset["image_width"]:
        raise ValueError("图片资产宽度与导入记录不一致")
    if asset.get("image_height") is not None and decoded.height != asset["image_height"]:
        raise ValueError("图片资产高度与导入记录不一致")
