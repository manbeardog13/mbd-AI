"""SQLite storage: conversations, messages, and Nero's long-term memory.

Conversations + messages are the running dialogue. Memories are durable facts
about Toni — typed, scored, and time-aware. This module is the **storage layer**;
`app/memory.py` is the **cognitive layer** (retrieval ranking, decay, reflection)
built on top of it.

Everything is a plain file on disk (data/memory.db). Nothing leaves the machine.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "memory.db"

# The memory layers Nero recognises (see docs/DIRECTIVE.md § Memory Architecture).
MEMORY_TYPES = ("semantic", "episodic", "preference", "experience", "procedural")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp01(x: float) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.5


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if needed and migrate older memory rows. Safe every startup."""
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT,
            created_at TEXT NOT NULL,
            active     INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS memories (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            content         TEXT NOT NULL,
            type            TEXT NOT NULL DEFAULT 'semantic',
            importance      REAL NOT NULL DEFAULT 0.5,
            confidence      REAL NOT NULL DEFAULT 0.8,
            source          TEXT NOT NULL DEFAULT 'user',
            entities        TEXT NOT NULL DEFAULT '',
            embedding       TEXT,
            created_at      TEXT NOT NULL,
            last_reinforced TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS world_state (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- Executive Memory (ADR-0008): the AI's own working-state register,
        -- kept in its own table — distinct store, distinct job from world_state.
        CREATE TABLE IF NOT EXISTS executive_state (
            key        TEXT PRIMARY KEY,
            value      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- Action Journal (Nero's chain of custody): an immutable, event-sourced
        -- record of every action. A base 'action' row plus later 'outcome' /
        -- 'note' / 'recovery' event rows that reference it by parent_id — the
        -- current state of an action is its base row overlaid with its events.
        -- Never UPDATE (append-only); only routine/temporary rows may be deleted
        -- (by the retention compaction), enforced by the triggers below.
        CREATE TABLE IF NOT EXISTS action_journal (
            action_id        TEXT PRIMARY KEY,
            event_type       TEXT NOT NULL DEFAULT 'action',   -- action | outcome | note | recovery
            parent_id        TEXT,                             -- NULL for base rows; base id for events
            created_at       TEXT NOT NULL,
            conversation_id  INTEGER,
            actor            TEXT NOT NULL DEFAULT 'nero',
            capability       TEXT NOT NULL DEFAULT '',
            risk             TEXT NOT NULL DEFAULT '',
            approval         TEXT NOT NULL DEFAULT '',
            status           TEXT NOT NULL DEFAULT '',
            ok               INTEGER NOT NULL DEFAULT 0,
            importance       TEXT NOT NULL DEFAULT 'routine',  -- critical|important|routine|temporary
            milestone        INTEGER NOT NULL DEFAULT 0,       -- Layer-3 permanent (never deleted)
            human_notes      TEXT NOT NULL DEFAULT '',
            undo_available   INTEGER NOT NULL DEFAULT 0,
            duration_ms      INTEGER NOT NULL DEFAULT 0,
            intent_json      TEXT NOT NULL DEFAULT '{}',       -- user_request, interpretation, planned_outcome
            exec_json        TEXT NOT NULL DEFAULT '{}',       -- params, targets, checks, output_summary, error
            recovery_json    TEXT,
            transitions_json TEXT NOT NULL DEFAULT '[]',
            schema_version   INTEGER NOT NULL DEFAULT 1,
            embedding        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_journal_time       ON action_journal(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_journal_capability ON action_journal(capability, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_journal_importance ON action_journal(importance, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_journal_conv       ON action_journal(conversation_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_journal_parent     ON action_journal(parent_id);
        CREATE INDEX IF NOT EXISTS idx_journal_event      ON action_journal(event_type, created_at DESC);

        -- IMMUTABILITY, enforced by the engine and not by convention: the journal
        -- protects itself. No row is ever updated; only routine/temporary rows may
        -- be deleted (retention compaction), never critical/important/milestone.
        CREATE TRIGGER IF NOT EXISTS journal_no_update
        BEFORE UPDATE ON action_journal
        BEGIN SELECT RAISE(ABORT, 'action_journal is append-only'); END;

        CREATE TRIGGER IF NOT EXISTS journal_no_delete
        BEFORE DELETE ON action_journal
        WHEN OLD.importance IN ('critical','important') OR OLD.milestone = 1
        BEGIN SELECT RAISE(ABORT, 'meaningful journal rows are permanent'); END;

        CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, id);
        """
    )
    conn.commit()
    _migrate_memories(conn)
    _migrate_journal(conn)
    conn.close()


def _migrate_memories(conn: sqlite3.Connection) -> None:
    """Add any missing columns to an older `memories` table, without data loss."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(memories)")}
    additions = {
        "type": "TEXT NOT NULL DEFAULT 'semantic'",
        "importance": "REAL NOT NULL DEFAULT 0.5",
        "confidence": "REAL NOT NULL DEFAULT 0.8",
        "source": "TEXT NOT NULL DEFAULT 'user'",
        "entities": "TEXT NOT NULL DEFAULT ''",
        "embedding": "TEXT",
        "last_reinforced": "TEXT",
    }
    changed = False
    for name, ddl in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {ddl}")
            changed = True
    if changed:
        # Backfill last_reinforced for pre-existing rows.
        conn.execute(
            "UPDATE memories SET last_reinforced = created_at "
            "WHERE last_reinforced IS NULL OR last_reinforced = ''"
        )
        conn.commit()


# --------------------------------------------------------------------------
# Conversations & messages
# --------------------------------------------------------------------------

def get_or_create_active_conversation() -> int:
    conn = _connect()
    row = conn.execute(
        "SELECT id FROM conversations WHERE active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        conv_id = row["id"]
    else:
        cur = conn.execute(
            "INSERT INTO conversations (title, created_at, active) VALUES (?, ?, 1)",
            (None, _now()),
        )
        conv_id = cur.lastrowid
        conn.commit()
    conn.close()
    return conv_id


def start_new_conversation() -> int:
    conn = _connect()
    conn.execute("UPDATE conversations SET active = 0 WHERE active = 1")
    cur = conn.execute(
        "INSERT INTO conversations (title, created_at, active) VALUES (?, ?, 1)",
        (None, _now()),
    )
    conv_id = cur.lastrowid
    conn.commit()
    conn.close()
    return conv_id


def add_message(conversation_id: int, role: str, content: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, _now()),
    )
    conn.commit()
    conn.close()


def get_messages(conversation_id: int, limit: int | None = None) -> list[dict]:
    conn = _connect()
    if limit is None:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT role, content FROM (
                SELECT id, role, content FROM messages
                WHERE conversation_id = ? ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (conversation_id, limit),
        ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


# --------------------------------------------------------------------------
# Memories (storage primitives — ranking/decay live in app/memory.py)
# --------------------------------------------------------------------------

def add_memory(
    content: str,
    mtype: str = "semantic",
    importance: float = 0.5,
    confidence: float = 0.8,
    source: str = "user",
    entities: list[str] | None = None,
    embedding: list[float] | None = None,
) -> int:
    now = _now()
    conn = _connect()
    cur = conn.execute(
        """
        INSERT INTO memories
            (content, type, importance, confidence, source, entities, embedding, created_at, last_reinforced)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            content.strip(),
            mtype if mtype in MEMORY_TYPES else "semantic",
            _clamp01(importance),
            _clamp01(confidence),
            source or "user",
            ",".join(entities or []),
            json.dumps(embedding) if embedding else None,
            now,
            now,
        ),
    )
    mem_id = cur.lastrowid
    conn.commit()
    conn.close()
    return mem_id


def reinforce_memory(memory_id: int, boost: float = 0.3) -> None:
    """Strengthen a memory that proved relevant again (confidence → 1, refresh time)."""
    conn = _connect()
    row = conn.execute(
        "SELECT confidence FROM memories WHERE id = ?", (memory_id,)
    ).fetchone()
    if row is not None:
        c = row["confidence"]
        c = min(1.0, c + (1.0 - c) * _clamp01(boost))
        conn.execute(
            "UPDATE memories SET confidence = ?, last_reinforced = ? WHERE id = ?",
            (c, _now(), memory_id),
        )
        conn.commit()
    conn.close()


def get_memories() -> list[dict]:
    """All memories for the UI list (newest first, without embeddings)."""
    conn = _connect()
    rows = conn.execute(
        """
        SELECT id, content, type, importance, confidence, source, created_at, last_reinforced
        FROM memories ORDER BY id DESC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def all_memories(include_embeddings: bool = True) -> list[dict]:
    """Every memory as dicts, for retrieval ranking and dedup (embeddings decoded)."""
    conn = _connect()
    rows = conn.execute(
        """
        SELECT id, content, type, importance, confidence, source, entities,
               embedding, created_at, last_reinforced
        FROM memories
        """
    ).fetchall()
    conn.close()
    out: list[dict] = []
    for r in rows:
        d = dict(r)
        if include_embeddings:
            d["embedding"] = json.loads(d["embedding"]) if d["embedding"] else None
        else:
            d.pop("embedding", None)
        out.append(d)
    return out


def delete_memory(memory_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# World state (Nero's live picture of what her person is working on)
# --------------------------------------------------------------------------

def get_world() -> dict:
    """Return the whole world state as {key: value}, in insertion/key order."""
    conn = _connect()
    rows = conn.execute(
        "SELECT key, value FROM world_state ORDER BY key ASC"
    ).fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def upsert_world(updates: dict) -> None:
    """Merge updates into the world state. A blank/None value clears that key."""
    if not updates:
        return
    now = _now()
    conn = _connect()
    for key, value in updates.items():
        key = str(key).strip()
        if not key:
            continue
        text = "" if value is None else str(value).strip()
        if not text:
            conn.execute("DELETE FROM world_state WHERE key = ?", (key,))
        else:
            conn.execute(
                """
                INSERT INTO world_state (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                               updated_at = excluded.updated_at
                """,
                (key, text, now),
            )
    conn.commit()
    conn.close()


def delete_world_key(key: str) -> None:
    """Remove a single field from the world state."""
    conn = _connect()
    conn.execute("DELETE FROM world_state WHERE key = ?", (str(key).strip(),))
    conn.commit()
    conn.close()


def clear_world() -> None:
    """Wipe the whole world state — a clean-slate reset for the owner."""
    conn = _connect()
    conn.execute("DELETE FROM world_state")
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Executive state (the AI's working-state register — see app/agent/state.py)
# --------------------------------------------------------------------------

def get_executive() -> dict:
    """Return the stored working-state fields as {key: value}."""
    conn = _connect()
    rows = conn.execute(
        "SELECT key, value FROM executive_state ORDER BY key ASC"
    ).fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def upsert_executive(updates: dict) -> None:
    """Merge updates into the working-state register. A blank value clears a key."""
    if not updates:
        return
    now = _now()
    conn = _connect()
    for key, value in updates.items():
        key = str(key).strip()
        if not key:
            continue
        text = "" if value is None else str(value).strip()
        if not text:
            conn.execute("DELETE FROM executive_state WHERE key = ?", (key,))
        else:
            conn.execute(
                """
                INSERT INTO executive_state (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                               updated_at = excluded.updated_at
                """,
                (key, text, now),
            )
    conn.commit()
    conn.close()


def clear_executive() -> None:
    """Wipe the working-state register — a fresh start for a new goal."""
    conn = _connect()
    conn.execute("DELETE FROM executive_state")
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Action Journal (storage primitives — record building lives in app/journal.py)
# --------------------------------------------------------------------------

# The columns a journal row may set. add_action() whitelists against this, so a
# caller can pass a partial dict and unknown keys are ignored (never SQL-injected
# as column names). event_type/parent_id carry the event-sourcing.
JOURNAL_COLUMNS = (
    "action_id", "event_type", "parent_id", "created_at", "conversation_id",
    "actor", "capability", "risk", "approval", "status", "ok", "importance",
    "milestone", "human_notes", "undo_available", "duration_ms",
    "intent_json", "exec_json", "recovery_json", "transitions_json",
    "schema_version", "embedding",
)
_JOURNAL_BOOLS = ("ok", "milestone", "undo_available")


def _migrate_journal(conn: sqlite3.Connection) -> None:
    """Add any missing columns to an older `action_journal`, without data loss.

    Mirrors `_migrate_memories`: additive only, so a journal created by an earlier
    version gains new columns on the next startup. The table/indexes/triggers
    themselves are created idempotently in init_db().
    """
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(action_journal)")}
    if not cols:
        return  # table absent (shouldn't happen — init_db created it)
    additions = {
        "event_type": "TEXT NOT NULL DEFAULT 'action'",
        "parent_id": "TEXT",
        "milestone": "INTEGER NOT NULL DEFAULT 0",
        "human_notes": "TEXT NOT NULL DEFAULT ''",
        "recovery_json": "TEXT",
        "transitions_json": "TEXT NOT NULL DEFAULT '[]'",
        "schema_version": "INTEGER NOT NULL DEFAULT 1",
        "embedding": "TEXT",
    }
    changed = False
    for name, ddl in additions.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE action_journal ADD COLUMN {name} {ddl}")
            changed = True
    if changed:
        conn.commit()


def add_action(row: dict, *, durable: bool = False) -> str:
    """Append one journal row (a base 'action' or an event). The ONLY write path.

    Returns the row's action_id (generated if absent). `durable=True` forces the
    write to disk (`PRAGMA synchronous=FULL`) for the strict-journaling path — a
    meaningful mutation's record must survive a crash. Never UPDATEs; the
    append-only trigger would abort that anyway.
    """
    r = dict(row or {})
    action_id = str(r.get("action_id") or f"act_{uuid.uuid4().hex}")
    r["action_id"] = action_id
    r.setdefault("created_at", _now())
    r.setdefault("event_type", "action")
    for b in _JOURNAL_BOOLS:
        if b in r:
            r[b] = 1 if r[b] else 0
    cols = [c for c in JOURNAL_COLUMNS if c in r]
    placeholders = ", ".join("?" for _ in cols)
    conn = _connect()
    try:
        if durable:
            conn.execute("PRAGMA synchronous = FULL")
        conn.execute(
            f"INSERT INTO action_journal ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(r[c] for c in cols),
        )
        conn.commit()
    finally:
        conn.close()
    return action_id


def get_action(action_id: str) -> dict | None:
    """Return a single journal row by its action_id (base or event), or None."""
    conn = _connect()
    r = conn.execute(
        "SELECT * FROM action_journal WHERE action_id = ?", (str(action_id),)
    ).fetchone()
    conn.close()
    return dict(r) if r is not None else None


def get_action_events(parent_id: str) -> list[dict]:
    """Return the event rows (outcome/note/recovery) for a base action, oldest first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM action_journal WHERE parent_id = ? ORDER BY created_at ASC, rowid ASC",
        (str(parent_id),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_actions(
    limit: int = 50,
    *,
    capability: str | None = None,
    importance: str | None = None,
    conversation_id: int | None = None,
    milestone: bool | None = None,
    since: str | None = None,
) -> list[dict]:
    """List base actions (newest first), filtered. Event rows are excluded."""
    clauses = ["event_type = 'action'"]
    params: list = []
    if capability:
        clauses.append("capability = ?"); params.append(capability)
    if importance:
        clauses.append("importance = ?"); params.append(importance)
    if conversation_id is not None:
        clauses.append("conversation_id = ?"); params.append(conversation_id)
    if milestone is not None:
        clauses.append("milestone = ?"); params.append(1 if milestone else 0)
    if since:
        clauses.append("created_at >= ?"); params.append(since)
    where = " AND ".join(clauses)
    params.append(max(1, int(limit)))
    conn = _connect()
    rows = conn.execute(
        f"SELECT * FROM action_journal WHERE {where} ORDER BY created_at DESC, rowid DESC LIMIT ?",
        tuple(params),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
