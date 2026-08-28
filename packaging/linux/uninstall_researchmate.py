#!/usr/bin/env python3
"""Remove only files owned by the native Linux desktop integration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--remove-local-state", action="store_true")
    args = parser.parse_args()
    install_dir = Path(__file__).resolve().parent
    manifest_path = args.manifest or install_dir / "installation-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        parser.error("unsupported installation manifest")
    owned = [Path(str(item)).expanduser() for item in manifest.get("owned_paths", [])]
    for path in owned:
        if path == install_dir:
            continue
        if path.is_file() or path.is_symlink():
            path.unlink()
    if args.remove_local_state:
        optional_state = [
            Path(str(item)).expanduser()
            for item in manifest.get("optional_local_state", [])
        ]
        for path in optional_state:
            if path.exists():
                shutil.rmtree(path)
    shutil.rmtree(install_dir)
    print("Removed the Linux desktop host, command, desktop entry and config.")
    print("Source, environments, workspaces, assets, archives and keys were preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
