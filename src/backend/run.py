"""
ResearchMate 启动脚本。

用法:
    python run.py              # 生产模式：后端 + 前端静态文件，一个端口
    python run.py --dev        # 开发模式：后端(8000) + Vite热更新(5173)，一起启动
    python run.py --no-browser # 不自动打开浏览器
    python run.py --kill       # 先杀掉占用端口的旧进程再启动
"""
import sys
import os
import argparse
import errno
import re
import signal
import shutil
import socket
import subprocess
import webbrowser
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
sys.path.insert(0, str(BACKEND_DIR))

from config import get as config_get  # noqa: E402 - backend path is added above

_vite_process = None


class PortPermissionError(RuntimeError):
    """The launcher cannot distinguish availability because bind was denied."""


def check_port(host, port):
    """Return True only when the port can be bound; surface permission failures."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.bind((host, port))
            return True
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EPERM}:
            raise PortPermissionError(
                f"无权检查或绑定 {host}:{port}；这不是可确认的端口占用"
            ) from exc
        return False


def _parse_pids(output):
    return {
        int(value) for value in re.findall(r"(?m)^\s*(\d+)\s*$", output or "")
        if int(value) != os.getpid()
    }


def _linux_listener_pids(port):
    pids = set()
    commands = []
    if shutil.which("lsof"):
        commands.append(["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"])
    if shutil.which("fuser"):
        commands.append(["fuser", "-n", "tcp", str(port)])
    for command in commands:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=5, check=False,
            )
            if command[0] == "fuser":
                pids.update(
                    int(value) for value in re.findall(r"\b\d+\b", result.stdout or "")
                    if int(value) != os.getpid()
                )
            else:
                pids.update(_parse_pids(result.stdout))
        except (OSError, subprocess.SubprocessError):
            continue
    return pids


def _powershell_executable():
    for name in ("powershell.exe", "powershell", "pwsh"):
        executable = shutil.which(name)
        if executable:
            return executable
    return None


def _windows_listener_pids(port):
    executable = _powershell_executable()
    if not executable:
        return set()
    command = (
        f"Get-NetTCPConnection -LocalPort {int(port)} -State Listen "
        "-ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess -Unique"
    )
    try:
        result = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    return _parse_pids(result.stdout)


def _wait_for_port(host, port, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check_port(host, port):
            return True
        time.sleep(0.1)
    return check_port(host, port)


def _terminate_linux_pids(pids):
    errors = []
    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError:
            errors.append(f"无权终止 Linux PID {pid}")
        except OSError as exc:
            errors.append(f"终止 Linux PID {pid} 失败：{exc}")
    return errors


def _force_terminate_linux_pids(pids):
    errors = []
    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
        except PermissionError:
            errors.append(f"无权强制终止 Linux PID {pid}")
        except OSError as exc:
            errors.append(f"强制终止 Linux PID {pid} 失败：{exc}")
    return errors


def _terminate_windows_pids(pids):
    executable = _powershell_executable()
    if not executable or not pids:
        return ["无法调用 PowerShell 终止 Windows listener"]
    pid_list = ",".join(str(pid) for pid in sorted(pids))
    command = f"Stop-Process -Id {pid_list} -Force -ErrorAction Stop"
    try:
        result = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"调用 PowerShell 失败：{exc}"]
    if result.returncode == 0:
        return []
    return ["Windows listener 终止失败；请以 PowerShell 管理员身份检查该 PID"]


def kill_port(host, port):
    """Terminate the exact Linux or Windows listener and verify the port is free."""
    messages = []
    linux_pids = _linux_listener_pids(port)
    if linux_pids:
        print(f"  找到 Linux listener PID: {', '.join(map(str, sorted(linux_pids)))}")
        messages.extend(_terminate_linux_pids(linux_pids))
        if _wait_for_port(host, port):
            return True, "Linux listener 已终止"
        messages.extend(_force_terminate_linux_pids(linux_pids))
        if _wait_for_port(host, port):
            return True, "Linux listener 已强制终止"

    windows_pids = _windows_listener_pids(port)
    if windows_pids:
        print(f"  找到 Windows listener PID: {', '.join(map(str, sorted(windows_pids)))}")
        messages.extend(_terminate_windows_pids(windows_pids))
        if _wait_for_port(host, port):
            return True, "Windows listener 已终止"

    if not linux_pids and not windows_pids:
        messages.append("未找到可终止的 Linux/Windows listener；可能需要管理员权限")
    elif not messages:
        messages.append("listener 在终止后仍占用端口；请检查其是否被服务管理器自动重启")
    return False, "；".join(messages)


def ensure_frontend_built():
    """确保前端已构建。如果没有 dist/，自动 npm run build。"""
    dist_dir = FRONTEND_DIR / "dist"
    if dist_dir.is_dir():
        print("  前端: dist/ 已就绪")
        return True

    print("  前端未构建，正在 npm run build ...")
    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(FRONTEND_DIR),
            check=True,
            timeout=120,
            capture_output=True,
            text=True,
        )
        print("  前端: 构建完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  前端构建失败:\n{e.stderr[-500:]}")
        return False
    except FileNotFoundError:
        print("  未找到 npm，请先安装 Node.js")
        return False


def start_vite():
    """启动 Vite 开发服务器。"""
    global _vite_process
    vite_port = config_get("frontend", "dev_port") or 5173
    print(f"  前端: 启动 Vite 开发服务器 (http://127.0.0.1:{vite_port}) ...")
    _vite_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(10):
        if _vite_process.poll() is not None:
            print("  ⚠ Vite 进程提前退出，请在前端目录单独运行 npm run dev 查看错误")
            return
        if not check_port("127.0.0.1", vite_port):
            time.sleep(0.5)
            return
        time.sleep(0.5)
    print("  ⚠ Vite 启动超时，请手动执行: cd src/frontend && npm run dev")


def stop_vite():
    global _vite_process
    if _vite_process:
        _vite_process.terminate()
        _vite_process.wait(timeout=5)
        _vite_process = None


def open_browser(host, port, dev=False):
    time.sleep(2)
    vite_port = config_get("frontend", "dev_port") or 5173
    url = f"http://{host}:{vite_port if dev else port}"
    print(f"\n  浏览器打开: {url}\n")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="ResearchMate 启动脚本")
    parser.add_argument("--dev", action="store_true", help="开发模式：后端 + Vite 热更新")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--kill", action="store_true", help="杀掉占用端口的旧进程后启动")
    args = parser.parse_args()

    from storage.database import init_db

    host = config_get("server", "host")
    port = config_get("server", "port")

    # 端口占用处理
    try:
        port_available = check_port(host, port)
    except PortPermissionError as exc:
        print(f"  ✗ {exc}")
        print("  请检查安全软件/沙箱权限，或在普通 WSL/终端中启动")
        sys.exit(1)
    if not port_available:
        print(f"  ⚠ 端口 {port} 已被占用", end="")
        if args.kill or sys.stdout.isatty():
            if args.kill or input(" → 杀掉旧进程重新启动？[Y/n] ").strip().lower() != "n":
                print("  正在清理...")
                cleared, detail = kill_port(host, port)
                if cleared:
                    print(f"  ✓ 已清理（{detail}）")
                else:
                    print(f"  ✗ 清理失败：{detail}")
                    print(f"  可保留原进程并改用其他端口：RESEARCHMATE_PORT={port + 1} python run.py --no-browser")
                    sys.exit(1)
            else:
                print("  已取消")
                sys.exit(0)
        else:
            print("\n  使用 python run.py --kill 明确清理 listener，或设置 RESEARCHMATE_PORT 改用其他端口")
            sys.exit(1)

    # 开发模式
    if args.dev:
        start_vite()
        # 开发模式：如果 dist 不存在，用 Vite 代理，不打开 reload
        print(f"  开发模式: 前端 http://127.0.0.1:{config_get('frontend', 'dev_port') or 5173} (Vite 热更新)")
        print(f"           后端 http://{host}:{port}")
        reload_flag = True
    else:
        # 生产模式：确保前端已构建
        if not ensure_frontend_built():
            print("  前端构建失败，仅启动后端 API")
        reload_flag = False

    # 初始化数据库
    init_db()
    print(f"  数据库: {config_get('database', 'path')}")

    # 打开浏览器
    if not args.no_browser:
        import threading
        threading.Thread(
            target=open_browser, args=(host, port, args.dev), daemon=True
        ).start()

    # 启动 uvicorn
    import uvicorn

    try:
        uvicorn.run(
            "api.server:app",
            host=host,
            port=port,
            reload=reload_flag,
            log_level="info",
        )
    finally:
        stop_vite()


if __name__ == "__main__":
    main()
