"""Repository and guarded local paths for user-imported assets."""
import hashlib
import sqlite3
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ASSET_ROOT = DATA_DIR / "assets"


def workspace_asset_path(workspace_path: str) -> Path:
    key = hashlib.sha256(str(Path(workspace_path).resolve()).encode()).hexdigest()[:20]
    return ASSET_ROOT / key


def workspace_asset_dir(workspace_path: str) -> Path:
    path = workspace_asset_path(workspace_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative_storage_path(path: Path) -> str:
    return str(path.resolve().relative_to(DATA_DIR.resolve()))


def resolve_storage_path(storage_path: str) -> Path:
    path = (DATA_DIR / storage_path).resolve()
    if not path.is_relative_to(ASSET_ROOT.resolve()):
        raise ValueError("非法资产路径")
    return path


def create_asset(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, Any]:
    cursor = conn.execute(
        """INSERT INTO assets
           (item_id, asset_kind, original_name, storage_path, mime_type,
            content_hash, size_bytes) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["item_id"], data["asset_kind"], data["original_name"],
            data["storage_path"], data["mime_type"], data["content_hash"],
            data["size_bytes"],
        ),
    )
    return get_asset(conn, cursor.lastrowid)


def get_asset(conn: sqlite3.Connection, asset_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return dict(row) if row else None


def list_assets(conn: sqlite3.Connection, item_id: int) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(
        "SELECT * FROM assets WHERE item_id = ? ORDER BY id", (item_id,)
    ).fetchall()]
