"""Portable workspace export/import including guarded user image assets."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from processors.image_decoder import decode_image
from services.image_materials import MAX_IMAGE_BYTES
from storage import assets as asset_repository
from storage import workspace as workspace_storage


ARCHIVE_FORMAT = "researchmate-workspace"
ARCHIVE_VERSION = 1
MAX_DATABASE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ASSET_COUNT = 1_000
MAX_MEMBER_COUNT = MAX_ASSET_COUNT + 2
MAX_MANIFEST_BYTES = 1024 * 1024


class WorkspaceArchiveError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class WorkspaceExport:
    path: Path
    filename: str


@dataclass(frozen=True)
class WorkspaceImport:
    db_path: str
    name: str
    legacy_database_only: bool


def create_workspace_archive() -> WorkspaceExport:
    """Create a consistent SQLite snapshot plus every asset referenced by it."""
    source = workspace_storage.get_active_connection()
    snapshot_path: Path | None = None
    archive_path: Path | None = None
    try:
        workspace_path = Path(source.execute("PRAGMA database_list").fetchone()[2]).resolve()
        snapshot_fd, snapshot_name = tempfile.mkstemp(prefix="researchmate-", suffix=".db")
        os.close(snapshot_fd)
        snapshot_path = Path(snapshot_name)
        snapshot = sqlite3.connect(snapshot_path)
        try:
            source.backup(snapshot)
        finally:
            snapshot.close()
        if snapshot_path.stat().st_size > MAX_DATABASE_BYTES:
            raise WorkspaceArchiveError(
                "工作区数据库超过 100 MB，无法生成可移植归档", status_code=413
            )

        snapshot = sqlite3.connect(snapshot_path)
        snapshot.row_factory = sqlite3.Row
        try:
            asset_rows = [
                dict(row) for row in snapshot.execute("SELECT * FROM assets ORDER BY id")
            ]
        finally:
            snapshot.close()
        if len(asset_rows) > MAX_ASSET_COUNT:
            raise WorkspaceArchiveError(
                f"工作区图片超过 {MAX_ASSET_COUNT} 个，无法生成归档", status_code=413
            )
        estimated_size = snapshot_path.stat().st_size + sum(
            int(row["size_bytes"]) for row in asset_rows
        )
        if estimated_size > MAX_UNCOMPRESSED_BYTES:
            raise WorkspaceArchiveError("工作区归档解压后不能超过 512 MB", status_code=413)

        archive_fd, archive_name = tempfile.mkstemp(
            prefix="researchmate-workspace-", suffix=".zip"
        )
        os.close(archive_fd)
        archive_path = Path(archive_name)
        manifest_assets = []
        seen_storage_paths: set[str] = set()
        workspace_asset_root = asset_repository.workspace_asset_path(workspace_path).resolve()
        with zipfile.ZipFile(
            archive_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            archive.write(snapshot_path, "workspace.db")
            for row in asset_rows:
                storage_path = str(row["storage_path"])
                if storage_path in seen_storage_paths:
                    raise WorkspaceArchiveError("工作区存在重复资产路径，不能安全导出")
                seen_storage_paths.add(storage_path)
                path = asset_repository.resolve_storage_path(storage_path)
                if not path.is_relative_to(workspace_asset_root):
                    raise WorkspaceArchiveError("工作区资产路径越过当前工作区边界")
                data, decoded = _read_and_validate_image(row, path)
                archive_member = f"assets/{row['id']}{decoded.suffix}"
                archive.writestr(archive_member, data)
                manifest_assets.append({
                    "id": row["id"],
                    "path": archive_member,
                    "content_hash": row["content_hash"],
                    "size_bytes": row["size_bytes"],
                    "mime_type": row["mime_type"],
                    "image_width": decoded.width,
                    "image_height": decoded.height,
                })
            manifest = {
                "format": ARCHIVE_FORMAT,
                "version": ARCHIVE_VERSION,
                "database": "workspace.db",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "assets": manifest_assets,
            }
            archive.writestr(
                "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
            )
        if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise WorkspaceArchiveError("工作区归档文件不能超过 512 MB", status_code=413)
        safe_stem = _safe_workspace_stem(workspace_path.name)
        return WorkspaceExport(
            path=archive_path,
            filename=f"{safe_stem}.researchmate.zip",
        )
    except WorkspaceArchiveError:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
        raise
    except (OSError, sqlite3.DatabaseError, ValueError, zipfile.BadZipFile) as exc:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
        raise WorkspaceArchiveError(f"无法生成完整工作区归档：{str(exc)[:500]}") from exc
    finally:
        source.close()
        if snapshot_path is not None:
            snapshot_path.unlink(missing_ok=True)


def import_workspace_upload(upload_path: Path, original_name: str) -> WorkspaceImport:
    if upload_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise WorkspaceArchiveError("工作区归档文件不能超过 512 MB", status_code=413)
    if zipfile.is_zipfile(upload_path):
        return _import_archive(upload_path, original_name)
    if original_name.lower().endswith(".db"):
        return _import_legacy_database(upload_path, original_name)
    raise WorkspaceArchiveError("请上传 ResearchMate .zip 完整归档或无图片的旧 .db")


def remove_temporary_export(path: Path) -> None:
    path.unlink(missing_ok=True)


def validate_workspace_database(path: Path) -> None:
    try:
        if path.stat().st_size > MAX_DATABASE_BYTES:
            raise WorkspaceArchiveError("工作区数据库不能超过 100 MB", status_code=413)
        with path.open("rb") as uploaded:
            if uploaded.read(16) != b"SQLite format 3\x00":
                raise WorkspaceArchiveError("不是有效的 ResearchMate 工作区数据库")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA trusted_schema=OFF")
            quick_check = conn.execute("PRAGMA quick_check").fetchone()[0]
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            conn.close()
        if quick_check != "ok" or not {"papers", "crawl_tasks"}.issubset(tables):
            raise WorkspaceArchiveError("不是有效的 ResearchMate 工作区数据库")
    except WorkspaceArchiveError:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise WorkspaceArchiveError("不是有效的 ResearchMate 工作区数据库") from exc


def _import_archive(upload_path: Path, original_name: str) -> WorkspaceImport:
    with tempfile.TemporaryDirectory(prefix="researchmate-import-") as temp_name:
        temp_root = Path(temp_name)
        database_path = temp_root / "workspace.db"
        try:
            with zipfile.ZipFile(upload_path) as archive:
                members = _validate_archive_members(archive)
                manifest_data = _read_member(
                    archive, members["manifest.json"], MAX_MANIFEST_BYTES
                )
                manifest = _decode_manifest(manifest_data)
                manifest_assets = manifest["assets"]
                expected_members = {"manifest.json", "workspace.db"}
                expected_members.update(entry["path"] for entry in manifest_assets)
                if set(members) != expected_members:
                    raise WorkspaceArchiveError("归档包含缺失、重复或未声明的文件")
                _extract_member(
                    archive, members["workspace.db"], database_path, MAX_DATABASE_BYTES
                )
                validate_workspace_database(database_path)
                workspace_storage._init_workspace_db(str(database_path))
                conn = sqlite3.connect(database_path)
                conn.row_factory = sqlite3.Row
                try:
                    rows = [dict(row) for row in conn.execute("SELECT * FROM assets ORDER BY id")]
                    plans = _validate_imported_assets(
                        archive, members, manifest_assets, rows
                    )
                    result = _install_imported_workspace(
                        conn, database_path, original_name, plans
                    )
                finally:
                    conn.close()
                return result
        except WorkspaceArchiveError:
            raise
        except (OSError, sqlite3.DatabaseError, ValueError, zipfile.BadZipFile) as exc:
            raise WorkspaceArchiveError(f"无法导入工作区完整归档：{str(exc)[:500]}") from exc


def _import_legacy_database(upload_path: Path, original_name: str) -> WorkspaceImport:
    with tempfile.TemporaryDirectory(prefix="researchmate-legacy-") as temp_name:
        database_path = Path(temp_name) / "workspace.db"
        shutil.copyfile(upload_path, database_path)
        validate_workspace_database(database_path)
        workspace_storage._init_workspace_db(str(database_path))
        conn = sqlite3.connect(database_path)
        try:
            asset_count = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        finally:
            conn.close()
        if asset_count:
            raise WorkspaceArchiveError(
                "旧 .db 含图片记录但不含图片文件，请从原工作区导出完整 .zip 归档"
            )
        result = _install_imported_workspace(
            None, database_path, original_name, []
        )
        return WorkspaceImport(
            db_path=result.db_path,
            name=result.name,
            legacy_database_only=True,
        )


def _install_imported_workspace(
    conn: sqlite3.Connection | None,
    database_path: Path,
    original_name: str,
    plans: list[tuple[dict, bytes, object]],
) -> WorkspaceImport:
    workspace_dir = workspace_storage.WORKSPACE_DIR
    workspace_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_workspace_stem(original_name)
    destination = _reserve_workspace_path(workspace_dir, stem)
    final_asset_dir = asset_repository.workspace_asset_path(destination)
    temp_asset_dir = final_asset_dir.with_name(
        f".{final_asset_dir.name}.importing-{uuid.uuid4().hex}"
    )
    temp_database = destination.with_name(
        f".{destination.name}.importing-{uuid.uuid4().hex}"
    )
    installed_assets = False
    try:
        if plans:
            temp_asset_dir.mkdir(parents=True, exist_ok=False)
            for row, data, decoded in plans:
                filename = f"{row['id']}-{row['content_hash'][:12]}{decoded.suffix}"
                temporary_file = temp_asset_dir / filename
                with temporary_file.open("xb") as output:
                    output.write(data)
                final_path = final_asset_dir / filename
                storage_path = asset_repository.relative_storage_path(final_path)
                conn.execute(
                    """UPDATE assets
                       SET storage_path = ?, image_width = ?, image_height = ?
                       WHERE id = ?""",
                    (storage_path, decoded.width, decoded.height, row["id"]),
                )
            conn.commit()
        if database_path.stat().st_size > MAX_DATABASE_BYTES:
            raise WorkspaceArchiveError("迁移后的工作区数据库超过 100 MB", status_code=413)
        if conn is None:
            shutil.copyfile(database_path, temp_database)
        else:
            portable_database = sqlite3.connect(temp_database)
            try:
                conn.backup(portable_database)
            finally:
                portable_database.close()
        if plans:
            final_asset_dir.parent.mkdir(parents=True, exist_ok=True)
            temp_asset_dir.rename(final_asset_dir)
            installed_assets = True
        os.replace(temp_database, destination)
        return WorkspaceImport(
            db_path=str(destination), name=destination.stem, legacy_database_only=False
        )
    except Exception:
        temp_database.unlink(missing_ok=True)
        if temp_asset_dir.exists():
            shutil.rmtree(temp_asset_dir)
        if installed_assets and final_asset_dir.exists():
            shutil.rmtree(final_asset_dir)
        destination.unlink(missing_ok=True)
        raise


def _validate_archive_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBER_COUNT:
        raise WorkspaceArchiveError("归档文件数量超过允许上限")
    members: dict[str, zipfile.ZipInfo] = {}
    total_size = 0
    for info in infos:
        name = info.filename
        pure_path = PurePosixPath(name)
        mode = info.external_attr >> 16
        if (
            not name
            or "\\" in name
            or pure_path.is_absolute()
            or ".." in pure_path.parts
            or pure_path.as_posix() != name
            or info.is_dir()
            or stat.S_ISLNK(mode)
        ):
            raise WorkspaceArchiveError("归档包含非法路径或符号链接")
        if info.flag_bits & 0x1 or info.compress_type not in {
            zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED,
        }:
            raise WorkspaceArchiveError("归档包含加密或不支持的压缩成员")
        if name in members:
            raise WorkspaceArchiveError("归档包含重复文件名")
        members[name] = info
        total_size += info.file_size
        if total_size > MAX_UNCOMPRESSED_BYTES:
            raise WorkspaceArchiveError("工作区归档解压后不能超过 512 MB", status_code=413)
    if "manifest.json" not in members or "workspace.db" not in members:
        raise WorkspaceArchiveError("归档缺少 manifest.json 或 workspace.db")
    if members["workspace.db"].file_size > MAX_DATABASE_BYTES:
        raise WorkspaceArchiveError("工作区数据库不能超过 100 MB", status_code=413)
    return members


def _decode_manifest(data: bytes) -> dict:
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceArchiveError("归档 manifest 无效") from exc
    if not isinstance(manifest, dict):
        raise WorkspaceArchiveError("归档 manifest 无效")
    if (
        manifest.get("format") != ARCHIVE_FORMAT
        or manifest.get("version") != ARCHIVE_VERSION
        or manifest.get("database") != "workspace.db"
        or not isinstance(manifest.get("assets"), list)
    ):
        raise WorkspaceArchiveError("不支持的 ResearchMate 工作区归档版本")
    if len(manifest["assets"]) > MAX_ASSET_COUNT:
        raise WorkspaceArchiveError("归档图片数量超过允许上限", status_code=413)
    seen_ids = set()
    seen_paths = set()
    for entry in manifest["assets"]:
        if not isinstance(entry, dict):
            raise WorkspaceArchiveError("归档资产清单无效")
        asset_id = entry.get("id")
        path = entry.get("path")
        if (
            not isinstance(asset_id, int)
            or not isinstance(path, str)
            or not path.startswith("assets/")
            or asset_id in seen_ids
            or path in seen_paths
        ):
            raise WorkspaceArchiveError("归档资产清单包含无效或重复项")
        seen_ids.add(asset_id)
        seen_paths.add(path)
    return manifest


def _validate_imported_assets(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    manifest_assets: list[dict],
    rows: list[dict],
) -> list[tuple[dict, bytes, object]]:
    manifest_by_id = {entry["id"]: entry for entry in manifest_assets}
    rows_by_id = {row["id"]: row for row in rows}
    if set(manifest_by_id) != set(rows_by_id):
        raise WorkspaceArchiveError("归档资产与数据库记录不一致")
    plans = []
    for asset_id, row in rows_by_id.items():
        entry = manifest_by_id[asset_id]
        for field in ("content_hash", "size_bytes", "mime_type"):
            if entry.get(field) != row.get(field):
                raise WorkspaceArchiveError("归档 manifest 与数据库资产事实不一致")
        info = members[entry["path"]]
        if info.file_size > MAX_IMAGE_BYTES:
            raise WorkspaceArchiveError("归档中的单张图片不能超过 10 MB", status_code=413)
        data = _read_member(archive, info, MAX_IMAGE_BYTES)
        decoded = _validate_image_data(row, data)
        if (
            entry.get("image_width") != decoded.width
            or entry.get("image_height") != decoded.height
        ):
            raise WorkspaceArchiveError("归档 manifest 的图片尺寸与完整解码不一致")
        plans.append((row, data, decoded))
    return plans


def _read_and_validate_image(row: dict, path: Path):
    if not path.is_file():
        raise WorkspaceArchiveError("工作区图片资产缺失，不能生成完整归档")
    try:
        with path.open("rb") as source:
            data = source.read(MAX_IMAGE_BYTES + 1)
    except OSError as exc:
        raise WorkspaceArchiveError("无法读取工作区图片资产") from exc
    return data, _validate_image_data(row, data)


def _validate_image_data(row: dict, data: bytes):
    if row.get("asset_kind") != "image":
        raise WorkspaceArchiveError("归档只支持当前的用户图片资产")
    if len(data) > MAX_IMAGE_BYTES or len(data) != row.get("size_bytes"):
        raise WorkspaceArchiveError("图片资产大小与数据库记录不一致")
    if hashlib.sha256(data).hexdigest() != row.get("content_hash"):
        raise WorkspaceArchiveError("图片资产哈希与数据库记录不一致")
    try:
        decoded = decode_image(data)
    except ValueError as exc:
        raise WorkspaceArchiveError(str(exc)) from exc
    if decoded.mime_type != row.get("mime_type"):
        raise WorkspaceArchiveError("图片资产格式与数据库记录不一致")
    if row.get("image_width") is not None and row["image_width"] != decoded.width:
        raise WorkspaceArchiveError("图片资产宽度与数据库记录不一致")
    if row.get("image_height") is not None and row["image_height"] != decoded.height:
        raise WorkspaceArchiveError("图片资产高度与数据库记录不一致")
    return decoded


def _read_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int
) -> bytes:
    chunks = bytearray()
    with archive.open(info) as source:
        while chunk := source.read(min(1024 * 1024, limit + 1 - len(chunks))):
            chunks.extend(chunk)
            if len(chunks) > limit:
                raise WorkspaceArchiveError("归档成员解压后超过允许大小", status_code=413)
    return bytes(chunks)


def _extract_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, destination: Path, limit: int
) -> None:
    size = 0
    with archive.open(info) as source, destination.open("xb") as output:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise WorkspaceArchiveError("工作区数据库不能超过 100 MB", status_code=413)
            output.write(chunk)


def _safe_workspace_stem(filename: str) -> str:
    name = Path(filename).name
    for suffix in (".zip", ".db"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
    if name.lower().endswith(".researchmate"):
        name = name[: -len(".researchmate")]
    safe = re.sub(r"[^\w.-]+", "_", name, flags=re.UNICODE).strip("._")[:80]
    return safe or "imported_workspace"


def _reserve_workspace_path(workspace_dir: Path, stem: str) -> Path:
    candidate = workspace_dir / f"{stem}.db"
    index = 1
    while True:
        try:
            descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
        except FileExistsError:
            candidate = workspace_dir / f"{stem}_{index}.db"
            index += 1
            continue
        if asset_repository.workspace_asset_path(candidate).exists():
            candidate.unlink(missing_ok=True)
            candidate = workspace_dir / f"{stem}_{index}.db"
            index += 1
            continue
        return candidate
