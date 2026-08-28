"""Local-only disposable backend used by desktop lifecycle probes."""

from __future__ import annotations

import argparse
import json
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path == "/api/health":
            body = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            body = (
                "<!doctype html><html><body><h1>ResearchMate desktop fixture</h1>"
                "<p>This page uses no workspace data or network.</p></body></html>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--ignore-term", action="store_true")
    args = parser.parse_args()

    def stop(_signum, _frame):
        if args.ignore_term:
            return
        args.marker.write_text("sigterm", encoding="utf-8")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), FixtureHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
