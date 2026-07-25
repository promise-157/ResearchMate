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
import signal
import socket
import subprocess
import webbrowser
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
sys.path.insert(0, str(BACKEND_DIR))

from config import get as config_get

_vite_process = None


def check_port(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.bind((host, port))
            return True
    except OSError:
        return False


def kill_port(host, port):
    import subprocess as sp
    try:
        r = sp.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            time.sleep(0.5)
            return True
    except Exception:
        pass
    try:
        r = sp.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True, timeout=5)
        for pid in r.stdout.strip().split():
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass
        if r.stdout.strip():
            time.sleep(0.5)
            return True
    except Exception:
        pass
    return False


def ensure_frontend_built():
    """确保前端已构建。如果没有 dist/，自动 npm run build。"""
    dist_dir = FRONTEND_DIR / "dist"
    if dist_dir.is_dir():
        print(f"  前端: dist/ 已就绪")
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
        if check_port("127.0.0.1", vite_port):
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
    if not check_port(host, port):
        print(f"  ⚠ 端口 {port} 已被占用", end="")
        if args.kill or sys.stdout.isatty():
            if args.kill or input(" → 杀掉旧进程重新启动？[Y/n] ").strip().lower() != "n":
                print("  正在清理...")
                if kill_port(host, port):
                    print("  ✓ 已清理")
                else:
                    print(f"  ✗ 清理失败，请手动: pkill -f 'python run.py'")
                    sys.exit(1)
            else:
                print("  已取消")
                sys.exit(0)
        else:
            print(f"\n  请手动: pkill -f 'python run.py'  或  python run.py --kill")
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
