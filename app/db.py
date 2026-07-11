"""Your AI's memory, stored in a local SQLite database.

Two kinds of memory live here:

  * conversations + messages — the running history of everything you've said
    to each other, so the AI has context and remembers across restarts.
  * memories — long-term facts about you (your name, what you're building,
    what you care about) that get woven into every conversation.

Everything is a plain file on your disk (data/memory.db). Nothing leaves
your machine.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "memory.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the tables if they don't exist yet. Safe to call every startup."""
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
            role            TEXT NOT NULL,        -- 'user' or 'assistant'
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS memories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            content    TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, id);
        """
    )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------
# Conversations & messages
# --------------------------------------------------------------------------

def get_or_create_active_conversation() -> int:
    """Return the id of the current conversation, creating one if needed."""
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
    """Archive the current conversation and begin a fresh one."""
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
    """Return messages in chronological order. If limit is set, the most recent N."""
    conn = _connect()
    if limit is None:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    else:
        # Grab the newest `limit`, then flip back to chronological order.
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
# Long-term memories (facts about you)
# --------------------------------------------------------------------------

def add_memory(content: str) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO memories (content, created_at) VALUES (?, ?)",
        (content.strip(), _now()),
    )
    mem_id = cur.lastrowid
    conn.commit()
    conn.close()
    return mem_id


def get_memories() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, content, created_at FROM memories ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_memory(memory_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()
