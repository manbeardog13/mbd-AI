#!/usr/bin/env python3
"""Self-test for the World Model: storage upsert/merge/clear, parsing, rendering.

Runs fully offline (temp DB, no Ollama), so it verifies the logic on any
machine. Exit 0 = pass.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, world_model  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


def main() -> int:
    db.DB_PATH = Path(tempfile.mkdtemp()) / "verify_world.db"
    db.init_db()

    check("render of empty state is ''", world_model.render({}, "Toni") == "")

    db.upsert_world({"current_project": "Nero", "current_task": "world model"})
    state = db.get_world()
    check("upsert stores fields",
          state.get("current_project") == "Nero" and state.get("current_task") == "world model")

    db.upsert_world({"current_task": "reviewing", "blockers": "VRAM"})
    state = db.get_world()
    check("merge updates existing + adds new",
          state["current_task"] == "reviewing" and state["blockers"] == "VRAM"
          and state["current_project"] == "Nero")

    db.upsert_world({"blockers": ""})
    check("blank value clears a field", "blockers" not in db.get_world())

    rendered = world_model.render(db.get_world(), "Toni")
    check("render includes labels + owner",
          "Current project: Nero" in rendered and "Toni" in rendered)

    updates = world_model.parse_world_updates(
        '```json\n{"current_task":"ship phase 2","unknown_key":"x","next_steps":"review"}\n```'
    )
    check("parse keeps known keys, drops unknown",
          updates.get("current_task") == "ship phase 2"
          and updates.get("next_steps") == "review"
          and "unknown_key" not in updates)

    survived = world_model.parse_world_updates(
        '<think>reasoning with {a:1}</think> Here it is: {"current_project":"Nero"} done.'
    )
    check("parse survives <think> + trailing prose", survived.get("current_project") == "Nero")

    check("parse junk -> {}", world_model.parse_world_updates("no json here") == {})

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  World Model logic verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
