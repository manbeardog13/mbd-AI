"""Unit tests for Executive Memory — the working-state register (ADR-0008).

The bar (ROADMAP Phase 1): the register holds the right project/branch (observed
from git, not stored-and-trusted), and intent fields persist so a later read
returns them instead of reconstructing. Uses a temp DB — touches no real data.

Run directly:  python tests/test_executive_memory.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db
from app.agent import state

REPO = str(Path(__file__).resolve().parent.parent)  # a real git repo


def _fresh_db():
    tmp = Path(tempfile.mkdtemp()) / "exec_test.db"
    db.DB_PATH = tmp
    db.init_db()


def test_observed_fields_come_from_the_machine():
    _fresh_db()
    obs = state.observe(REPO)
    assert obs["project"] == Path(REPO).name  # basename of the project dir
    # branch is whatever git reports (a string) or None if git is unavailable.
    assert obs["branch"] is None or isinstance(obs["branch"], str)


def test_intent_fields_persist_across_reads():
    _fresh_db()
    state.update({"goal": "ship phase 1", "task": "build the agent loop",
                  "next_action": "write tests"})
    ws = state.read(REPO)
    assert ws.goal == "ship phase 1"
    assert ws.task == "build the agent loop"
    assert ws.next_action == "write tests"


def test_observed_wins_over_stored():
    _fresh_db()
    # Even if someone stored a stale branch, the observed one must win on read.
    db.upsert_executive({"branch": "stale-branch-name"})
    ws = state.read(REPO)
    observed = state.observe(REPO)["branch"]
    assert ws.branch == observed  # not "stale-branch-name" (unless git agrees)


def test_update_ignores_observed_and_unknown_keys():
    _fresh_db()
    changed = state.update({"branch": "nope", "project": "nope", "bogus": "x",
                            "blocker": "waiting on review"})
    assert "branch" not in changed and "project" not in changed and "bogus" not in changed
    assert changed.get("blocker") == "waiting on review"
    assert db.get_executive().get("branch") is None


def test_clear_resets_intent():
    _fresh_db()
    state.update({"goal": "x", "task": "y"})
    state.clear()
    ws = state.read(REPO)
    assert ws.goal is None and ws.task is None


def test_render_orders_and_labels():
    ws = state.WorkingState(goal="ship", branch="main", next_action="test")
    out = state.render(ws)
    assert "Goal: ship" in out and "Branch: main" in out and "Next action: test" in out
    assert out.index("Goal") < out.index("Branch") < out.index("Next action")


def test_render_empty_is_blank():
    assert state.render(state.WorkingState()) == ""


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} executive-memory tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
