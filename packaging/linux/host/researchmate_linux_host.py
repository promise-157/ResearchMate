#!/usr/bin/env python3
"""User-scoped GTK/WebKit desktop owner for a Linux ResearchMate checkout."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

CONFIG_SCHEMA_VERSION = 1
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def xdg_path(variable: str, fallback: str, *parts: str) -> Path:
    root = Path(os.environ.get(variable, Path.home() / fallback)).expanduser()
    return root.joinpath(*parts)


def default_config_path() -> Path:
    return xdg_path("XDG_CONFIG_HOME", ".config", "researchmate", "desktop-config.json")


def load_config(path: Path) -> dict[str, object]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read desktop config {path}: {error}") from error
    if config.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError("Unsupported desktop config schema")
    project = config.get("project_path")
    conda = config.get("conda_executable")
    environment = config.get("conda_environment")
    port = config.get("port")
    if not isinstance(project, str) or not Path(project).is_absolute():
        raise ValueError("project_path must be an absolute Linux path")
    if not isinstance(conda, str) or not Path(conda).is_absolute():
        raise ValueError("conda_executable must be an absolute Linux path")
    if not isinstance(environment, str) or not SAFE_NAME.fullmatch(environment):
        raise ValueError("conda_environment contains unsupported characters")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    return config


def supervisor_command(
    config: dict[str, object], instance_id: str,
    supervisor_script: str = "src/backend/desktop_runtime.py",
) -> list[str]:
    return [
        str(config["conda_executable"]),
        "run",
        "--no-capture-output",
        "-n",
        str(config["conda_environment"]),
        "python",
        supervisor_script,
        "--instance-id",
        instance_id,
        "--port",
        str(config["port"]),
    ]


class SingleInstance:
    def __init__(self, activate) -> None:
        runtime = xdg_path("XDG_RUNTIME_DIR", ".cache", "researchmate")
        runtime.mkdir(parents=True, exist_ok=True)
        self._lock_file = (runtime / "desktop.lock").open("a+")
        self.socket_path = runtime / "desktop.sock"
        self.primary = False
        self._server: socket.socket | None = None
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.primary = True
        except BlockingIOError:
            return
        try:
            self.socket_path.unlink(missing_ok=True)
            self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            self._server.listen(1)
            threading.Thread(target=self._listen, args=(activate,), daemon=True).start()
        except Exception:
            self.close()
            raise

    def activate_existing(self) -> bool:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(2)
                client.connect(str(self.socket_path))
                client.sendall(b"activate\n")
            return True
        except OSError:
            return False

    def _listen(self, activate) -> None:
        while self._server is not None:
            try:
                connection, _ = self._server.accept()
                with connection:
                    if connection.recv(64).strip() == b"activate":
                        activate()
            except OSError:
                return

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        if self.primary:
            self.socket_path.unlink(missing_ok=True)
        self._lock_file.close()


class BackendOwner:
    def __init__(self, config: dict[str, object], on_ready, on_failed,
                 supervisor_script: str = "src/backend/desktop_runtime.py") -> None:
        self.config = config
        self.instance_id = uuid.uuid4().hex
        self.on_ready = on_ready
        self.on_failed = on_failed
        self.process: subprocess.Popen[str] | None = None
        self.process_group_id: int | None = None
        self.stopping = False
        self.supervisor_script = supervisor_script
        self.log_path = xdg_path("XDG_STATE_HOME", ".local/state", "researchmate", "desktop.log")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        project = str(self.config["project_path"])
        self.process = subprocess.Popen(
            supervisor_command(self.config, self.instance_id, self.supervisor_script),
            cwd=project,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._read_events, daemon=True).start()
        threading.Thread(target=self._read_logs, daemon=True).start()
        threading.Thread(target=self._wait_until_ready, daemon=True).start()

    def _read_events(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("instance_id") != self.instance_id:
                continue
            if event.get("event") == "backend_spawned":
                pgid = event.get("process_group_id")
                if isinstance(pgid, int) and pgid > 1:
                    self.process_group_id = pgid
            elif event.get("event") == "startup_failed":
                self.on_failed(str(event.get("message") or "Backend startup failed"))

    def _read_logs(self) -> None:
        assert self.process and self.process.stderr
        with self.log_path.open("a", encoding="utf-8") as log:
            for line in self.process.stderr:
                sanitized = re.sub(r"(?i)(api[_-]?key|authorization)(\s*[:=]\s*)\S+", r"\1\2[redacted]", line)
                log.write(sanitized)
                log.flush()

    def _wait_until_ready(self) -> None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 45
        url = f"http://127.0.0.1:{self.config['port']}/api/health"
        while time.monotonic() < deadline:
            if self.process and self.process.poll() is not None:
                if not self.stopping:
                    self.on_failed("Backend exited before becoming ready")
                return
            try:
                with opener.open(url, timeout=2) as response:
                    if response.status == 200:
                        self.on_ready(f"http://127.0.0.1:{self.config['port']}/")
                        return
            except OSError:
                time.sleep(0.25)
        self.on_failed("Backend health check timed out")

    def stop(self) -> None:
        if not self.process or self.stopping:
            return
        self.stopping = True
        if self.process.poll() is None and self.process.stdin:
            try:
                frame = json.dumps({
                    "command": "shutdown",
                    "instance_id": self.instance_id,
                    "reason": "window_close",
                })
                self.process.stdin.write(frame + "\n")
                self.process.stdin.flush()
                self.process.stdin.close()
            except OSError:
                pass
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            if self.process_group_id and self.process_group_id > 1:
                try:
                    os.killpg(self.process_group_id, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.process.kill()
            self.process.wait(timeout=5)


def load_gtk():
    import gi

    gi.require_version("Gtk", "3.0")
    webkit_version = None
    for candidate in ("4.1", "4.0"):
        try:
            gi.require_version("WebKit2", candidate)
            webkit_version = candidate
            break
        except ValueError:
            continue
    if webkit_version is None:
        raise RuntimeError("WebKitGTK 4.1 or 4.0 introspection data is required")
    from gi.repository import GLib, Gtk, WebKit2

    return GLib, Gtk, WebKit2


def run_window(config: dict[str, object], supervisor_script: str) -> int:
    GLib, Gtk, WebKit2 = load_gtk()
    window = Gtk.Window(title="ResearchMate")
    window.set_default_size(1280, 820)
    stack = Gtk.Stack()
    status = Gtk.Label(label="Starting ResearchMate backend...")
    webview = WebKit2.WebView()
    stack.add_named(status, "status")
    stack.add_named(webview, "webview")
    window.add(stack)
    window.show_all()
    stack.set_visible_child_name("status")

    def activate() -> None:
        GLib.idle_add(lambda: (window.present(), False)[1])

    instance = SingleInstance(activate)
    if not instance.primary:
        activated = instance.activate_existing()
        instance.close()
        return 0 if activated else 2

    def ready(url: str) -> None:
        def update() -> bool:
            webview.load_uri(url)
            stack.set_visible_child_name("webview")
            return False
        GLib.idle_add(update)

    def failed(message: str) -> None:
        def update() -> bool:
            status.set_text(message + "\nSee ~/.local/state/researchmate/desktop.log")
            stack.set_visible_child_name("status")
            return False
        GLib.idle_add(update)

    owner = BackendOwner(config, ready, failed, supervisor_script)
    owner.start()

    def closing(*_args) -> bool:
        owner.stop()
        instance.close()
        Gtk.main_quit()
        return False

    window.connect("delete-event", closing)
    try:
        Gtk.main()
    finally:
        owner.stop()
        instance.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--test-supervisor-script", choices=(
        "tests/fixtures/desktop_runtime_harness.py",
    ))
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.check_config:
            print("Linux desktop config is valid")
            return 0
        supervisor_script = args.test_supervisor_script or "src/backend/desktop_runtime.py"
        return run_window(config, supervisor_script)
    except (ValueError, RuntimeError, OSError) as error:
        print(f"ResearchMate desktop error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
