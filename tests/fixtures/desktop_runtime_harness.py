"""Test-only CLI wrapper around the production desktop supervisor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "src" / "backend"
sys.path.insert(0, str(BACKEND))

from desktop_runtime import DesktopRuntimeSupervisor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--marker", default="/tmp/researchmate-desktop-host-fixture.marker"
    )
    parser.add_argument("--graceful-timeout", type=float, default=3.0)
    parser.add_argument("--ignore-term", action="store_true")
    args = parser.parse_args()

    command = [
        sys.executable,
        str(Path(__file__).with_name("desktop_runtime_backend.py")),
        "--port",
        str(args.port),
        "--marker",
        args.marker,
    ]
    if args.ignore_term:
        command.append("--ignore-term")
    return DesktopRuntimeSupervisor(
        instance_id=args.instance_id,
        port=args.port,
        graceful_timeout=args.graceful_timeout,
        backend_command=command,
    ).run()


if __name__ == "__main__":
    raise SystemExit(main())
