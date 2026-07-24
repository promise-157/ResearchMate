"""
ResearchMate 启动脚本。

用法:
    python run.py              # 启动后端 + 打开浏览器
    python run.py --no-browser # 启动后端，不打开浏览器
    python run.py --reload     # 开发模式，代码变更自动重载
"""
import sys
import os
import argparse
import webbrowser
import time
from pathlib import Path

# 确保 backend 目录在 Python 路径中
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


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
    args = parser.parse_args()

    from config import get as config_get
    from storage.database import init_db

    host = config_get("server", "host")
    port = config_get("server", "port")
    reload = args.reload or config_get("server", "reload")

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
