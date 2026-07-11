#!/usr/bin/env python3
"""Verify Nero's configuration loads cleanly (including with blank fields).

Run inside the venv so `app` and PyYAML resolve.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.config import load_config
except Exception as exc:  # noqa: BLE001
    print(f"  XX could not import app.config: {exc}")
    print("     Run inside the venv, e.g.  .venv/bin/python verify/verify_everything.py")
    sys.exit(1)


def main() -> int:
    try:
        cfg = load_config()
    except Exception as exc:  # noqa: BLE001
        print(f"  XX config.yaml failed to load: {exc}")
        return 1

    print("  OK config loads.")
    print(f"     name={cfg.ai_name!r}  model={cfg.model!r}  humor={cfg.humor}")
    print(f"     languages={cfg.languages}  goals={len(cfg.goals)}  principles={len(cfg.principles)}")
    if not (0 <= cfg.humor <= 100):
        print("  XX humor out of range")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
