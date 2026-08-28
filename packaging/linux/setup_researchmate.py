#!/usr/bin/env python3
"""Transparent check/plan/apply setup for the native Linux desktop host."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

SCHEMA_VERSION = 1


def xdg(variable: str, fallback: str) -> Path:
    return Path(os.environ.get(variable, Path.home() / fallback)).expanduser()


def run(command: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    output = (completed.stdout or completed.stderr).strip()
    return completed.returncode == 0, output


def check_environment(project: Path, conda: Path, environment: str) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []

    def add(name: str, ok: bool, required: bool, detail: str, remedy: str) -> None:
        checks.append({
            "name": name,
            "ok": ok,
            "required": required,
            "detail": detail,
            "remedy": "" if ok else remedy,
        })

    add("ResearchMate checkout", (project / "src/backend/desktop_runtime.py").is_file(), True,
        str(project), "Clone ResearchMate inside the Linux filesystem and select its absolute path")
    add("Conda-compatible executable", conda.is_file() and os.access(conda, os.X_OK), True,
        str(conda), "Install Conda/Mamba/Micromamba yourself and select its executable")
    python_ok = False
    packages_ok = False
    if conda.is_file():
        python_ok, _ = run([
            str(conda), "run", "-n", environment, "python", "-c",
            "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)",
        ])
        if python_ok:
            packages_ok, _ = run([
                str(conda), "run", "-n", environment, "python", "-c",
                "import fastapi,uvicorn,httpx,bs4,lxml,apscheduler,yaml,pydantic,multipart,PIL",
            ])
    add("Python 3.11 environment", python_ok, True, environment,
        f"Create it yourself: conda create -n {environment} python=3.11")
    add("Backend Python packages", packages_ok, True, "src/backend/requirements.txt",
        "Install with python -m pip install -r src/backend/requirements.txt")
    frontend = (project / "src/frontend/dist/index.html").is_file()
    add("Frontend production build", frontend, True, "src/frontend/dist/index.html",
        "Install Node/npm and run npm ci followed by npm run build in src/frontend")

    gtk_ok, gtk_output = run([
        "/usr/bin/python3", "-c",
        "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk",
    ]) if Path("/usr/bin/python3").is_file() else (False, "system Python missing")
    add("GTK 3 Python introspection", gtk_ok, True, gtk_output or "/usr/bin/python3 + PyGObject",
        "Install your distribution packages for Python 3 GObject introspection and GTK 3")
    webkit_script = (
        "import gi\n"
        "ok=False\n"
        "for v in ('4.1','4.0'):\n"
        " try:\n  gi.require_version('WebKit2',v); ok=True; break\n"
        " except ValueError: pass\n"
        "raise SystemExit(0 if ok else 1)\n"
        "from gi.repository import WebKit2\n"
    )
    webkit_ok, webkit_output = run(["/usr/bin/python3", "-c", webkit_script]) if gtk_ok else (False, "")
    add("WebKitGTK introspection", webkit_ok, True, webkit_output or "WebKit2 4.1 or 4.0",
        "Install your distribution WebKitGTK introspection package (4.1 or 4.0)")

    tesseract_ok, output = run([str(conda), "run", "-n", environment, "tesseract", "--version"]) \
        if conda.is_file() else (False, "")
    add("Tesseract OCR", tesseract_ok, False, output.splitlines()[0] if output else "optional",
        "Install Tesseract and the language packs you need, or leave OCR unavailable")
    return checks


def display_checks(checks: list[dict[str, object]]) -> None:
    for check in checks:
        state = "OK" if check["ok"] else ("MISSING" if check["required"] else "OPTIONAL")
        print(f"[{state}] {check['name']}: {check['detail']}")
        if check["remedy"]:
            print(f"  Remedy: {check['remedy']}")


def install(plan: dict[str, object], script_directory: Path) -> None:
    install_dir = Path(str(plan["install_directory"])).expanduser()
    config_path = Path(str(plan["config_path"])).expanduser()
    launcher_path = Path(str(plan["launcher_path"])).expanduser()
    desktop_path = Path(str(plan["desktop_entry_path"])).expanduser()
    host_source = script_directory / "host/researchmate_linux_host.py"
    uninstall_source = script_directory / "uninstall_researchmate.py"

    install_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="researchmate-linux-", dir=install_dir.parent))
    backup = install_dir.with_name(install_dir.name + ".previous")
    auxiliary_paths = (config_path, launcher_path, desktop_path)
    auxiliary_backup: dict[Path, tuple[bytes, int] | None] = {}
    for path in auxiliary_paths:
        auxiliary_backup[path] = (path.read_bytes(), path.stat().st_mode) if path.is_file() else None
    switched = False
    try:
        shutil.copy2(host_source, staging / host_source.name)
        shutil.copy2(uninstall_source, staging / uninstall_source.name)
        manifest = dict(plan)
        manifest["installed_at"] = datetime.now(timezone.utc).isoformat()
        (staging / "installation-manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if backup.exists():
            shutil.rmtree(backup)
        if install_dir.exists():
            install_dir.rename(backup)
        staging.rename(install_dir)
        switched = True

        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {
            "schema_version": 1,
            "project_path": plan["project_path"],
            "conda_executable": plan["conda_executable"],
            "conda_environment": plan["conda_environment"],
            "port": plan["port"],
        }
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        launcher_path.parent.mkdir(parents=True, exist_ok=True)
        launcher_path.write_text(
            "#!/bin/sh\nexec /usr/bin/python3 "
            + json.dumps(str(install_dir / host_source.name)) + ' "$@"\n', encoding="utf-8"
        )
        launcher_path.chmod(0o755)
        desktop_path.parent.mkdir(parents=True, exist_ok=True)
        desktop_path.write_text(
            "[Desktop Entry]\nType=Application\nName=ResearchMate\n"
            f"Exec={launcher_path}\nTerminal=false\nCategories=Office;Utility;\n",
            encoding="utf-8",
        )
        desktop_path.chmod(0o755)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        if switched and install_dir.exists():
            shutil.rmtree(install_dir)
        if backup.exists() and not install_dir.exists():
            backup.rename(install_dir)
        for path, snapshot in auxiliary_backup.items():
            if snapshot is None:
                if path.is_file() or path.is_symlink():
                    path.unlink()
            else:
                contents, mode = snapshot
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(contents)
                path.chmod(mode)
        raise


def main() -> int:
    script_directory = Path(__file__).resolve().parent
    repository = script_directory.parent.parent.resolve()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("check", "plan", "apply"), default="check")
    parser.add_argument("--plan", type=Path, default=repository / "researchmate-linux-install-plan.json")
    parser.add_argument("--project", type=Path, default=repository)
    parser.add_argument("--conda", type=Path, required=False)
    parser.add_argument("--environment", default="researchmate")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    approved = None
    if args.mode == "apply":
        if not args.plan.is_file():
            parser.error("install plan missing; run plan and review it first")
        approved = json.loads(args.plan.read_text(encoding="utf-8"))
        if approved.get("schema_version") != SCHEMA_VERSION:
            parser.error("unsupported install plan schema")
        args.project = Path(str(approved["project_path"]))
        args.conda = Path(str(approved["conda_executable"]))
        args.environment = str(approved["conda_environment"])
        args.port = int(approved["port"])

    if args.conda is None:
        candidates = [
            Path.home() / "miniconda3/condabin/conda",
            Path.home() / "miniforge3/condabin/conda",
            Path.home() / "mambaforge/condabin/conda",
            Path.home() / "anaconda3/condabin/conda",
        ]
        args.conda = next((item for item in candidates if item.is_file()), Path("/missing/conda"))

    checks = check_environment(args.project.resolve(), args.conda.resolve(), args.environment)
    display_checks(checks)
    failed = [check for check in checks if check["required"] and not check["ok"]]
    if args.mode == "check":
        return 2 if failed else 0

    config_home = xdg("XDG_CONFIG_HOME", ".config")
    data_home = xdg("XDG_DATA_HOME", ".local/share")
    plan = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_path": str(args.project.resolve()),
        "conda_executable": str(args.conda.resolve()),
        "conda_environment": args.environment,
        "port": args.port,
        "install_directory": str(data_home / "researchmate-desktop"),
        "config_path": str(config_home / "researchmate/desktop-config.json"),
        "launcher_path": str(Path.home() / ".local/bin/researchmate"),
        "desktop_entry_path": str(data_home / "applications/researchmate.desktop"),
        "owned_paths": [
            str(data_home / "researchmate-desktop"),
            str(config_home / "researchmate/desktop-config.json"),
            str(Path.home() / ".local/bin/researchmate"),
            str(data_home / "applications/researchmate.desktop"),
        ],
        "external_dependencies_not_owned": [
            "Linux operating system and desktop session", "system Python/PyGObject/GTK/WebKitGTK",
            "Git and ResearchMate checkout", "Conda-compatible tool and Python environment",
            "Node/npm and frontend packages", "Tesseract and language packs",
            "ResearchMate workspaces, assets, archives and keys",
        ],
        "checks": checks,
    }
    if args.mode == "plan":
        args.plan.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Plan written: {args.plan}")
        return 2 if failed else 0
    if failed:
        print("Required checks failed; no changes were applied", file=sys.stderr)
        return 2
    install(approved, script_directory)
    print("Installed native Linux ResearchMate desktop entry and command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
