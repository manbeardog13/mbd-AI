"""Manual entrypoint for Nero Mission Control.

This file is never called by Host Presence, startup hooks, or the legacy Nero
launcher. Running it is the explicit operator launch required by ADR-0017.
"""
from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch Nero Mission Control manually")
    parser.add_argument("--repo", type=Path, default=ROOT, help="Git worktree to inspect")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from uvicorn import run

    from mission_control import create_app

    app = create_app(args.repo.resolve())
    print(
        f"Nero Mission Control is explicitly running at http://{args.host}:{args.port}\n"
        "Remote Git write routes are disabled. Press Ctrl+C to stop."
    )
    run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
