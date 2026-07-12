#!/usr/bin/env python3
"""Self-test for Executive Memory — the working-state register (ADR-0008).

Offline, on a temp DB. Proves: deterministic fields (project/branch) are observed
from the machine and win over anything stored; intent fields persist so a later
read returns them without reconstruction; unknown/observed keys can't be written
as intent; render is ordered and labelled. Exit 0 = pass.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.agent import state  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


def main() -> int:
    repo = str(Path(__file__).resolve().parent.parent)
    db.DB_PATH = Path(tempfile.mkdtemp()) / "verify_exec.db"
    db.init_db()

    obs = state.observe(repo)
    check("project is observed as the directory name", obs["project"] == Path(repo).name)
    check("branch is observed from git (str or None)",
          obs["branch"] is None or isinstance(obs["branch"], str))
    print(f"     -> observed: project={obs['project']!r} branch={obs['branch']!r}")

    state.update({"goal": "ship phase 1", "task": "agent loop", "next_action": "verify"})
    ws = state.read(repo)
    check("intent fields persist across a read",
          ws.goal == "ship phase 1" and ws.task == "agent loop" and ws.next_action == "verify")

    db.upsert_executive({"branch": "stale-name"})
    check("observed branch wins over a stored one", state.read(repo).branch == obs["branch"])

    changed = state.update({"branch": "x", "project": "y", "bogus": "z", "blocker": "review"})
    check("update ignores observed + unknown keys, keeps intent",
          "branch" not in changed and "project" not in changed
          and "bogus" not in changed and changed.get("blocker") == "review")

    rendered = state.render(state.WorkingState(goal="ship", branch="main", next_action="test"))
    check("render is ordered and labelled",
          "Goal: ship" in rendered
          and rendered.index("Goal") < rendered.index("Branch") < rendered.index("Next action"))

    state.clear()
    check("clear resets intent", state.read(repo).goal is None)

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Executive Memory verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
