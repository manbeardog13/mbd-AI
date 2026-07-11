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

        CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, id);
        """
    )
    conn.commit()
    _migrate_memories(conn)
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
