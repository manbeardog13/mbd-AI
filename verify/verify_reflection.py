#!/usr/bin/env python3
"""Verify reflection: Nero extracts a memory from a sample exchange.

Needs Ollama running (uses the chat model). Skips otherwise. Uses a temporary
database so it never touches your real memories.

If reflection stores nothing, this prints exactly what the model returned (raw,
stripped, and parsed) so the cause is visible instead of guessed at — the most
common one is a reasoning model spending its whole token budget "thinking" and
never reaching the JSON.
"""
from __future__ import annotations

import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, memory  # noqa: E402
from app.config import load_config  # noqa: E402
from app.llm import complete_chat  # noqa: E402


def server_up(host: str) -> bool:
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


USER = "My name is Toni and I'm building a local AI called Nero on my NVIDIA GPU."
REPLY = "Love it, Toni — a fully-local Nero on your own GPU is a brilliant project."


def _diagnose(cfg) -> None:
    """Show exactly what the reflection model returns, and how it parses."""
    model = cfg.reflection_model or cfg.model
    print(f"  · reflection model: {model}  (num_predict={memory.REFLECTION_NUM_PREDICT}, think=False)")
    raw = complete_chat(
        cfg,
        [
            {"role": "system", "content": memory._REFLECTION_SYSTEM},
            {"role": "user", "content": memory._reflection_user_prompt(cfg.owner_name, USER, REPLY)},
        ],
        temperature=0.0,
        model=model,
        num_predict=memory.REFLECTION_NUM_PREDICT,
        keep_alive="0" if model != cfg.model else None,
        think=False,
    )
    print(f"  · raw model output ({len(raw)} chars):")
    print("    " + (repr(raw[:800]) if raw else "<empty>"))
    stripped = memory.strip_think(raw)
    if stripped != raw:
        print(f"  · after strip_think ({len(stripped)} chars): {repr(stripped[:400])}")
    parsed = memory.parse_memories(raw)
    print(f"  · parse_memories -> {len(parsed)} item(s)")
    if raw and not parsed:
        if "<think>" in raw and "</think>" not in raw:
            print("    HINT: output is an *unterminated* <think> block — the model spent its")
            print("    whole budget reasoning and never emitted JSON. Raise num_predict, or")
            print("    ensure your Ollama honors think=False (update Ollama).")
        elif not raw:
            print("    HINT: model returned nothing — check the model is pulled and healthy.")
        else:
            print("    HINT: output wasn't a parseable JSON array of memories (see raw above).")


def main() -> int:
    cfg = load_config()
    if not server_up(cfg.ollama_host):
        print("  . Ollama not reachable — skipping (see verify_ollama).")
        return 2

    db.DB_PATH = Path(tempfile.mkdtemp()) / "verify_reflection.db"
    db.init_db()

    result = memory.reflect(cfg, USER, REPLY)
    print(f"  reflection result: {result}")

    if result.get("skipped"):
        print("  XX reflection was skipped or errored (is the chat model pulled?).")
        _diagnose(cfg)
        return 1

    stored = len(db.all_memories())
    print(f"  {'OK' if stored else 'XX'} reflection ran; {stored} memory(ies) stored.")
    if not stored:
        _diagnose(cfg)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
