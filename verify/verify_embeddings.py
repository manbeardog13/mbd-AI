#!/usr/bin/env python3
"""Verify local embeddings work (nomic-embed-text via Ollama).

Skips if Ollama isn't running (verify_ollama covers that); fails if the server
is up but embeddings don't come back.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config  # noqa: E402
from app.llm import embed_text  # noqa: E402

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

    cfg = load_config()
    vec = embed_text(cfg, "Toni is building a local AI called Nero.")
    if not vec:
        print(f"  XX embeddings returned nothing.")
        print(f"     Fix: ollama pull {cfg.embed_model}")
        return 1

    print(f"  OK embeddings work: {cfg.embed_model} → {len(vec)}-dim vector")
    return 0


if __name__ == "__main__":
    sys.exit(main())
