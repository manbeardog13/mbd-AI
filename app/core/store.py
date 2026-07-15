"""Durable Core state, append-only events, approvals, and write leases."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from .contracts import (
    AgentResult,
    Approval,
    ApprovalStatus,
    Event,
    RiskLevel,
    Task,
    TaskStatus,
    VerificationProfile,
    VerificationRun,
    VerificationStatus,
)


Clock = Callable[[], datetime]


SCHEMA_VERSION = 2


# Kept as individual statements so schema creation and migration can stay inside
# the same explicit transaction.  sqlite3.executescript() may issue an implicit
# commit, which would make the migration event and its DDL separable on failure.
_LATEST_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS core_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_tasks (
        task_id TEXT PRIMARY KEY,
        objective TEXT NOT NULL,
        status TEXT NOT NULL,
        priority INTEGER NOT NULL,
        dependencies_json TEXT NOT NULL,
        acceptance_json TEXT NOT NULL,
        write_required INTEGER NOT NULL,
        repository TEXT NOT NULL,
        branch TEXT,
        worktree TEXT,
        assigned_adapter TEXT,
        context_version TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 0,
        result_json TEXT,
        blocker TEXT,
        verification_profile_id TEXT,
        verification_profile_version INTEGER,
        verification_profile_digest TEXT,
        verified_run_id TEXT
    )
    """,
    """CREATE INDEX IF NOT EXISTS idx_core_tasks_queue
       ON core_tasks(status, priority DESC, created_at ASC)""",
    """
    CREATE TABLE IF NOT EXISTS core_approvals (
        approval_id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        summary TEXT NOT NULL,
        risk TEXT NOT NULL,
        status TEXT NOT NULL,
        requested_by TEXT NOT NULL,
        requested_at TEXT NOT NULL,
        decided_at TEXT,
        decided_by TEXT,
        decision_note TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS core_events (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL UNIQUE,
        event_type TEXT NOT NULL,
        actor TEXT NOT NULL,
        task_id TEXT,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        previous_hash TEXT NOT NULL,
        event_hash TEXT NOT NULL UNIQUE
    )
    """,
    """CREATE INDEX IF NOT EXISTS idx_core_events_type_time
       ON core_events(event_type, created_at DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_core_events_task_time
       ON core_events(task_id, created_at DESC)""",
    """
    CREATE TRIGGER IF NOT EXISTS core_events_no_update
    BEFORE UPDATE ON core_events BEGIN
        SELECT RAISE(ABORT, 'core events are append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS core_events_no_delete
    BEFORE DELETE ON core_events BEGIN
        SELECT RAISE(ABORT, 'core events are append-only');
    END
    """,
    """
    CREATE TABLE IF NOT EXISTS core_verification_runs (
        run_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES core_tasks(task_id) ON DELETE RESTRICT,
        task_version INTEGER NOT NULL,
        attempt INTEGER NOT NULL CHECK(attempt > 0),
        profile_id TEXT NOT NULL,
        profile_version INTEGER NOT NULL,
        profile_digest TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN (
            'running', 'passed', 'failed', 'blocked', 'backend_unavailable',
            'timed_out', 'stale', 'error', 'interrupted'
        )),
        authoritative INTEGER NOT NULL DEFAULT 0 CHECK(authoritative IN (0, 1)),
        backend_id TEXT NOT NULL,
        backend_version TEXT NOT NULL,
        backend_capabilities_json TEXT NOT NULL,
        repository_key TEXT NOT NULL,
        repository TEXT NOT NULL,
        worktree TEXT NOT NULL,
        branch TEXT,
        head_before TEXT,
        head_after TEXT,
        clean_before INTEGER NOT NULL CHECK(clean_before IN (0, 1)),
        clean_after INTEGER NOT NULL CHECK(clean_after IN (0, 1)),
        lease_id TEXT,
        lease_fencing_token INTEGER,
        requested_at TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        workspace_after_json TEXT,
        evidence_json TEXT NOT NULL,
        evidence_hash TEXT UNIQUE,
        error_code TEXT,
        version INTEGER NOT NULL DEFAULT 0,
        UNIQUE(task_id, attempt),
        CHECK(authoritative = 0 OR status = 'passed'),
        CHECK(
            (status = 'running' AND completed_at IS NULL
             AND workspace_after_json IS NULL AND evidence_hash IS NULL)
            OR
            (status <> 'running' AND completed_at IS NOT NULL
             AND workspace_after_json IS NOT NULL AND evidence_hash IS NOT NULL)
        )
    )
    """,
    """CREATE INDEX IF NOT EXISTS idx_core_verification_runs_task_time
       ON core_verification_runs(task_id, requested_at DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_core_verification_runs_status_time
       ON core_verification_runs(status, requested_at DESC)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_core_verification_one_running_repository
       ON core_verification_runs(repository_key) WHERE status = 'running'""",
    """
    CREATE TRIGGER IF NOT EXISTS core_verification_runs_terminal_no_update
    BEFORE UPDATE ON core_verification_runs
    WHEN OLD.status <> 'running' OR NEW.status = 'running'
    BEGIN
        SELECT RAISE(ABORT, 'terminal verification runs are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS core_verification_runs_no_delete
    BEFORE DELETE ON core_verification_runs BEGIN
        SELECT RAISE(ABORT, 'verification runs are append-only');
    END
    """,
)


# Compatibility for callers which imported the old module-level schema string.
SCHEMA = ";\n".join(statement.strip() for statement in _LATEST_SCHEMA_STATEMENTS)


