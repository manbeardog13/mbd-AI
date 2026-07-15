"""Durable Core state, append-only events, approvals, and write leases."""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    AgentResult,
    Approval,
    ApprovalStatus,
    Event,
    Lease,
    RiskLevel,
    Task,
    TaskStatus,
)


Clock = Callable[[], datetime]


SCHEMA = """
CREATE TABLE IF NOT EXISTS core_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

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
    result_json TEXT,
    blocker TEXT
);
CREATE INDEX IF NOT EXISTS idx_core_tasks_queue
    ON core_tasks(status, priority DESC, created_at ASC);

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
);

CREATE TABLE IF NOT EXISTS core_write_leases (
    repository_key TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    task_id TEXT,
    token_hash TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

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
);
CREATE INDEX IF NOT EXISTS idx_core_events_type_time
    ON core_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_core_events_task_time
    ON core_events(task_id, created_at DESC);

CREATE TRIGGER IF NOT EXISTS core_events_no_update
BEFORE UPDATE ON core_events BEGIN
    SELECT RAISE(ABORT, 'core events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS core_events_no_delete
BEFORE DELETE ON core_events BEGIN
    SELECT RAISE(ABORT, 'core events are append-only');
END;
"""


@dataclass(frozen=True, slots=True)
class LeaseGrant:
    lease: Lease
    token: str


