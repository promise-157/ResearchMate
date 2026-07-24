"""
ResearchMate 启动脚本。

用法:
    python run.py              # 启动后端 + 打开浏览器
    python run.py --no-browser # 启动后端，不打开浏览器
    python run.py --reload     # 开发模式，代码变更自动重载
    python run.py --kill       # 先杀掉占用端口的旧进程再启动
"""
import sys
import os
import argparse
import signal
import socket
import webbrowser
import time
from pathlib import Path

# 确保 backend 目录在 Python 路径中
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


def check_port(host, port):
    """检查端口是否被占用。返回 True 表示空闲。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.bind((host, port))
            return True
    except OSError:
        return False


def kill_port(host, port):
    """杀掉占用指定端口的进程。"""
    import subprocess
    try:
        # 用 ss 或 lsof 或 fuser 查找占用进程
        result = subprocess.run(
            ["fuser", "-k", f"{port}/tcp"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            time.sleep(0.5)
            return True
    except Exception:
        pass

    # fallback: 用 lsof
    try:
        result = subprocess.run(
            ["lsof", "-t", f"-i:{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
        if pids:
            time.sleep(0.5)
            return True
    except Exception:
        pass

    return False


def open_browser(host, port):
    """延迟打开浏览器（等 uvicorn 启动完毕）。"""
    url = f"http://{host}:{port}"
    time.sleep(1.5)
    print(f"\n  浏览器打开: {url}\n")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="ResearchMate 启动脚本")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--reload", action="store_true", help="开发模式，代码变更自动重载")
    parser.add_argument("--kill", action="store_true", help="杀掉占用端口的旧进程后启动")
    args = parser.parse_args()

    from config import get as config_get
    from storage.database import init_db

    host = config_get("server", "host")
    port = config_get("server", "port")
    reload = args.reload or config_get("server", "reload")

    # 端口占用处理
    if not check_port(host, port):
        print(f"  ⚠ 端口 {port} 已被占用", end="")
        if args.kill or sys.stdout.isatty():
            if args.kill or input(" → 杀掉旧进程重新启动？[Y/n] ").strip().lower() != "n":
                print("  正在清理...")
                if kill_port(host, port):
                    print("  ✓ 已清理")
                else:
                    print(f"  ✗ 清理失败，请手动执行: pkill -f 'python run.py'")
                    sys.exit(1)
            else:
                print("  已取消")
                sys.exit(0)
        else:
            print(f"\n  请手动执行: pkill -f 'python run.py'  或  python run.py --kill")
            sys.exit(1)

    # 初始化数据库
    init_db()
    print(f"  数据库: {config_get('database', 'path')}")

    # 打开浏览器
    if not args.no_browser:
        import threading
        threading.Thread(target=open_browser, args=(host, port), daemon=True).start()

    # 启动 uvicorn
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