def _normalize_schema_sql(value: str | None) -> str:
    text = re.sub(r"\bIF\s+NOT\s+EXISTS\b", "", value or "", flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return re.sub(r"\s*([(),=<>])\s*", r"\1", text)


def _schema_statement_name(statement: str) -> str | None:
    match = re.search(
        r"\bCREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX|TRIGGER)\s+"
        r"(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
        statement,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


_CRITICAL_SCHEMA_NAMES = {
    "core_verification_runs",
    "idx_core_verification_one_running_repository",
    "core_events_no_update",
    "core_events_no_delete",
    "core_verification_runs_terminal_no_update",
    "core_verification_runs_no_delete",
}
_EXPECTED_CRITICAL_SCHEMA_SQL = {
    name: _normalize_schema_sql(statement)
    for statement in _LATEST_SCHEMA_STATEMENTS
    if (name := _schema_statement_name(statement)) in _CRITICAL_SCHEMA_NAMES
}


class StoreError(RuntimeError):
    """Raised when durable Core state cannot satisfy a requested operation."""


class SafeModeError(StoreError):
    """Raised when event integrity forces Core into read-only safe mode."""


class StoreConflict(StoreError):
    """Raised when a task changed after the caller observed it."""


class _ClosingConnection(sqlite3.Connection):
    """SQLite context manager that also releases the Windows file handle."""

    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat(timespec="milliseconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class CoreStore:
    """SQLite-backed Core state with one transaction per public mutation."""

    def __init__(self, db_path: str | Path, *, clock: Clock = _utc_now) -> None:
        self.db_path = Path(db_path).resolve()
        self.clock = clock
        self._safe_mode_reason: str | None = None

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            self._begin(conn)
            tables = self._table_names(conn)
            core_tables = {name for name in tables if name.startswith("core_")}

            # A genuinely new database is created directly at the latest schema.
            # The BEGIN IMMEDIATE lock makes two simultaneous initializers serialize.
            if not core_tables:
                self._execute_latest_schema(conn)
                conn.execute(
                    "INSERT INTO core_meta(key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
                conn.commit()
                return

            required_v1 = {
                "core_meta",
                "core_tasks",
                "core_approvals",
                "core_events",
            }
            missing_v1 = required_v1 - tables
            if missing_v1:
                self._enter_safe_mode(
                    "database schema is incomplete: " + ", ".join(sorted(missing_v1))
                )

            # Existing state is never mutated until its append-only history has
            # been checked.  This is deliberately inside the write transaction so
            # no competing migration can change the database between check and DDL.
            valid, message = self._verify_event_chain_conn(
                conn, allow_legacy_schema=True
            )
            if not valid:
                self._enter_safe_mode(message)

            raw_version = conn.execute(
                "SELECT value FROM core_meta WHERE key = 'schema_version'"
            ).fetchone()
            try:
                version = int(raw_version["value"]) if raw_version else 1
            except (TypeError, ValueError):
                self._enter_safe_mode("database schema version is invalid")

            if version > SCHEMA_VERSION:
                self._enter_safe_mode(
                    f"database schema version {version} is newer than supported "
                    f"version {SCHEMA_VERSION}"
                )
            if version < 1:
                self._enter_safe_mode(f"database schema version {version} is invalid")

            if version == 1:
                self._migrate_v1_to_v2(conn)
            else:
                self._validate_latest_schema_conn(conn)
            conn.commit()

    @staticmethod
    def _table_names(conn: sqlite3.Connection) -> set[str]:
        return {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    @staticmethod
    def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
        # Only internal constant table names are passed here.
        return {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }

    @staticmethod
    def _execute_latest_schema(conn: sqlite3.Connection) -> None:
        for statement in _LATEST_SCHEMA_STATEMENTS:
            conn.execute(statement)

    def _enter_safe_mode(self, reason: str) -> None:
        self._safe_mode_reason = reason
        raise SafeModeError(
            f"event integrity failed; read-only safe mode: {reason}"
        )

    def _migrate_v1_to_v2(self, conn: sqlite3.Connection) -> None:
        columns = self._column_names(conn, "core_tasks")
        additions = (
            (
                "version",
                "ALTER TABLE core_tasks ADD COLUMN version INTEGER NOT NULL DEFAULT 0",
            ),
            (
                "verification_profile_id",
                "ALTER TABLE core_tasks ADD COLUMN verification_profile_id TEXT",
            ),
            (
                "verification_profile_version",
                "ALTER TABLE core_tasks ADD COLUMN verification_profile_version INTEGER",
            ),
            (
                "verification_profile_digest",
                "ALTER TABLE core_tasks ADD COLUMN verification_profile_digest TEXT",
            ),
            (
                "verified_run_id",
                "ALTER TABLE core_tasks ADD COLUMN verified_run_id TEXT",
            ),
        )
        for column, statement in additions:
            if column not in columns:
                conn.execute(statement)

        self._execute_latest_schema(conn)
        legacy_meta = conn.execute(
            "SELECT key, value FROM core_meta WHERE key <> 'schema_version'"
        ).fetchall()
        for row in legacy_meta:
            key = str(row["key"])
            previous_value = str(row["value"])
            conn.execute("DELETE FROM core_meta WHERE key = ?", (key,))
            self._record_event(
                conn,
                "meta.invalidated",
                actor="nero-core",
                payload={
                    "meta_key": key,
                    "meta_deleted": True,
                    "previous_value_sha256": hashlib.sha256(
                        previous_value.encode("utf-8")
                    ).hexdigest(),
                    "reason": "legacy metadata has no M2 projection binding",
                },
            )
        conn.execute(
            """INSERT INTO core_meta(key, value) VALUES ('schema_version', ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (str(SCHEMA_VERSION),),
        )
        self._record_event(
            conn,
            "schema.migrated",
            actor="nero-core",
            payload={
                "from_version": 1,
                "to_version": SCHEMA_VERSION,
                "added_task_fields": [
                    "verification_profile_id",
                    "verification_profile_version",
                    "verification_profile_digest",
                    "verified_run_id",
                ],
                "added_tables": ["core_verification_runs"],
            },
        )
        self._validate_latest_schema_conn(conn)
        valid, message = self._verify_event_chain_conn(conn)
        if not valid:
            self._enter_safe_mode(message)

    def _validate_latest_schema_conn(self, conn: sqlite3.Connection) -> None:
        problem = self._latest_schema_problem(conn)
        if problem:
            self._enter_safe_mode(problem)

    def _latest_schema_problem(self, conn: sqlite3.Connection) -> str | None:
        tables = self._table_names(conn)
        required_tables = {
            "core_meta",
            "core_tasks",
            "core_approvals",
            "core_events",
            "core_verification_runs",
        }
        missing = required_tables - tables
        if missing:
            return (
                "database schema version 2 is incomplete: "
                + ", ".join(sorted(missing))
            )
        required_task_columns = {
            "version",
            "verification_profile_id",
            "verification_profile_version",
            "verification_profile_digest",
            "verified_run_id",
        }
        missing_columns = required_task_columns - self._column_names(
            conn, "core_tasks"
        )
        if missing_columns:
            return (
                "database schema version 2 is missing task fields: "
                + ", ".join(sorted(missing_columns))
            )
        required_run_columns = {
            "run_id",
            "task_id",
            "task_version",
            "attempt",
            "profile_id",
            "profile_version",
            "profile_digest",
            "status",
            "authoritative",
            "backend_id",
            "backend_version",
            "backend_capabilities_json",
            "repository_key",
            "repository",
            "worktree",
            "branch",
            "head_before",
            "head_after",
            "clean_before",
            "clean_after",
            "lease_id",
            "lease_fencing_token",
            "requested_at",
            "started_at",
            "completed_at",
            "workspace_after_json",
            "evidence_json",
            "evidence_hash",
            "error_code",
            "version",
        }
        missing_run_columns = required_run_columns - self._column_names(
            conn, "core_verification_runs"
        )
        if missing_run_columns:
            return (
                "database schema version 2 is missing verification fields: "
                + ", ".join(sorted(missing_run_columns))
            )
        artifacts = {
            str(row["name"]): _normalize_schema_sql(row["sql"])
            for row in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE name IN ("
                + ",".join("?" for _ in _CRITICAL_SCHEMA_NAMES)
                + ")",
                tuple(sorted(_CRITICAL_SCHEMA_NAMES)),
            ).fetchall()
        }
        missing_artifacts = _CRITICAL_SCHEMA_NAMES - set(artifacts)
        if missing_artifacts:
            return (
                "database schema version 2 is missing integrity artifacts: "
                + ", ".join(sorted(missing_artifacts))
            )
        for name, expected in _EXPECTED_CRITICAL_SCHEMA_SQL.items():
            if artifacts.get(name) != expected:
                return f"database integrity artifact definition changed: {name}"
        return None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path, timeout=5.0, factory=_ClosingConnection
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA synchronous = FULL")
        return conn

    def _begin(self, conn: sqlite3.Connection) -> None:
        conn.execute("BEGIN IMMEDIATE")

    def _record_event(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        *,
        actor: str,
        task_id: str | None = None,
        payload: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> Event:
        created = created_at or _iso(self.clock())
        event_id = str(uuid.uuid4())
        body = payload or {}
        payload_json = _canonical_json(body)
        previous = conn.execute(
            "SELECT event_hash FROM core_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = str(previous["event_hash"]) if previous else "GENESIS"
        digest_material = _canonical_json(
            {
                "event_id": event_id,
                "event_type": event_type,
                "actor": actor,
                "task_id": task_id,
                "payload": body,
                "created_at": created,
                "previous_hash": previous_hash,
            }
        )
        event_hash = hashlib.sha256(digest_material.encode("utf-8")).hexdigest()
        cursor = conn.execute(
            """
            INSERT INTO core_events(
                event_id, event_type, actor, task_id, payload_json, created_at,
                previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                actor,
                task_id,
                payload_json,
                created,
                previous_hash,
                event_hash,
            ),
        )
        return Event(
            sequence=int(cursor.lastrowid),
            event_id=event_id,
            event_type=event_type,
            actor=actor,
            task_id=task_id,
            payload=body,
            created_at=created,
            previous_hash=previous_hash,
            event_hash=event_hash,
        )

    def record_event(
        self,
        event_type: str,
        *,
        actor: str = "nero-core",
        task_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Event:
        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            event = self._record_event(
                conn, event_type, actor=actor, task_id=task_id, payload=payload
            )
            conn.commit()
            return event

    def list_events(
        self,
        *,
        event_type: str | None = None,
        task_id: str | None = None,
        limit: int = 200,
    ) -> list[Event]:
        clauses: list[str] = []
        args: list[Any] = []
        if event_type:
            clauses.append("event_type = ?")
            args.append(event_type)
        if task_id:
            clauses.append("task_id = ?")
            args.append(task_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.append(max(1, min(int(limit), 1000)))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM core_events {where} ORDER BY sequence DESC LIMIT ?",
                args,
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def list_events_after(
        self,
        *,
        after_sequence: int = 0,
        through_sequence: int | None = None,
        limit: int = 500,
    ) -> list[Event]:
        """Read an ascending cursor page without replaying earlier events."""
        upper = (
            self.latest_event_sequence()
            if through_sequence is None
            else max(0, int(through_sequence))
        )
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM core_events WHERE sequence > ? AND sequence <= ?
                   ORDER BY sequence ASC LIMIT ?""",
                (
                    max(0, int(after_sequence)),
                    upper,
                    max(1, min(int(limit), 1000)),
                ),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def latest_event_sequence(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM core_events"
            ).fetchone()
        return int(row["sequence"] if row else 0)

    def verify_event_chain(self) -> tuple[bool, str]:
        if self._safe_mode_reason:
            return False, self._safe_mode_reason
        try:
            with self._connect() as conn:
                result = self._verify_event_chain_conn(conn)
        except (
            sqlite3.Error,
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            json.JSONDecodeError,
        ) as exc:
            result = False, f"event chain unreadable: {type(exc).__name__}"
        if not result[0]:
            self._safe_mode_reason = result[1]
        return result

    def _verify_event_chain_conn(
        self,
        conn: sqlite3.Connection,
        *,
        allow_legacy_schema: bool = False,
    ) -> tuple[bool, str]:
        tables = self._table_names(conn)
        current_schema = False
        if "core_meta" in tables:
            version_row = conn.execute(
                "SELECT value FROM core_meta WHERE key = 'schema_version'"
            ).fetchone()
            if version_row is None:
                if not allow_legacy_schema:
                    return False, "database schema version metadata is missing"
                schema_version = 1
            else:
                try:
                    schema_version = int(version_row["value"])
                except (TypeError, ValueError):
                    return False, "database schema version is invalid"
            if schema_version == SCHEMA_VERSION:
                current_schema = True
                schema_problem = self._latest_schema_problem(conn)
                if schema_problem:
                    return False, schema_problem
            elif schema_version == 1 and allow_legacy_schema:
                task_columns = self._column_names(conn, "core_tasks")
                v2_task_columns = {
                    "verification_profile_id",
                    "verification_profile_version",
                    "verification_profile_digest",
                    "verified_run_id",
                }
                if (
                    "core_verification_runs" in tables
                    or bool(task_columns.intersection(v2_task_columns))
                ):
                    return (
                        False,
                        "database schema version metadata conflicts with M2 artifacts",
                    )
            elif schema_version > SCHEMA_VERSION:
                return (
                    False,
                    f"database schema version {schema_version} is newer than "
                    f"supported version {SCHEMA_VERSION}",
                )
            elif schema_version < 1:
                return False, f"database schema version {schema_version} is invalid"
            else:
                return (
                    False,
                    f"database schema version {schema_version} is not current; "
                    f"expected {SCHEMA_VERSION}",
                )
        rows = conn.execute("SELECT * FROM core_events ORDER BY sequence ASC").fetchall()
        previous_hash = "GENESIS"
        decoded_events: list[tuple[sqlite3.Row, dict[str, Any]]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except (TypeError, ValueError, json.JSONDecodeError):
                return False, f"event payload invalid at sequence {row['sequence']}"
            if not isinstance(payload, dict):
                return False, f"event payload invalid at sequence {row['sequence']}"
            material = _canonical_json(
                {
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "actor": row["actor"],
                    "task_id": row["task_id"],
                    "payload": payload,
                    "created_at": row["created_at"],
                    "previous_hash": row["previous_hash"],
                }
            )
            expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                return False, f"event chain failed at sequence {row['sequence']}"
            previous_hash = row["event_hash"]
            decoded_events.append((row, payload))

        if current_schema:
            valid, message = self._verify_meta_projections_conn(conn, decoded_events)
            if not valid:
                return valid, message

        if "core_verification_runs" in self._table_names(conn):
            valid, message = self._verify_verification_records_conn(
                conn, decoded_events
            )
            if not valid:
                return valid, message
            valid, message = self._verify_task_verification_projections_conn(
                conn, decoded_events
            )
            if not valid:
                return valid, message
        return True, f"event chain valid ({len(rows)} events)"

    @staticmethod
    def _verify_meta_projections_conn(
        conn: sqlite3.Connection,
        events: list[tuple[sqlite3.Row, dict[str, Any]]],
    ) -> tuple[bool, str]:
        latest: dict[str, dict[str, Any]] = {}
        for _, payload in events:
            key = payload.get("meta_key")
            if key is None:
                continue
            if not isinstance(key, str) or not key or key == "schema_version":
                return False, "Core metadata event has an invalid reserved key"
            if payload.get("meta_deleted") is True:
                if "value_sha256" in payload:
                    return False, f"metadata tombstone has a value digest for key {key}"
            else:
                digest = payload.get("value_sha256")
                if not isinstance(digest, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", digest
                ):
                    return False, f"metadata event has an invalid digest for key {key}"
            latest[key] = payload

        rows = conn.execute(
            "SELECT key, value FROM core_meta WHERE key <> 'schema_version'"
        ).fetchall()
        values = {str(row["key"]): str(row["value"]) for row in rows}
        for key, value in values.items():
            projection = latest.get(key)
            if projection is None or projection.get("meta_deleted") is True:
                return False, f"Core metadata row has no bound event for key {key}"
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            if projection.get("value_sha256") != digest:
                return False, f"Core metadata projection failed integrity for key {key}"
        for key, projection in latest.items():
            if projection.get("meta_deleted") is True:
                if key in values:
                    return False, f"deleted Core metadata was restored for key {key}"
            elif key not in values:
                return False, f"Core metadata event has no row for key {key}"
        return True, "Core metadata projections valid"

    def _verify_task_verification_projections_conn(
        self,
        conn: sqlite3.Connection,
        events: list[tuple[sqlite3.Row, dict[str, Any]]],
    ) -> tuple[bool, str]:
        profile_events: dict[str, dict[str, Any]] = {}
        m2_task_ids: set[str] = set()
        for event_row, payload in events:
            if (
                event_row["event_type"] == "task.queued"
                and payload.get("context_version") == "mission-control-m2"
                and isinstance(event_row["task_id"], str)
            ):
                m2_task_ids.add(str(event_row["task_id"]))
            if event_row["event_type"] != "verification.profile_bound":
                continue
            task_id = event_row["task_id"]
            if not isinstance(task_id, str) or not task_id:
                return (
                    False,
                    "verification.profile_bound event has no task projection at "
                    f"sequence {event_row['sequence']}",
                )
            if task_id in profile_events:
                return False, f"task {task_id} has duplicate profile binding events"
            profile_events[task_id] = payload

        task_rows = conn.execute("SELECT * FROM core_tasks").fetchall()
        tasks = {str(row["task_id"]): row for row in task_rows}
        for task_id, task_row in tasks.items():
            projection = (
                task_row["verification_profile_id"],
                task_row["verification_profile_version"],
                task_row["verification_profile_digest"],
            )
            populated = tuple(value is not None for value in projection)
            if any(populated) and not all(populated):
                return False, f"task {task_id} has a partial profile projection"
            profile_event = profile_events.get(task_id)
            if all(populated):
                if profile_event is None:
                    return False, f"task {task_id} is missing its profile binding event"
                event_projection = (
                    profile_event.get("profile_id"),
                    profile_event.get("profile_version"),
                    profile_event.get("profile_digest"),
                )
                expected_projection = (
                    projection[0],
                    int(projection[1]),
                    projection[2],
                )
                if event_projection != expected_projection:
                    return False, f"task {task_id} profile projection failed integrity"
            elif profile_event is not None:
                return False, f"task {task_id} profile event has no pinned projection"

            verified_run_id = task_row["verified_run_id"]
            if verified_run_id is None:
                if (
                    task_row["status"] == TaskStatus.COMPLETE.value
                    and (
                        all(populated)
                        or task_id in m2_task_ids
                        or task_row["context_version"] == "mission-control-m2"
                    )
                ):
                    return (
                        False,
                        f"M2 completed task {task_id} has no verified run projection",
                    )
                continue
            verified = conn.execute(
                "SELECT * FROM core_verification_runs WHERE run_id = ?",
                (verified_run_id,),
            ).fetchone()
            if verified is None:
                return False, f"task {task_id} references an unknown verified run"
            if (
                verified["task_id"] != task_id
                or verified["status"] != VerificationStatus.PASSED.value
                or not bool(verified["authoritative"])
                or task_row["status"] != TaskStatus.COMPLETE.value
            ):
                return False, f"task {task_id} verified run projection failed integrity"

        orphaned_profiles = set(profile_events) - set(tasks)
        if orphaned_profiles:
            return (
                False,
                "profile binding event has no task projection for task "
                + sorted(orphaned_profiles)[0],
            )

        authoritative_rows = conn.execute(
            """SELECT run_id, task_id FROM core_verification_runs
               WHERE status = ? AND authoritative = 1""",
            (VerificationStatus.PASSED.value,),
        ).fetchall()
        for run_row in authoritative_rows:
            task_row = tasks.get(str(run_row["task_id"]))
            if (
                task_row is None
                or task_row["status"] != TaskStatus.COMPLETE.value
                or task_row["verified_run_id"] != run_row["run_id"]
            ):
                return (
                    False,
                    "authoritative verification has no trusted task projection for run "
                    + str(run_row["run_id"]),
                )
        return True, "task verification projections valid"

    def _verify_verification_records_conn(
        self,
        conn: sqlite3.Connection,
        events: list[tuple[sqlite3.Row, dict[str, Any]]],
    ) -> tuple[bool, str]:
        started_events: dict[str, tuple[sqlite3.Row, dict[str, Any]]] = {}
        recorded_events: dict[str, tuple[sqlite3.Row, dict[str, Any]]] = {}
        transition_events: dict[str, tuple[sqlite3.Row, dict[str, Any]]] = {}
        for event_row, payload in events:
            if event_row["event_type"] == "task.transitioned":
                verification_run_id = payload.get("verification_run_id")
                if verification_run_id is not None:
                    if not isinstance(verification_run_id, str) or not verification_run_id:
                        return (
                            False,
                            "verification task transition has invalid run identity at "
                            f"sequence {event_row['sequence']}",
                        )
                    if verification_run_id in transition_events:
                        return (
                            False,
                            "duplicate verification task transition for run "
                            + verification_run_id,
                        )
                    transition_events[verification_run_id] = (event_row, payload)
                continue
            if event_row["event_type"] not in {
                "verification.started",
                "verification.recorded",
            }:
                continue
            run_id = payload.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                return (
                    False,
                    f"{event_row['event_type']} event missing run_id at sequence "
                    f"{event_row['sequence']}",
                )
            target = (
                started_events
                if event_row["event_type"] == "verification.started"
                else recorded_events
            )
            if run_id in target:
                return False, f"duplicate verification.recorded event for run {run_id}"
            target[run_id] = (event_row, payload)

        run_rows = conn.execute(
            "SELECT * FROM core_verification_runs ORDER BY requested_at ASC, run_id ASC"
        ).fetchall()
        seen_started: set[str] = set()
        seen_terminal: set[str] = set()
        for run_row in run_rows:
            run_id = str(run_row["run_id"])
            status = str(run_row["status"])
            started_entry = started_events.get(run_id)
            if started_entry is None:
                return False, f"verification run {run_id} is missing its started event"
            started_row, started_payload = started_entry
            if started_row["task_id"] != run_row["task_id"]:
                return False, f"verification start task binding failed for run {run_id}"
            expected_start = {
                "run_id": run_id,
                "task_version": int(run_row["task_version"]),
                "attempt": int(run_row["attempt"]),
                "profile_id": run_row["profile_id"],
                "profile_version": int(run_row["profile_version"]),
                "profile_digest": run_row["profile_digest"],
                "backend_id": run_row["backend_id"],
                "backend_version": run_row["backend_version"],
                "repository_key": run_row["repository_key"],
                "repository": run_row["repository"],
                "worktree": run_row["worktree"],
                "branch": run_row["branch"],
                "head_before": run_row["head_before"],
                "clean_before": bool(run_row["clean_before"]),
                "lease_id": run_row["lease_id"],
                "lease_fencing_token": run_row["lease_fencing_token"],
                "from_task_version": int(run_row["task_version"]),
                "to_task_version": int(run_row["task_version"]) + 1,
            }
            if started_payload != expected_start:
                return False, f"verification start receipt binding failed for run {run_id}"
            seen_started.add(run_id)
            event_entry = recorded_events.get(run_id)
            if status == VerificationStatus.RUNNING.value:
                if event_entry is not None:
                    return False, f"running verification run {run_id} has terminal event"
                task_row = conn.execute(
                    "SELECT * FROM core_tasks WHERE task_id = ?",
                    (run_row["task_id"],),
                ).fetchone()
                if task_row is None or (
                    task_row["status"] != TaskStatus.VERIFYING.value
                    or int(task_row["version"]) != int(run_row["task_version"]) + 1
                    or task_row["verification_profile_id"] != run_row["profile_id"]
                    or task_row["verification_profile_version"]
                    != run_row["profile_version"]
                    or task_row["verification_profile_digest"]
                    != run_row["profile_digest"]
                    or task_row["repository"] != run_row["repository"]
                    or task_row["worktree"] != run_row["worktree"]
                    or task_row["branch"] != run_row["branch"]
                    or task_row["verified_run_id"] is not None
                ):
                    return False, f"running verification task projection failed for run {run_id}"
                try:
                    running_evidence = json.loads(run_row["evidence_json"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    return False, f"running verification evidence invalid for run {run_id}"
                if running_evidence != {}:
                    return False, f"running verification run {run_id} has terminal evidence"
                continue

            try:
                evidence = json.loads(run_row["evidence_json"])
            except (TypeError, ValueError, json.JSONDecodeError):
                return False, f"verification evidence unreadable for run {run_id}"
            if not isinstance(evidence, dict):
                return False, f"verification evidence invalid for run {run_id}"
            evidence_problem = self._verification_evidence_problem(run_row, evidence)
            if evidence_problem:
                return False, f"{evidence_problem} for run {run_id}"
            expected_hash = self.calculate_evidence_hash(evidence)
            if run_row["evidence_hash"] != expected_hash:
                return False, f"verification evidence hash failed for run {run_id}"
            if event_entry is None:
                return False, f"verification run {run_id} is missing its recorded event"

            event_row, payload = event_entry
            if event_row["task_id"] != run_row["task_id"]:
                return False, f"verification event task binding failed for run {run_id}"
            if payload.get("evidence_hash") != expected_hash:
                return False, f"verification event evidence hash failed for run {run_id}"
            if (
                payload.get("status") != run_row["status"]
                or payload.get("authoritative") is not bool(run_row["authoritative"])
            ):
                return False, f"verification event result binding failed for run {run_id}"
            try:
                expected_receipt = self._verification_receipt_from_row(run_row)
            except (TypeError, ValueError, json.JSONDecodeError):
                return False, f"verification receipt unreadable for run {run_id}"
            task_terminal_status = (
                TaskStatus.COMPLETE.value
                if status == VerificationStatus.PASSED.value
                and bool(run_row["authoritative"])
                else (
                    TaskStatus.FAILED.value
                    if status
                    in {
                        VerificationStatus.FAILED.value,
                        VerificationStatus.TIMED_OUT.value,
                    }
                    else TaskStatus.BLOCKED.value
                )
            )
            claimed_task_version = int(run_row["task_version"]) + 1
            expected_recorded = {
                "run_id": run_id,
                "status": status,
                "authoritative": bool(run_row["authoritative"]),
                "evidence_hash": expected_hash,
                "receipt": expected_receipt,
                "task_terminal_status": task_terminal_status,
                "from_task_version": claimed_task_version,
                "to_task_version": claimed_task_version + 1,
            }
            if payload != expected_recorded:
                return False, f"verification receipt binding failed for run {run_id}"
            if event_row["created_at"] != run_row["completed_at"]:
                return False, f"verification event time binding failed for run {run_id}"

            transition_entry = transition_events.get(run_id)
            if transition_entry is None:
                return False, f"verification run {run_id} is missing its task transition"
            transition_row, transition_payload = transition_entry
            expected_transition_fields = {
                "from": TaskStatus.VERIFYING.value,
                "to": task_terminal_status,
                "result": None,
                "verified_run_id": (
                    run_id if task_terminal_status == TaskStatus.COMPLETE.value else None
                ),
                "verification_run_id": run_id,
                "from_version": claimed_task_version,
                "to_version": claimed_task_version + 1,
            }
            if (
                transition_row["task_id"] != run_row["task_id"]
                or transition_row["created_at"] != run_row["completed_at"]
                or set(transition_payload)
                != set(expected_transition_fields).union({"blocker"})
                or any(
                    transition_payload.get(key) != value
                    for key, value in expected_transition_fields.items()
                )
                or (
                    task_terminal_status == TaskStatus.COMPLETE.value
                    and transition_payload.get("blocker") is not None
                )
                or (
                    task_terminal_status != TaskStatus.COMPLETE.value
                    and not isinstance(transition_payload.get("blocker"), str)
                )
            ):
                return False, f"verification task transition binding failed for run {run_id}"
            seen_terminal.add(run_id)

        orphaned_starts = set(started_events) - seen_started
        if orphaned_starts:
            return (
                False,
                "verification.started event has no run row for run "
                + sorted(orphaned_starts)[0],
            )
        orphaned_records = set(recorded_events) - seen_terminal
        if orphaned_records:
            return (
                False,
                "verification.recorded event has no terminal row for run "
                + sorted(orphaned_records)[0],
            )
        orphaned_transitions = set(transition_events) - seen_terminal
        if orphaned_transitions:
            return (
                False,
                "verification task transition has no terminal run for run "
                + sorted(orphaned_transitions)[0],
            )
        return True, f"verification records valid ({len(seen_terminal)} terminal runs)"

    @staticmethod
    def _verification_evidence_problem(
        run_row: sqlite3.Row, evidence: Mapping[str, Any]
    ) -> str | None:
        try:
            capabilities = json.loads(run_row["backend_capabilities_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            return "verification backend capabilities are unreadable"
        capability_booleans = {
            "execution_available",
            "network_disabled",
            "rootfs_readonly",
            "snapshot_readonly",
            "runs_as_nonroot",
            "host_credentials_unavailable",
            "host_devices_unavailable",
            "docker_socket_unavailable",
            "child_process_limit",
            "memory_limit_supported",
            "cpu_limit_supported",
            "timeout_supported",
            "output_limit_supported",
            "no_new_privileges",
            "capabilities_dropped",
            "test_only",
        }
        capability_strings = {
            "backend_id",
            "backend_version",
            "isolation_level",
            "os_family",
        }
        if (
            not isinstance(capabilities, dict)
            or set(capabilities) != capability_booleans | capability_strings
            or any(
                type(capabilities.get(name)) is not bool
                for name in capability_booleans
            )
            or any(
                type(capabilities.get(name)) is not str
                or not capabilities[name].strip()
                or len(capabilities[name]) > 200
                or any(ord(character) < 32 for character in capabilities[name])
                for name in capability_strings
            )
        ):
            return "verification backend capabilities are invalid"
        if (
            capabilities["backend_id"] != run_row["backend_id"]
            or capabilities["backend_version"] != run_row["backend_version"]
        ):
            return "verification backend capability identity is invalid"
        binding = evidence.get("binding")
        expected_binding = {
            "run_id": run_row["run_id"],
            "task_id": run_row["task_id"],
            "task_version": int(run_row["task_version"]),
            "attempt": int(run_row["attempt"]),
            "profile_id": run_row["profile_id"],
            "profile_version": int(run_row["profile_version"]),
            "profile_digest": run_row["profile_digest"],
            "backend_id": run_row["backend_id"],
            "backend_version": run_row["backend_version"],
            "repository_key": run_row["repository_key"],
            "lease_id": run_row["lease_id"],
            "lease_fencing_token": run_row["lease_fencing_token"],
        }
        if binding != expected_binding:
            return "verification evidence binding failed"
        profile = evidence.get("profile")
        if not isinstance(profile, dict) or (
            profile.get("profile_id") != run_row["profile_id"]
            or profile.get("version") != int(run_row["profile_version"])
            or profile.get("manifest_digest") != run_row["profile_digest"]
        ):
            return "verification evidence profile binding failed"
        recovery_projection = {
            "profile_id": run_row["profile_id"],
            "version": int(run_row["profile_version"]),
            "manifest_digest": run_row["profile_digest"],
            "recovery_projection_only": True,
        }
        if profile == recovery_projection:
            if not (
                run_row["status"] == VerificationStatus.INTERRUPTED.value
                and run_row["error_code"] == "VERIFICATION_PROCESS_INTERRUPTED"
            ):
                return "verification recovery profile projection is not permitted"
        else:
            manifest = dict(profile)
            manifest_digest = manifest.pop("manifest_digest", None)
            recomputed_digest = hashlib.sha256(
                _canonical_json(manifest).encode("utf-8")
            ).hexdigest()
            if (
                manifest_digest != run_row["profile_digest"]
                or recomputed_digest != run_row["profile_digest"]
            ):
                return "verification evidence profile manifest digest failed"
        backend = evidence.get("backend")
        if (
            not isinstance(backend, dict)
            or set(backend) != {
                "capabilities",
                "authorized",
                "missing_capabilities",
            }
            or backend.get("capabilities") != capabilities
            or type(backend.get("authorized")) is not bool
            or not isinstance(backend.get("missing_capabilities"), list)
            or any(
                not isinstance(item, str) or not item
                for item in backend.get("missing_capabilities", [])
            )
            or backend.get("missing_capabilities")
            != sorted(set(backend.get("missing_capabilities", [])))
        ):
            return "verification evidence backend binding failed"
        expected_before = {
            "repository_key": run_row["repository_key"],
            "repository": run_row["repository"],
            "worktree": run_row["worktree"],
            "branch": run_row["branch"],
            "head": run_row["head_before"],
            "clean": bool(run_row["clean_before"]),
            "conflict_count": 0,
            "detached_head": False,
        }
        if evidence.get("workspace_before") != expected_before:
            return "verification evidence starting workspace binding failed"
        workspace_after = evidence.get("workspace_after")
        try:
            recorded_after = json.loads(run_row["workspace_after_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            return "verification recorded final workspace is unreadable"
        expected_workspace_keys = {
            "repository_key",
            "repository",
            "worktree",
            "branch",
            "head",
            "clean",
            "conflict_count",
            "detached_head",
        }
        if (
            not isinstance(workspace_after, dict)
            or not isinstance(recorded_after, dict)
            or set(workspace_after) != expected_workspace_keys
            or workspace_after != recorded_after
            or workspace_after.get("head") != run_row["head_after"]
            or workspace_after.get("clean") is not bool(run_row["clean_after"])
            or type(workspace_after.get("conflict_count")) is not int
            or int(workspace_after["conflict_count"]) < 0
            or type(workspace_after.get("detached_head")) is not bool
        ):
            return "verification evidence final workspace binding failed"
        workspace_drift_visible = bool(
            workspace_after.get("repository_key") != run_row["repository_key"]
            or workspace_after.get("repository") != run_row["repository"]
            or workspace_after.get("worktree") != run_row["worktree"]
            or workspace_after.get("branch") != run_row["branch"]
            or workspace_after.get("head") != run_row["head_before"]
            or workspace_after.get("clean") is not True
            or workspace_after.get("conflict_count") != 0
            or workspace_after.get("detached_head") is not False
        )
        drift = evidence.get("drift")
        if (
            not isinstance(drift, list)
            or any(not isinstance(item, str) or not item for item in drift)
            or drift != sorted(set(drift))
            or (workspace_drift_visible and "workspace_drift" not in drift)
        ):
            return "verification evidence final workspace binding failed"
        if (
            evidence.get("final_status") != run_row["status"]
            or evidence.get("authoritative") is not bool(run_row["authoritative"])
            or evidence.get("requested_at") != run_row["requested_at"]
            or evidence.get("completed_at") != run_row["completed_at"]
        ):
            return "verification evidence terminal binding failed"
        runner_result = evidence.get("runner_result")
        expected_runner_keys = {
            "status",
            "exit_code",
            "duration_ms",
            "stdout_sha256",
            "stderr_sha256",
            "stdout_excerpt",
            "stderr_excerpt",
            "output_truncated",
            "error_code",
            "detail",
        }
        if (
            not isinstance(runner_result, dict)
            or set(runner_result) != expected_runner_keys
            or (
                runner_result.get("exit_code") is not None
                and type(runner_result.get("exit_code")) is not int
            )
            or type(runner_result.get("duration_ms")) is not int
            or int(runner_result.get("duration_ms", -1)) < 0
            or type(runner_result.get("stdout_sha256")) is not str
            or re.fullmatch(
                r"[0-9a-f]{64}", runner_result.get("stdout_sha256", "")
            )
            is None
            or type(runner_result.get("stderr_sha256")) is not str
            or re.fullmatch(
                r"[0-9a-f]{64}", runner_result.get("stderr_sha256", "")
            )
            is None
            or type(runner_result.get("stdout_excerpt")) is not str
            or len(runner_result.get("stdout_excerpt", "").encode("utf-8")) > 4096
            or type(runner_result.get("stderr_excerpt")) is not str
            or len(runner_result.get("stderr_excerpt", "").encode("utf-8")) > 4096
            or type(runner_result.get("output_truncated")) is not bool
            or (
                runner_result.get("error_code") is not None
                and (
                    type(runner_result.get("error_code")) is not str
                    or len(runner_result.get("error_code", "")) > 200
                    or any(
                        ord(character) < 32
                        for character in runner_result.get("error_code", "")
                    )
                )
            )
            or type(runner_result.get("detail")) is not str
            or len(runner_result.get("detail", "").encode("utf-8")) > 1000
        ):
            return "verification runner evidence is invalid"
        try:
            runner_status = VerificationStatus(runner_result.get("status"))
        except (TypeError, ValueError):
            return "verification runner status is invalid"
        if run_row["status"] == VerificationStatus.PASSED.value:
            if (
                not bool(run_row["authoritative"])
                or runner_status is not VerificationStatus.PASSED
                or type(runner_result.get("exit_code")) is not int
                or runner_result.get("exit_code") != 0
                or backend.get("authorized") is not True
                or backend.get("missing_capabilities") != []
                or evidence.get("drift") != []
                or workspace_after.get("repository_key") != run_row["repository_key"]
                or workspace_after.get("repository") != run_row["repository"]
                or workspace_after.get("worktree") != run_row["worktree"]
                or workspace_after.get("branch") != run_row["branch"]
                or workspace_after.get("head") != run_row["head_before"]
                or workspace_after.get("clean") is not True
                or workspace_after.get("conflict_count") != 0
                or workspace_after.get("detached_head") is not False
            ):
                return "authoritative pass evidence is inconsistent"
        return None

    def _assert_writable(self, conn: sqlite3.Connection) -> None:
        if self._safe_mode_reason:
            raise SafeModeError(
                "event integrity failed; read-only safe mode: "
                + self._safe_mode_reason
            )
        valid, message = self._verify_event_chain_conn(conn)
        if not valid:
            self._safe_mode_reason = message
            raise SafeModeError(
                f"event integrity failed; read-only safe mode: {message}"
            )

    def create_task(
        self,
        *,
        objective: str,
        repository: str,
        priority: int = 50,
        dependencies: tuple[str, ...] = (),
        acceptance_criteria: tuple[str, ...] = (),
        write_required: bool = False,
        branch: str | None = None,
        worktree: str | None = None,
        context_version: str = "mission-control-m2",
        actor: str = "operator",
    ) -> Task:
        objective = objective.strip()
        if not objective:
            raise StoreError("task objective is required")
        task_id = str(uuid.uuid4())
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            conn.execute(
                """
                INSERT INTO core_tasks(
                    task_id, objective, status, priority, dependencies_json,
                    acceptance_json, write_required, repository, branch,
                    worktree, assigned_adapter, context_version, created_at,
                    updated_at, version, result_json, blocker
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, 0, NULL, NULL)
                """,
                (
                    task_id,
                    objective,
                    TaskStatus.QUEUED.value,
                    int(priority),
                    _canonical_json(list(dependencies)),
                    _canonical_json(list(acceptance_criteria)),
                    int(write_required),
                    str(Path(repository).resolve()),
                    branch,
                    worktree,
                    context_version,
                    now,
                    now,
                ),
            )
            self._record_event(
                conn,
                "task.queued",
                actor=actor,
                task_id=task_id,
                payload={
                    "objective": objective,
                    "priority": int(priority),
                    "write_required": bool(write_required),
                    "dependencies": list(dependencies),
                    "context_version": context_version,
                },
                created_at=now,
            )
            conn.commit()
        task = self.get_task(task_id)
        if task is None:  # pragma: no cover - defensive invariant
            raise StoreError("created task could not be reloaded")
        return task

    def get_task(self, task_id: str) -> Task | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return self._task_from_row(row) if row else None

    def list_tasks(self, *, status: TaskStatus | None = None) -> list[Task]:
        with self._connect() as conn:
            if status is None:
                rows = conn.execute(
                    "SELECT * FROM core_tasks ORDER BY priority DESC, created_at ASC"
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM core_tasks WHERE status = ?
                       ORDER BY priority DESC, created_at ASC""",
                    (status.value,),
                ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def bind_verification_profile(
        self,
        task_id: str,
        *,
        profile: VerificationProfile,
        expected_version: int,
        actor: str = "nero-core",
    ) -> Task:
        """Pin one immutable, code-owned verification manifest to a task."""
        if not profile.profile_id.strip() or not profile.manifest_digest.strip():
            raise StoreError("verification profile identity and digest are required")
        if int(profile.version) < 1:
            raise StoreError("verification profile version must be positive")
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            row = conn.execute(
                "SELECT * FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise StoreError(f"unknown task: {task_id}")
            if int(row["version"]) != int(expected_version):
                raise StoreConflict(
                    f"task version changed: expected {expected_version}, "
                    f"found {row['version']}"
                )
            existing = (
                row["verification_profile_id"],
                row["verification_profile_version"],
                row["verification_profile_digest"],
            )
            requested = (
                profile.profile_id,
                int(profile.version),
                profile.manifest_digest,
            )
            if existing == requested:
                conn.commit()
                return self._task_from_row(row)
            if any(value is not None for value in existing):
                raise StoreConflict(
                    "task verification profile is already pinned and cannot be replaced"
                )
            if TaskStatus(row["status"]) in {
                TaskStatus.COMPLETE,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                raise StoreConflict("terminal tasks cannot bind a verification profile")

            updated = conn.execute(
                """UPDATE core_tasks
                   SET verification_profile_id = ?,
                       verification_profile_version = ?,
                       verification_profile_digest = ?,
                       updated_at = ?, version = version + 1
                   WHERE task_id = ? AND version = ?
                     AND verification_profile_id IS NULL
                     AND verification_profile_version IS NULL
                     AND verification_profile_digest IS NULL""",
                (
                    profile.profile_id,
                    int(profile.version),
                    profile.manifest_digest,
                    now,
                    task_id,
                    int(expected_version),
                ),
            )
            if updated.rowcount != 1:
                raise StoreConflict("verification profile binding lost an atomic race")
            self._record_event(
                conn,
                "verification.profile_bound",
                actor=actor,
                task_id=task_id,
                payload={
                    "profile_id": profile.profile_id,
                    "profile_version": int(profile.version),
                    "profile_digest": profile.manifest_digest,
                    "from_version": int(expected_version),
                    "to_version": int(expected_version) + 1,
                },
                created_at=now,
            )
            bound_row = conn.execute(
                "SELECT * FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            conn.commit()
        if bound_row is None:  # pragma: no cover - transactional invariant
            raise StoreError("profile-bound task could not be reloaded")
        return self._task_from_row(bound_row)

    def assign_task(
        self,
        task_id: str,
        *,
        adapter_id: str,
        branch: str | None,
        worktree: str | None,
        expected_version: int,
        actor: str = "nero-core",
    ) -> Task:
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            row = conn.execute(
                "SELECT status, version FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise StoreError(f"unknown task: {task_id}")
            if row["status"] != TaskStatus.QUEUED.value:
                raise StoreConflict(
                    f"task {task_id} is {row['status']}, not queued"
                )
            if int(row["version"]) != int(expected_version):
                raise StoreConflict(
                    f"task version changed: expected {expected_version}, "
                    f"found {row['version']}"
                )
            updated = conn.execute(
                """UPDATE core_tasks
                   SET status = ?, assigned_adapter = ?, branch = ?, worktree = ?,
                       blocker = NULL, updated_at = ?, version = version + 1
                   WHERE task_id = ? AND status = ? AND version = ?""",
                (
                    TaskStatus.PREPARING.value,
                    adapter_id,
                    branch,
                    worktree,
                    now,
                    task_id,
                    TaskStatus.QUEUED.value,
                    int(expected_version),
                ),
            )
            if updated.rowcount != 1:  # pragma: no cover - transaction invariant
                raise StoreConflict("task assignment lost an atomic status race")
            self._record_event(
                conn,
                "task.assigned",
                actor=actor,
                task_id=task_id,
                payload={
                    "from": row["status"],
                    "to": TaskStatus.PREPARING.value,
                    "adapter": adapter_id,
                    "branch": branch,
                    "worktree": worktree,
                    "from_version": int(expected_version),
                    "to_version": int(expected_version) + 1,
                },
                created_at=now,
            )
            assigned_row = conn.execute(
                "SELECT * FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            conn.commit()
        if assigned_row is None:  # pragma: no cover
            raise StoreError("assigned task could not be reloaded")
        return self._task_from_row(assigned_row)

    def transition_task(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        expected_status: TaskStatus,
        expected_version: int,
        blocker: str | None = None,
        result: AgentResult | None = None,
        actor: str = "nero-core",
    ) -> Task:
        if status is TaskStatus.COMPLETE:
            raise StoreError(
                "task completion is owned by Core verification; "
                "finalize an authoritative passed verification run"
            )
        if expected_status is TaskStatus.COMPLETE:
            raise StoreConflict("completed tasks are immutable")
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            active_run = conn.execute(
                """SELECT run_id FROM core_verification_runs
                   WHERE task_id = ? AND status = ? LIMIT 1""",
                (task_id, VerificationStatus.RUNNING.value),
            ).fetchone()
            if active_run is not None:
                raise StoreConflict(
                    "task state is owned by active verification run "
                    + str(active_run["run_id"])
                )
            row = conn.execute(
                "SELECT status, version FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise StoreError(f"unknown task: {task_id}")
            if row["status"] != expected_status.value:
                raise StoreConflict(
                    f"task status changed: expected {expected_status.value}, "
                    f"found {row['status']}"
                )
            if int(row["version"]) != int(expected_version):
                raise StoreConflict(
                    f"task version changed: expected {expected_version}, "
                    f"found {row['version']}"
                )
            result_json = _canonical_json(result.as_dict()) if result else None
            updated = conn.execute(
                """UPDATE core_tasks
                   SET status = ?, blocker = ?, result_json = COALESCE(?, result_json),
                       updated_at = ?, version = version + 1
                   WHERE task_id = ? AND status = ? AND version = ?""",
                (
                    status.value,
                    blocker,
                    result_json,
                    now,
                    task_id,
                    expected_status.value,
                    int(expected_version),
                ),
            )
            if updated.rowcount != 1:  # pragma: no cover - transaction invariant
                raise StoreConflict("task transition lost an atomic status race")
            self._record_event(
                conn,
                "task.transitioned",
                actor=actor,
                task_id=task_id,
                payload={
                    "from": row["status"],
                    "to": status.value,
                    "blocker": blocker,
                    "result": result.as_dict() if result else None,
                    "from_version": int(expected_version),
                    "to_version": int(expected_version) + 1,
                },
                created_at=now,
            )
            transitioned_row = conn.execute(
                "SELECT * FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            conn.commit()
        if transitioned_row is None:  # pragma: no cover
            raise StoreError("transitioned task could not be reloaded")
        return self._task_from_row(transitioned_row)

    @staticmethod
    def calculate_evidence_hash(evidence: Mapping[str, Any]) -> str:
        """Return the canonical evidence digest used by rows and journal events."""
        return hashlib.sha256(
            _canonical_json(dict(evidence)).encode("utf-8")
        ).hexdigest()

    def begin_verification_run(
        self,
        run: VerificationRun,
        *,
        expected_task_status: TaskStatus = TaskStatus.VERIFYING,
        expected_task_version: int,
        actor: str = "nero-core",
    ) -> VerificationRun:
        """Atomically claim a task/repository for one RUNNING verification."""
        if run.status is not VerificationStatus.RUNNING:
            raise StoreError("new verification runs must have running status")
        if run.authoritative:
            raise StoreError("a running verification cannot be authoritative")
        if run.completed_at is not None or run.evidence_hash is not None:
            raise StoreError("a running verification cannot contain terminal evidence")
        if run.evidence != {} or run.error_code is not None:
            raise StoreError("a running verification must start with empty evidence")
        if int(run.version) != 0:
            raise StoreError("new verification runs must start at version 0")
        if run.task_version != int(expected_task_version):
            raise StoreConflict("verification run carries a stale task version")
        if not run.run_id.strip() or not run.repository_key.strip():
            raise StoreError("verification run and repository identities are required")

        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            task_row = conn.execute(
                "SELECT * FROM core_tasks WHERE task_id = ?", (run.task_id,)
            ).fetchone()
            if task_row is None:
                raise StoreError(f"unknown task: {run.task_id}")
            if task_row["status"] != expected_task_status.value:
                raise StoreConflict(
                    f"task status changed: expected {expected_task_status.value}, "
                    f"found {task_row['status']}"
                )
            if int(task_row["version"]) != int(expected_task_version):
                raise StoreConflict(
                    f"task version changed: expected {expected_task_version}, "
                    f"found {task_row['version']}"
                )
            task_profile = (
                task_row["verification_profile_id"],
                task_row["verification_profile_version"],
                task_row["verification_profile_digest"],
            )
            run_profile = (
                run.profile_id,
                int(run.profile_version),
                run.profile_digest,
            )
            if task_profile != run_profile:
                raise StoreConflict(
                    "verification run does not match the task's pinned profile"
                )
            if task_row["repository"] != run.repository:
                raise StoreConflict("verification repository changed after task claim")
            if task_row["worktree"] != run.worktree:
                raise StoreConflict("verification worktree changed after task claim")
            if task_row["branch"] != run.branch:
                raise StoreConflict("verification branch changed after task claim")
            if bool(task_row["write_required"]) and (
                not run.lease_id or run.lease_fencing_token is None
            ):
                raise StoreConflict(
                    "write verification requires a lease id and fencing token"
                )

            attempt_row = conn.execute(
                """SELECT COALESCE(MAX(attempt), 0) + 1 AS next_attempt
                   FROM core_verification_runs WHERE task_id = ?""",
                (run.task_id,),
            ).fetchone()
            next_attempt = int(attempt_row["next_attempt"])
            if int(run.attempt) != next_attempt:
                raise StoreConflict(
                    f"verification attempt changed: expected {next_attempt}, "
                    f"found {run.attempt}"
                )

            claimed_task = conn.execute(
                """UPDATE core_tasks
                   SET updated_at = ?, version = version + 1
                   WHERE task_id = ? AND status = ? AND version = ?""",
                (
                    run.started_at,
                    run.task_id,
                    expected_task_status.value,
                    int(expected_task_version),
                ),
            )
            if claimed_task.rowcount != 1:
                raise StoreConflict("verification task claim lost an atomic race")

            try:
                conn.execute(
                    """INSERT INTO core_verification_runs(
                           run_id, task_id, task_version, attempt, profile_id,
                           profile_version, profile_digest, status, authoritative,
                           backend_id, backend_version, backend_capabilities_json,
                           repository_key, repository, worktree, branch, head_before,
                           head_after, clean_before, clean_after, lease_id,
                           lease_fencing_token, requested_at, started_at, completed_at,
                           workspace_after_json, evidence_json, evidence_hash,
                           error_code, version
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                 ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run.run_id,
                        run.task_id,
                        int(run.task_version),
                        int(run.attempt),
                        run.profile_id,
                        int(run.profile_version),
                        run.profile_digest,
                        VerificationStatus.RUNNING.value,
                        0,
                        run.backend_id,
                        run.backend_version,
                        _canonical_json(run.backend_capabilities),
                        run.repository_key,
                        run.repository,
                        run.worktree,
                        run.branch,
                        run.head_before,
                        run.head_after,
                        int(run.clean_before),
                        int(run.clean_after),
                        run.lease_id,
                        run.lease_fencing_token,
                        run.requested_at,
                        run.started_at,
                        None,
                        None,
                        _canonical_json(run.evidence),
                        None,
                        None,
                        0,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreConflict(
                    "verification run claim conflicts with an active or prior claim"
                ) from exc

            self._record_event(
                conn,
                "verification.started",
                actor=actor,
                task_id=run.task_id,
                payload={
                    "run_id": run.run_id,
                    "task_version": int(run.task_version),
                    "attempt": int(run.attempt),
                    "profile_id": run.profile_id,
                    "profile_version": int(run.profile_version),
                    "profile_digest": run.profile_digest,
                    "backend_id": run.backend_id,
                    "backend_version": run.backend_version,
                    "repository_key": run.repository_key,
                    "repository": run.repository,
                    "worktree": run.worktree,
                    "branch": run.branch,
                    "head_before": run.head_before,
                    "clean_before": bool(run.clean_before),
                    "lease_id": run.lease_id,
                    "lease_fencing_token": run.lease_fencing_token,
                    "from_task_version": int(run.task_version),
                    "to_task_version": int(run.task_version) + 1,
                },
                created_at=run.started_at,
            )
            claimed_row = conn.execute(
                "SELECT * FROM core_verification_runs WHERE run_id = ?",
                (run.run_id,),
            ).fetchone()
            conn.commit()
        if claimed_row is None:  # pragma: no cover - transactional invariant
            raise StoreError("verification run could not be reloaded")
        return self._verification_run_from_row(claimed_row)

    def finalize_verification_run(
        self,
        run_id: str,
        *,
        expected_run_version: int,
        status: VerificationStatus,
        authoritative: bool,
        head_after: str | None,
        clean_after: bool,
        workspace_after: Mapping[str, Any],
        completed_at: str,
        evidence: Mapping[str, Any],
        evidence_hash: str,
        error_code: str | None,
        task_terminal_status: TaskStatus,
        blocker: str | None,
        actor: str = "nero-core",
    ) -> tuple[VerificationRun, Task]:
        """Seal a run and transition its task in one atomic transaction."""
        if status is VerificationStatus.RUNNING:
            raise StoreError("verification finalization requires a terminal status")
        if authoritative and status is not VerificationStatus.PASSED:
            raise StoreError("only a passed verification can be authoritative")
        if status is VerificationStatus.PASSED and not authoritative:
            raise StoreError("a passed verification must be authoritative")
        if task_terminal_status is TaskStatus.COMPLETE:
            if status is not VerificationStatus.PASSED or not authoritative:
                raise StoreError(
                    "task completion requires an authoritative passed verification"
                )
            blocker = None
        elif task_terminal_status not in {TaskStatus.BLOCKED, TaskStatus.FAILED}:
            raise StoreError(
                "verification may transition its task only to complete, blocked, or failed"
            )
        terminal_time = str(completed_at).strip()
        if not terminal_time:
            raise StoreError("verification completion time is required")
        evidence_data = dict(evidence)
        workspace_after_data = dict(workspace_after)
        if evidence_data.get("workspace_after") != workspace_after_data:
            raise StoreError("verification final workspace does not match evidence")
        expected_hash = self.calculate_evidence_hash(evidence_data)
        if evidence_hash != expected_hash:
            raise StoreError("verification evidence hash is not canonical")
        if task_terminal_status is not TaskStatus.COMPLETE and not blocker:
            blocker = error_code or f"verification {status.value}"

        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            run_row = conn.execute(
                "SELECT * FROM core_verification_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run_row is None:
                raise StoreError(f"unknown verification run: {run_id}")
            if run_row["status"] != VerificationStatus.RUNNING.value:
                raise StoreConflict("verification run is already terminal")
            if int(run_row["version"]) != int(expected_run_version):
                raise StoreConflict(
                    f"verification run version changed: expected {expected_run_version}, "
                    f"found {run_row['version']}"
                )

            task_row = conn.execute(
                "SELECT * FROM core_tasks WHERE task_id = ?",
                (run_row["task_id"],),
            ).fetchone()
            if task_row is None:  # pragma: no cover - protected by foreign key
                raise StoreError("verification task no longer exists")
            if task_row["status"] != TaskStatus.VERIFYING.value:
                raise StoreConflict(
                    "verification task changed state while the run was active"
                )
            claimed_task_version = int(run_row["task_version"]) + 1
            if int(task_row["version"]) != claimed_task_version:
                raise StoreConflict(
                    "verification task version changed while the run was active"
                )
            task_profile = (
                task_row["verification_profile_id"],
                task_row["verification_profile_version"],
                task_row["verification_profile_digest"],
            )
            run_profile = (
                run_row["profile_id"],
                run_row["profile_version"],
                run_row["profile_digest"],
            )
            if task_profile != run_profile:
                raise StoreConflict(
                    "verification profile binding changed while the run was active"
                )

            updated_run = conn.execute(
                """UPDATE core_verification_runs
                   SET status = ?, authoritative = ?, head_after = ?, clean_after = ?,
                       completed_at = ?, workspace_after_json = ?, evidence_json = ?,
                       evidence_hash = ?, error_code = ?, version = version + 1
                   WHERE run_id = ? AND status = ? AND version = ?""",
                (
                    status.value,
                    int(authoritative),
                    head_after,
                    int(clean_after),
                    terminal_time,
                    _canonical_json(workspace_after_data),
                    _canonical_json(evidence_data),
                    expected_hash,
                    error_code,
                    run_id,
                    VerificationStatus.RUNNING.value,
                    int(expected_run_version),
                ),
            )
            if updated_run.rowcount != 1:  # pragma: no cover - locked invariant
                raise StoreConflict("verification finalization lost an atomic race")

            trusted_completion = bool(
                authoritative
                and status is VerificationStatus.PASSED
                and task_terminal_status is TaskStatus.COMPLETE
            )
            updated_task = conn.execute(
                """UPDATE core_tasks
                   SET status = ?, blocker = ?, verified_run_id = ?, updated_at = ?,
                       version = version + 1
                   WHERE task_id = ? AND status = ? AND version = ?""",
                (
                    task_terminal_status.value,
                    blocker,
                    run_id if trusted_completion else None,
                    terminal_time,
                    run_row["task_id"],
                    TaskStatus.VERIFYING.value,
                    claimed_task_version,
                ),
            )
            if updated_task.rowcount != 1:  # pragma: no cover - locked invariant
                raise StoreConflict("verification task transition lost an atomic race")

            terminal_row = conn.execute(
                "SELECT * FROM core_verification_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if terminal_row is None:  # pragma: no cover
                raise StoreError("terminal verification run could not be reloaded")
            evidence_problem = self._verification_evidence_problem(
                terminal_row, evidence_data
            )
            if evidence_problem:
                raise StoreError(evidence_problem)
            receipt = self._verification_receipt_from_row(terminal_row)
            self._record_event(
                conn,
                "verification.recorded",
                actor=actor,
                task_id=str(run_row["task_id"]),
                payload={
                    "run_id": run_id,
                    "status": status.value,
                    "authoritative": bool(authoritative),
                    "evidence_hash": expected_hash,
                    "receipt": receipt,
                    "task_terminal_status": task_terminal_status.value,
                    "from_task_version": claimed_task_version,
                    "to_task_version": claimed_task_version + 1,
                },
                created_at=terminal_time,
            )
            self._record_event(
                conn,
                "task.transitioned",
                actor=actor,
                task_id=str(run_row["task_id"]),
                payload={
                    "from": TaskStatus.VERIFYING.value,
                    "to": task_terminal_status.value,
                    "blocker": blocker,
                    "result": None,
                    "verified_run_id": run_id if trusted_completion else None,
                    "verification_run_id": run_id,
                    "from_version": claimed_task_version,
                    "to_version": claimed_task_version + 1,
                },
                created_at=terminal_time,
            )
            final_task_row = conn.execute(
                "SELECT * FROM core_tasks WHERE task_id = ?",
                (run_row["task_id"],),
            ).fetchone()
            conn.commit()
        if final_task_row is None:  # pragma: no cover
            raise StoreError("verification task could not be reloaded")
        return (
            self._verification_run_from_row(terminal_row),
            self._task_from_row(final_task_row),
        )

    def get_verification_run(self, run_id: str) -> VerificationRun | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM core_verification_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._verification_run_from_row(row) if row else None

    def list_verification_runs(
        self,
        *,
        task_id: str | None = None,
        status: VerificationStatus | None = None,
        limit: int = 100,
    ) -> list[VerificationRun]:
        clauses: list[str] = []
        args: list[Any] = []
        if task_id:
            clauses.append("task_id = ?")
            args.append(task_id)
        if status is not None:
            clauses.append("status = ?")
            args.append(status.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.append(max(1, min(int(limit), 1000)))
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT * FROM core_verification_runs {where}
                    ORDER BY requested_at DESC, run_id DESC LIMIT ?""",
                args,
            ).fetchall()
        return [self._verification_run_from_row(row) for row in rows]

    def next_verification_attempt(self, task_id: str) -> int:
        """Return the next display attempt; the claim transaction rechecks it."""

        with self._connect() as conn:
            row = conn.execute(
                """SELECT COALESCE(MAX(attempt), 0) + 1 AS next_attempt
                   FROM core_verification_runs WHERE task_id = ?""",
                (task_id,),
            ).fetchone()
        return int(row["next_attempt"] if row else 1)

    def request_approval(
        self,
        *,
        action: str,
        summary: str,
        risk: RiskLevel,
        requested_by: str,
    ) -> Approval:
        approval_id = str(uuid.uuid4())
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            conn.execute(
                """INSERT INTO core_approvals(
                       approval_id, action, summary, risk, status, requested_by,
                       requested_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    approval_id,
                    action,
                    summary,
                    risk.value,
                    ApprovalStatus.PENDING.value,
                    requested_by,
                    now,
                ),
            )
            self._record_event(
                conn,
                "approval.requested",
                actor=requested_by,
                payload={
                    "approval_id": approval_id,
                    "action": action,
                    "summary": summary,
                    "risk": risk.value,
                },
                created_at=now,
            )
            conn.commit()
        approval = self.get_approval(approval_id)
        if approval is None:  # pragma: no cover
            raise StoreError("created approval could not be reloaded")
        return approval

    def decide_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        decided_by: str,
        note: str = "",
    ) -> Approval:
        now = _iso(self.clock())
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            row = conn.execute(
                "SELECT status FROM core_approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
            if row is None:
                raise StoreError(f"unknown approval: {approval_id}")
            if row["status"] != ApprovalStatus.PENDING.value:
                raise StoreError("approval is no longer pending")
            conn.execute(
                """UPDATE core_approvals SET status = ?, decided_at = ?,
                   decided_by = ?, decision_note = ? WHERE approval_id = ?""",
                (status.value, now, decided_by, note, approval_id),
            )
            self._record_event(
                conn,
                "approval.decided",
                actor=decided_by,
                payload={
                    "approval_id": approval_id,
                    "status": status.value,
                    "note": note,
                    "remote_operation_executed": False,
                },
                created_at=now,
            )
            conn.commit()
        approval = self.get_approval(approval_id)
        if approval is None:  # pragma: no cover
            raise StoreError("decided approval could not be reloaded")
        return approval

    def get_approval(self, approval_id: str) -> Approval | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM core_approvals WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()
        return self._approval_from_row(row) if row else None

    def list_approvals(self, *, status: ApprovalStatus | None = None) -> list[Approval]:
        with self._connect() as conn:
            if status is None:
                rows = conn.execute(
                    "SELECT * FROM core_approvals ORDER BY requested_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM core_approvals WHERE status = ?
                       ORDER BY requested_at DESC""",
                    (status.value,),
                ).fetchall()
        return [self._approval_from_row(row) for row in rows]

    def get_meta(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM core_meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_meta(
        self,
        key: str,
        value: str,
        *,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        normalized_key = str(key).strip()
        if not normalized_key:
            raise StoreError("metadata key is required")
        if normalized_key == "schema_version":
            raise StoreError("schema_version is reserved for transactional migration")
        normalized_value = str(value)
        event_payload = {
            **dict(payload),
            "meta_key": normalized_key,
            "meta_deleted": False,
            "value_sha256": hashlib.sha256(
                normalized_value.encode("utf-8")
            ).hexdigest(),
        }
        with self._connect() as conn:
            self._begin(conn)
            self._assert_writable(conn)
            conn.execute(
                """INSERT INTO core_meta(key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (normalized_key, normalized_value),
            )
            self._record_event(
                conn,
                event_type,
                actor=actor,
                payload=event_payload,
            )
            conn.commit()

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> Task:
        result_data = json.loads(row["result_json"]) if row["result_json"] else None
        result = AgentResult(
            summary=result_data["summary"],
            files_changed=tuple(result_data.get("files_changed", [])),
            tests_run=tuple(result_data.get("tests_run", [])),
            risks=tuple(result_data.get("risks", [])),
            unresolved_questions=tuple(result_data.get("unresolved_questions", [])),
            recommended_next_action=result_data.get("recommended_next_action", ""),
            raw_reference=result_data.get("raw_reference"),
            source=result_data.get("source", "legacy_unverified"),
            provider_contacted=bool(result_data.get("provider_contacted", False)),
        ) if result_data else None
        return Task(
            task_id=row["task_id"],
            objective=row["objective"],
            status=TaskStatus(row["status"]),
            priority=int(row["priority"]),
            dependencies=tuple(json.loads(row["dependencies_json"])),
            acceptance_criteria=tuple(json.loads(row["acceptance_json"])),
            write_required=bool(row["write_required"]),
            repository=row["repository"],
            branch=row["branch"],
            worktree=row["worktree"],
            assigned_adapter=row["assigned_adapter"],
            context_version=row["context_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            version=int(row["version"]),
            last_result=result,
            blocker=row["blocker"],
            verification_profile_id=row["verification_profile_id"],
            verification_profile_version=(
                int(row["verification_profile_version"])
                if row["verification_profile_version"] is not None
                else None
            ),
            verification_profile_digest=row["verification_profile_digest"],
            verified_run_id=row["verified_run_id"],
        )

    @staticmethod
    def _verification_run_from_row(row: sqlite3.Row) -> VerificationRun:
        backend_capabilities = json.loads(row["backend_capabilities_json"])
        evidence = json.loads(row["evidence_json"])
        if not isinstance(backend_capabilities, dict):
            raise StoreError("verification backend capabilities are invalid")
        if not isinstance(evidence, dict):
            raise StoreError("verification evidence is invalid")
        return VerificationRun(
            run_id=row["run_id"],
            task_id=row["task_id"],
            task_version=int(row["task_version"]),
            attempt=int(row["attempt"]),
            profile_id=row["profile_id"],
            profile_version=int(row["profile_version"]),
            profile_digest=row["profile_digest"],
            status=VerificationStatus(row["status"]),
            authoritative=bool(row["authoritative"]),
            backend_id=row["backend_id"],
            backend_version=row["backend_version"],
            backend_capabilities=backend_capabilities,
            repository_key=row["repository_key"],
            repository=row["repository"],
            worktree=row["worktree"],
            branch=row["branch"],
            head_before=row["head_before"],
            head_after=row["head_after"],
            clean_before=bool(row["clean_before"]),
            clean_after=bool(row["clean_after"]),
            lease_id=row["lease_id"],
            lease_fencing_token=(
                int(row["lease_fencing_token"])
                if row["lease_fencing_token"] is not None
                else None
            ),
            requested_at=row["requested_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            evidence=evidence,
            evidence_hash=row["evidence_hash"],
            error_code=row["error_code"],
            version=int(row["version"]),
        )

    @staticmethod
    def _verification_receipt_from_row(row: sqlite3.Row) -> dict[str, Any]:
        capabilities = json.loads(row["backend_capabilities_json"])
        if not isinstance(capabilities, dict):
            raise ValueError("backend capabilities must be an object")
        workspace_after = json.loads(row["workspace_after_json"])
        if not isinstance(workspace_after, dict):
            raise ValueError("final workspace must be an object")
        return {
            "run_id": row["run_id"],
            "task_id": row["task_id"],
            "task_version": int(row["task_version"]),
            "attempt": int(row["attempt"]),
            "profile_id": row["profile_id"],
            "profile_version": int(row["profile_version"]),
            "profile_digest": row["profile_digest"],
            "status": row["status"],
            "authoritative": bool(row["authoritative"]),
            "backend_id": row["backend_id"],
            "backend_version": row["backend_version"],
            "backend_capabilities": capabilities,
            "repository_key": row["repository_key"],
            "repository": row["repository"],
            "worktree": row["worktree"],
            "branch": row["branch"],
            "head_before": row["head_before"],
            "head_after": row["head_after"],
            "clean_before": bool(row["clean_before"]),
            "clean_after": bool(row["clean_after"]),
            "workspace_after": workspace_after,
            "lease_id": row["lease_id"],
            "lease_fencing_token": (
                int(row["lease_fencing_token"])
                if row["lease_fencing_token"] is not None
                else None
            ),
            "requested_at": row["requested_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "evidence_hash": row["evidence_hash"],
            "error_code": row["error_code"],
            "version": int(row["version"]),
        }

    @staticmethod
    def _approval_from_row(row: sqlite3.Row) -> Approval:
        return Approval(
            approval_id=row["approval_id"],
            action=row["action"],
            summary=row["summary"],
            risk=RiskLevel(row["risk"]),
            status=ApprovalStatus(row["status"]),
            requested_by=row["requested_by"],
            requested_at=row["requested_at"],
            decided_at=row["decided_at"],
            decided_by=row["decided_by"],
            decision_note=row["decision_note"],
        )

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> Event:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {"_integrity_error": "payload is unreadable"}
        return Event(
            sequence=int(row["sequence"]),
            event_id=row["event_id"],
            event_type=row["event_type"],
            actor=row["actor"],
            task_id=row["task_id"],
            payload=payload,
            created_at=row["created_at"],
            previous_hash=row["previous_hash"],
            event_hash=row["event_hash"],
        )
