#!/usr/bin/env python3
"""Self-test for the memory subsystem: storage, decay, ranking, dedup, parsing.

Runs fully offline (no Ollama) using a temporary database and synthetic
embeddings, so it verifies the *logic* on any machine. Exit 0 = pass.
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, memory  # noqa: E402
from app.config import load_config  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


def main() -> int:
    db.DB_PATH = Path(tempfile.mkdtemp()) / "verify_memory.db"
    db.init_db()
    cfg = load_config()

    now = datetime.now(timezone.utc)
    check("decay: fresh ~= 1.0", abs(memory.decay_factor(now.isoformat(), 30) - 1.0) < 0.01)
    one_hl = (now - timedelta(days=30)).isoformat()
    check("decay: one half-life ~= 0.5", abs(memory.decay_factor(one_hl, 30) - 0.5) < 0.05)

    check("cosine: identical = 1", abs(memory.cosine([1, 0, 0], [1, 0, 0]) - 1.0) < 1e-6)
    check("cosine: orthogonal = 0", abs(memory.cosine([1, 0, 0], [0, 1, 0])) < 1e-6)

    raw = 'ok! [{"content":"Toni builds Nero","type":"semantic","importance":0.8,"confidence":0.9,"entities":["Nero"]}]'
    parsed = memory.parse_memories(raw)
    check("parse: extracts 1 memory", len(parsed) == 1 and parsed[0]["content"].startswith("Toni"))
    check("parse: junk -> []", memory.parse_memories("no json here") == [])

    # Retrieval ranks the semantically-closest memory first.
    db.add_memory("likes dark mode", mtype="preference", confidence=0.9, embedding=[1, 0, 0])
    db.add_memory("uses Windows", mtype="semantic", confidence=0.9, embedding=[0, 1, 0])
    memory.embed_text = lambda _cfg, _q: [1, 0, 0]  # query resembles "dark mode"
    top = memory.retrieve(cfg, "what theme do I like", k=2)
    check("retrieve: closest memory first", bool(top) and top[0]["content"] == "likes dark mode")

    # Storing a near-duplicate reinforces instead of adding a second copy.
    memory.embed_text = lambda _cfg, _t: [0, 0, 1]
    before = len(db.all_memories())
    item = {"content": "plays guitar", "type": "semantic", "importance": 0.5, "confidence": 0.7, "entities": []}
    check("store: first is added", memory.store_memory(cfg, dict(item)) == "added")
    check("store: duplicate is reinforced", memory.store_memory(cfg, dict(item)) == "reinforced")
    check("dedup: stored only once", len(db.all_memories()) == before + 1)

    # Regression (mixed-scale bug): an embedded, relevant memory must beat a
    # non-embedded irrelevant one. Fresh DB so earlier rows don't interfere.
    db.DB_PATH = Path(tempfile.mkdtemp()) / "verify_memory2.db"
    db.init_db()
    db.add_memory("favorite language is Python", mtype="preference", confidence=0.7, embedding=[0, 1, 0])
    db.add_memory("talked about the weather once", mtype="episodic", confidence=0.7)  # no embedding
    memory.embed_text = lambda _cfg, _q: [0, 1, 0]
    ranked = memory.retrieve(cfg, "which language do I prefer", k=2)
    check("mixed-scale: embedded-relevant ranks first",
          bool(ranked) and ranked[0]["content"] == "favorite language is Python")

    # Regression (embed-dim change): a stored embedding of a different length
    # must fall back to lexical recall instead of being buried.
    db.DB_PATH = Path(tempfile.mkdtemp()) / "verify_memory3.db"
    db.init_db()
    db.add_memory("enjoys hiking on weekends", mtype="preference", confidence=0.8, embedding=[1, 0])
    memory.embed_text = lambda _cfg, _q: [0.1, 0.2, 0.3, 0.4]  # different dimension
    recalled = memory.retrieve(cfg, "what hiking does Toni enjoy", k=1)
    check("dim-mismatch: still recalled via lexical fallback",
          bool(recalled) and recalled[0]["content"].startswith("enjoys hiking"))

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Memory subsystem logic verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
