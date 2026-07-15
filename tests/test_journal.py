"""Action Journal tests — Stage 1: storage foundation (append-only, event-sourced).

Verifies the storage layer in app/db.py: the table/migration, the write+read
primitives, event-sourcing (base 'action' + linked event rows), and — critically —
that immutability is enforced by the DATABASE (triggers), not by convention.

Later stages grow this file (redaction, dispatch integration, …). Storage first.

Run directly:  python tests/test_journal.py
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db


def _fresh() -> None:
    db.DB_PATH = Path(tempfile.mkdtemp()) / "journal_test.db"
    db.init_db()


def _raw() -> sqlite3.Connection:
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def test_init_is_idempotent():
    _fresh()
    db.init_db(); db.init_db()  # repeat startups must not error
    conn = _raw()
    got = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='action_journal'"
    ).fetchone()
    conn.close()
    assert got is not None


def test_add_and_get_action():
    _fresh()
    aid = db.add_action({"capability": "git.status", "status": "completed", "ok": True,
                         "importance": "routine", "risk": "safe", "approval": "auto"})
    assert aid.startswith("act_")
    row = db.get_action(aid)
    assert row["capability"] == "git.status" and row["ok"] == 1 and row["event_type"] == "action"


def test_event_sourcing_outcome_row():
    _fresh()
    base = db.add_action({"capability": "fs.write", "status": "executing", "importance": "important"})
    db.add_action({"capability": "fs.write", "event_type": "outcome", "parent_id": base,
                   "status": "completed", "ok": True, "duration_ms": 12})
    events = db.get_action_events(base)
    assert len(events) == 1 and events[0]["event_type"] == "outcome" and events[0]["ok"] == 1
    # Listing shows base actions only — event rows never appear as top-level actions.
    assert [r["action_id"] for r in db.get_actions()] == [base]


def test_append_only_update_is_rejected():
    _fresh()
    aid = db.add_action({"capability": "git.status", "status": "completed", "importance": "routine"})
    conn = _raw()
    raised = False
    try:
        conn.execute("UPDATE action_journal SET status='tampered' WHERE action_id=?", (aid,))
        conn.commit()
    except sqlite3.Error:
        raised = True
    conn.close()
    assert raised, "UPDATE must be blocked by the append-only trigger"
    assert db.get_action(aid)["status"] == "completed"  # truly unchanged


def test_delete_blocked_for_meaningful_rows():
    _fresh()
    crit = db.add_action({"capability": "terminal.run", "importance": "critical", "status": "denied"})
    mile = db.add_action({"capability": "x", "importance": "routine", "milestone": True})
    for aid in (crit, mile):
        conn = _raw()
        blocked = False
        try:
            conn.execute("DELETE FROM action_journal WHERE action_id=?", (aid,))
            conn.commit()
        except sqlite3.Error:
            blocked = True
        conn.close()
        assert blocked, f"delete of protected row {aid} must abort"
        assert db.get_action(aid) is not None


def test_delete_allowed_for_routine():
    _fresh()
    aid = db.add_action({"capability": "fs.read", "importance": "routine", "status": "completed"})
    conn = _raw()
    conn.execute("DELETE FROM action_journal WHERE action_id=?", (aid,))
    conn.commit(); conn.close()
    assert db.get_action(aid) is None  # retention compaction may remove routine noise


def test_get_actions_filters_and_order():
    _fresh()
    db.add_action({"capability": "git.status", "importance": "routine",
                   "created_at": "2026-07-10T00:00:00+00:00"})
    db.add_action({"capability": "fs.write", "importance": "important",
                   "created_at": "2026-07-11T00:00:00+00:00"})
    db.add_action({"capability": "fs.write", "importance": "important",
                   "created_at": "2026-07-12T00:00:00+00:00"})
    times = [r["created_at"] for r in db.get_actions()]
    assert times == sorted(times, reverse=True)  # newest first
    assert len(db.get_actions(capability="fs.write")) == 2
    assert len(db.get_actions(importance="important")) == 2
    assert len(db.get_actions(since="2026-07-12T00:00:00+00:00")) == 1


def test_durable_write_persists():
    _fresh()
    aid = db.add_action({"capability": "fs.write", "importance": "important",
                         "status": "executing"}, durable=True)
    assert db.get_action(aid) is not None


def test_unknown_keys_are_ignored_not_injected():
    _fresh()
    aid = db.add_action({"capability": "git.status", "bogus_col": "x", "importance": "routine"})
    assert db.get_action(aid)["capability"] == "git.status"  # unknown key dropped, no crash


def test_migrate_journal_is_safe_on_existing_table():
    _fresh()
    db.add_action({"capability": "git.status", "importance": "routine"})
    conn = _raw()
    db._migrate_journal(conn)  # additive; must not error or lose the row
    conn.close()
    assert len(db.get_actions()) == 1


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} Action-Journal storage tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