class StoreError(RuntimeError):
    """Raised when durable Core state cannot satisfy a requested operation."""


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


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CoreStore:
    """SQLite-backed Core state with one transaction per public mutation."""

    def __init__(self, db_path: str | Path, *, clock: Clock = _utc_now) -> None:
        self.db_path = Path(db_path).resolve()
        self.clock = clock

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

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

    def verify_event_chain(self) -> tuple[bool, str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM core_events ORDER BY sequence ASC").fetchall()
        previous_hash = "GENESIS"
        for row in rows:
            payload = json.loads(row["payload_json"])
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
        return True, f"event chain valid ({len(rows)} events)"

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
        context_version: str = "m1",
        actor: str = "operator",
    ) -> Task:
        objective = objective.strip()
        if not objective:
            raise StoreError("task objective is required")
        task_id = str(uuid.uuid4())
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            conn.execute(
                """
                INSERT INTO core_tasks(
                    task_id, objective, status, priority, dependencies_json,
                    acceptance_json, write_required, repository, branch,
                    worktree, assigned_adapter, context_version, created_at,
                    updated_at, result_json, blocker
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, NULL, NULL)
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

    def assign_task(
        self,
        task_id: str,
        *,
        adapter_id: str,
        branch: str | None,
        worktree: str | None,
        actor: str = "nero-core",
    ) -> Task:
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            row = conn.execute(
                "SELECT status FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise StoreError(f"unknown task: {task_id}")
            conn.execute(
                """UPDATE core_tasks
                   SET status = ?, assigned_adapter = ?, branch = ?, worktree = ?,
                       blocker = NULL, updated_at = ?
                   WHERE task_id = ?""",
                (
                    TaskStatus.PREPARING.value,
                    adapter_id,
                    branch,
                    worktree,
                    now,
                    task_id,
                ),
            )
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
                },
                created_at=now,
            )
            conn.commit()
        task = self.get_task(task_id)
        if task is None:  # pragma: no cover
            raise StoreError("assigned task could not be reloaded")
        return task

    def transition_task(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        blocker: str | None = None,
        result: AgentResult | None = None,
        actor: str = "nero-core",
    ) -> Task:
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            row = conn.execute(
                "SELECT status FROM core_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise StoreError(f"unknown task: {task_id}")
            result_json = _canonical_json(result.as_dict()) if result else None
            conn.execute(
                """UPDATE core_tasks
                   SET status = ?, blocker = ?, result_json = COALESCE(?, result_json),
                       updated_at = ? WHERE task_id = ?""",
                (status.value, blocker, result_json, now, task_id),
            )
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
                },
                created_at=now,
            )
            conn.commit()
        task = self.get_task(task_id)
        if task is None:  # pragma: no cover
            raise StoreError("transitioned task could not be reloaded")
        return task

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

    def acquire_lease(
        self,
        repository_key: str,
        *,
        owner: str,
        task_id: str | None,
        ttl_seconds: int = 120,
        actor: str = "nero-core",
    ) -> LeaseGrant | None:
        ttl = max(5, min(int(ttl_seconds), 3600))
        now_dt = _as_utc(self.clock())
        now = _iso(now_dt)
        expires = _iso(now_dt + timedelta(seconds=ttl))
        token = secrets.token_urlsafe(32)
        with self._connect() as conn:
            self._begin(conn)
            self._expire_lease_if_needed(conn, repository_key, now_dt, actor=actor)
            row = conn.execute(
                "SELECT * FROM core_write_leases WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            if row is not None:
                self._record_event(
                    conn,
                    "lease.denied",
                    actor=actor,
                    task_id=task_id,
                    payload={
                        "repository_key": repository_key,
                        "requested_owner": owner,
                        "active_owner": row["owner"],
                        "expires_at": row["expires_at"],
                    },
                    created_at=now,
                )
                conn.commit()
                return None
            conn.execute(
                """INSERT INTO core_write_leases(
                       repository_key, owner, task_id, token_hash, acquired_at,
                       heartbeat_at, expires_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    repository_key,
                    owner,
                    task_id,
                    _token_hash(token),
                    now,
                    now,
                    expires,
                ),
            )
            self._record_event(
                conn,
                "lease.acquired",
                actor=actor,
                task_id=task_id,
                payload={
                    "repository_key": repository_key,
                    "owner": owner,
                    "expires_at": expires,
                },
                created_at=now,
            )
            conn.commit()
        return LeaseGrant(
            lease=Lease(repository_key, owner, task_id, now, now, expires),
            token=token,
        )

    def current_lease(self, repository_key: str) -> Lease | None:
        now_dt = _as_utc(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            self._expire_lease_if_needed(conn, repository_key, now_dt, actor="nero-core")
            row = conn.execute(
                "SELECT * FROM core_write_leases WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            conn.commit()
        return self._lease_from_row(row) if row else None

    def heartbeat_lease(
        self,
        repository_key: str,
        token: str,
        *,
        ttl_seconds: int = 120,
        actor: str = "nero-core",
    ) -> Lease:
        ttl = max(5, min(int(ttl_seconds), 3600))
        now_dt = _as_utc(self.clock())
        now = _iso(now_dt)
        expires = _iso(now_dt + timedelta(seconds=ttl))
        with self._connect() as conn:
            self._begin(conn)
            self._expire_lease_if_needed(conn, repository_key, now_dt, actor=actor)
            row = conn.execute(
                "SELECT * FROM core_write_leases WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            if row is None or not secrets.compare_digest(row["token_hash"], _token_hash(token)):
                raise StoreError("lease token is invalid or expired")
            conn.execute(
                """UPDATE core_write_leases SET heartbeat_at = ?, expires_at = ?
                   WHERE repository_key = ?""",
                (now, expires, repository_key),
            )
            self._record_event(
                conn,
                "lease.heartbeat",
                actor=actor,
                task_id=row["task_id"],
                payload={"repository_key": repository_key, "expires_at": expires},
                created_at=now,
            )
            conn.commit()
        lease = self.current_lease(repository_key)
        if lease is None:  # pragma: no cover
            raise StoreError("lease disappeared after heartbeat")
        return lease

    def release_lease(
        self,
        repository_key: str,
        token: str,
        *,
        actor: str = "nero-core",
    ) -> bool:
        now = _iso(self.clock())
        with self._connect() as conn:
            self._begin(conn)
            row = conn.execute(
                "SELECT * FROM core_write_leases WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            if row is None or not secrets.compare_digest(row["token_hash"], _token_hash(token)):
                self._record_event(
                    conn,
                    "lease.release_denied",
                    actor=actor,
                    payload={"repository_key": repository_key},
                    created_at=now,
                )
                conn.commit()
                return False
            conn.execute(
                "DELETE FROM core_write_leases WHERE repository_key = ?",
                (repository_key,),
            )
            self._record_event(
                conn,
                "lease.released",
                actor=actor,
                task_id=row["task_id"],
                payload={"repository_key": repository_key, "owner": row["owner"]},
                created_at=now,
            )
            conn.commit()
            return True

    def get_meta(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM core_meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO core_meta(key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, value),
            )

    def _expire_lease_if_needed(
        self,
        conn: sqlite3.Connection,
        repository_key: str,
        now: datetime,
        *,
        actor: str,
    ) -> None:
        row = conn.execute(
            "SELECT * FROM core_write_leases WHERE repository_key = ?",
            (repository_key,),
        ).fetchone()
        if row is None or _parse_time(row["expires_at"]) > now:
            return
        conn.execute(
            "DELETE FROM core_write_leases WHERE repository_key = ?",
            (repository_key,),
        )
        self._record_event(
            conn,
            "lease.expired",
            actor=actor,
            task_id=row["task_id"],
            payload={"repository_key": repository_key, "owner": row["owner"]},
            created_at=_iso(now),
        )

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
            last_result=result,
            blocker=row["blocker"],
        )

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
        return Event(
            sequence=int(row["sequence"]),
            event_id=row["event_id"],
            event_type=row["event_type"],
            actor=row["actor"],
            task_id=row["task_id"],
            payload=json.loads(row["payload_json"]),
            created_at=row["created_at"],
            previous_hash=row["previous_hash"],
            event_hash=row["event_hash"],
        )

    @staticmethod
    def _lease_from_row(row: sqlite3.Row) -> Lease:
        return Lease(
            repository_key=row["repository_key"],
            owner=row["owner"],
            task_id=row["task_id"],
            acquired_at=row["acquired_at"],
            heartbeat_at=row["heartbeat_at"],
            expires_at=row["expires_at"],
        )
