#!/usr/bin/env python3
"""Verify reflection: Nero extracts a memory from a sample exchange.

Needs Ollama running (uses the chat model). Skips otherwise. Uses a temporary
database so it never touches your real memories.
"""
from __future__ import annotations

import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, memory  # noqa: E402
from app.config import load_config  # noqa: E402

HOST = "http://127.0.0.1:11434"


def server_up() -> bool:
    try:
        with urllib.request.urlopen(HOST + "/api/tags", timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    if not server_up():
        print("  . Ollama not reachable — skipping (see verify_ollama).")
        return 2

    db.DB_PATH = Path(tempfile.mkdtemp()) / "verify_reflection.db"
    db.init_db()
    cfg = load_config()

    result = memory.reflect(
        cfg,
        "My name is Toni and I'm building a local AI called Nero on my NVIDIA GPU.",
        "Love it, Toni — a fully-local Nero on your own GPU is a brilliant project.",
    )
    print(f"  reflection result: {result}")

    if result.get("skipped"):
        print("  XX reflection was skipped or errored (is the chat model pulled?).")
        return 1

    stored = len(db.all_memories())
    print(f"  {'OK' if stored else 'XX'} reflection ran; {stored} memory(ies) stored.")
    return 0 if stored >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())
