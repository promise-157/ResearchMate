"""Private WSL process supervisor for the Windows desktop host.

The desktop host owns this process through redirected stdin/stdout.  Protocol
events are JSON lines on stdout; backend logs are forwarded to stderr.  This is
not an HTTP API and is not intended to be started as a persistent service.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, TextIO


BACKEND_DIR = Path(__file__).resolve().parent
INSTANCE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
DEFAULT_GRACEFUL_TIMEOUT_SECONDS = 15.0
DEFAULT_STARTUP_PORT_TIMEOUT_SECONDS = 8.0
RUNTIME_INFO_ENV = "RESEARCHMATE_RUNTIME_INFO_JSON"


class DesktopRuntimeError(RuntimeError):
    """A stable local lifecycle error safe to send to the desktop host."""


def _validate_runtime_info_json(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) > 32_768:
        raise DesktopRuntimeError("桌面安装信息超过允许大小")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DesktopRuntimeError("桌面安装信息不是有效 JSON") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise DesktopRuntimeError("桌面安装信息版本无效")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def port_is_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, port))
        return True
    except OSError:
        return False


def _configure_child_process() -> None:
    """Create a process group and ask Linux to terminate it when we disappear."""
    os.setsid()
    libc = ctypes.CDLL(None, use_errno=True)
    pr_set_pdeathsig = 1
    if libc.prctl(pr_set_pdeathsig, signal.SIGTERM) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGTERM)


def _default_backend_command() -> list[str]:
    return [sys.executable, str(BACKEND_DIR / "run.py"), "--no-browser"]


class DesktopRuntimeSupervisor:
    def __init__(
        self,
        *,
        instance_id: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        graceful_timeout: float = DEFAULT_GRACEFUL_TIMEOUT_SECONDS,
        stdin: TextIO = sys.stdin,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
        backend_command: list[str] | None = None,
        runtime_info_json: str | None = None,
        startup_port_timeout: float = DEFAULT_STARTUP_PORT_TIMEOUT_SECONDS,
        process_factory: Any = subprocess.Popen,
    ) -> None:
        if not INSTANCE_ID_RE.fullmatch(instance_id):
            raise DesktopRuntimeError("桌面运行实例标识无效")
        if host != "127.0.0.1":
            raise DesktopRuntimeError("桌面运行只允许监听 127.0.0.1")
        if not 1 <= port <= 65535:
            raise DesktopRuntimeError("桌面运行端口无效")
        if graceful_timeout <= 0:
            raise DesktopRuntimeError("优雅退出等待时间必须大于零")
        if startup_port_timeout < 0:
            raise DesktopRuntimeError("启动端口等待时间不能为负数")

        self.instance_id = instance_id
        self.host = host
        self.port = port
        self.graceful_timeout = graceful_timeout
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.backend_command = backend_command or _default_backend_command()
        self.runtime_info_json = _validate_runtime_info_json(runtime_info_json)
        self.startup_port_timeout = startup_port_timeout
        self.process_factory = process_factory
        self.process: subprocess.Popen[str] | None = None
        self.process_group_id: int | None = None
        self._commands: queue.Queue[dict[str, Any]] = queue.Queue()
        self._shutdown_requested = False
        self._forced = False

    def emit(self, event: str, **payload: Any) -> None:
        message = {"event": event, "instance_id": self.instance_id, **payload}
        self.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.stdout.flush()

    def _read_commands(self) -> None:
        while True:
            line = self.stdin.readline()
            if line == "":
                self._commands.put({"command": "shutdown", "reason": "host_eof"})
                return
            try:
                message = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                self._commands.put({"command": "invalid"})
                continue
            if not isinstance(message, dict):
                self._commands.put({"command": "invalid"})
                continue
            self._commands.put(message)

    def _install_signal_handlers(self) -> None:
        def request_shutdown(signum: int, _frame: Any) -> None:
            self._commands.put({"command": "shutdown", "reason": f"signal_{signum}"})

        signal.signal(signal.SIGTERM, request_shutdown)
        signal.signal(signal.SIGINT, request_shutdown)

    def start_backend(self) -> None:
        deadline = time.monotonic() + self.startup_port_timeout
        while not port_is_available(self.host, self.port) and time.monotonic() < deadline:
            time.sleep(0.1)
        if not port_is_available(self.host, self.port):
            raise DesktopRuntimeError(
                f"本机端口 {self.port} 已被占用；桌面宿主不会复用或终止未知进程"
            )
        child_environment = os.environ.copy()
        if self.runtime_info_json:
            child_environment[RUNTIME_INFO_ENV] = self.runtime_info_json
        else:
            child_environment.pop(RUNTIME_INFO_ENV, None)
        self.process = self.process_factory(
            self.backend_command,
            cwd=str(BACKEND_DIR),
            stdin=subprocess.DEVNULL,
            stdout=self.stderr,
            stderr=self.stderr,
            text=True,
            env=child_environment,
            preexec_fn=_configure_child_process,
        )
        self.process_group_id = os.getpgid(self.process.pid)
        self.emit(
            "backend_spawned",
            pid=self.process.pid,
            process_group_id=self.process_group_id,
            port=self.port,
        )

    def _request_backend_stop(self, reason: str) -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self.emit("shutdown_started", reason=reason)
        if self.process is None or self.process.poll() is not None:
            return
        assert self.process_group_id is not None
        os.killpg(self.process_group_id, signal.SIGTERM)

    def _finish_backend_stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        try:
            self.process.wait(timeout=self.graceful_timeout)
        except subprocess.TimeoutExpired:
            assert self.process_group_id is not None
            self._forced = True
            self.emit("shutdown_forced", process_group_id=self.process_group_id)
            os.killpg(self.process_group_id, signal.SIGKILL)
            self.process.wait(timeout=5)

    def _handle_command(self, message: dict[str, Any]) -> None:
        command = message.get("command")
        if command == "invalid":
            self.emit("control_warning", message="忽略无效的桌面控制帧")
            return
        if command != "shutdown":
            self.emit("control_warning", message="忽略未知的桌面控制命令")
            return
        supplied_id = message.get("instance_id")
        if supplied_id is not None and supplied_id != self.instance_id:
            self.emit("control_warning", message="忽略实例标识不匹配的关闭命令")
            return
        self._request_backend_stop(str(message.get("reason") or "host_request"))

    def run(self) -> int:
        self._install_signal_handlers()
        self.emit("supervisor_started", pid=os.getpid(), port=self.port)
        try:
            self.start_backend()
        except (DesktopRuntimeError, OSError, subprocess.SubprocessError) as exc:
            self.emit("startup_failed", message=str(exc))
            return 1

        reader = threading.Thread(target=self._read_commands, daemon=True)
        reader.start()
        assert self.process is not None

        while self.process.poll() is None and not self._shutdown_requested:
            try:
                message = self._commands.get(timeout=0.1)
            except queue.Empty:
                continue
            self._handle_command(message)

        if self._shutdown_requested:
            self._finish_backend_stop()

        exit_code = self.process.poll()
        if exit_code is None:
            exit_code = self.process.wait()
        self.emit(
            "backend_exited",
            exit_code=exit_code,
            requested=self._shutdown_requested,
            forced=self._forced,
        )
        return 0 if self._shutdown_requested else int(exit_code or 0)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ResearchMate Windows desktop WSL supervisor")
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--runtime-info-json")
    parser.add_argument(
        "--startup-port-timeout",
        type=float,
        default=DEFAULT_STARTUP_PORT_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--graceful-timeout",
        type=float,
        default=DEFAULT_GRACEFUL_TIMEOUT_SECONDS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        supervisor = DesktopRuntimeSupervisor(
            instance_id=args.instance_id,
            host=args.host,
            port=args.port,
            graceful_timeout=args.graceful_timeout,
            runtime_info_json=args.runtime_info_json,
            startup_port_timeout=args.startup_port_timeout,
        )
    except DesktopRuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())
