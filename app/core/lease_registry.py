"""Repository-global write coordination anchored in Git's common directory.

The registry is intentionally separate from the operator-selected Core state
database. Every worktree and every Mission Control instance for one repository
therefore contends on the same SQLite row inside the canonical Git common
directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterator

from .contracts import Lease


Clock = Callable[[], datetime]


REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS lease_generation (
    fencing_token INTEGER PRIMARY KEY AUTOINCREMENT
);

CREATE TABLE IF NOT EXISTS repository_write_lease (
    repository_key TEXT PRIMARY KEY,
    lease_id TEXT NOT NULL UNIQUE,
    fencing_token INTEGER NOT NULL UNIQUE,
    owner TEXT NOT NULL,
    task_id TEXT,
    token_hash TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lease_history (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    repository_key TEXT NOT NULL,
    lease_id TEXT,
    fencing_token INTEGER,
    owner TEXT,
    task_id TEXT,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS lease_history_no_update
BEFORE UPDATE ON lease_history BEGIN
    SELECT RAISE(ABORT, 'lease history is append-only');
END;
CREATE TRIGGER IF NOT EXISTS lease_history_no_delete
BEFORE DELETE ON lease_history BEGIN
    SELECT RAISE(ABORT, 'lease history is append-only');
END;
"""


class LeaseRegistryError(RuntimeError):
    """Raised when a canonical lease cannot be renewed or validated."""


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


@dataclass(frozen=True, slots=True)
class LeaseGrant:
    lease: Lease
    token: str


@dataclass(frozen=True, slots=True)
class LeaseObservation:
    active: Lease | None
    expired: Lease | None = None


@dataclass(frozen=True, slots=True)
class LeaseAcquisition:
    grant: LeaseGrant | None
    active: Lease | None
    expired: Lease | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _as_utc(value).isoformat(timespec="milliseconds")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RepositoryLeaseRegistry:
    """One cross-process managed writer for a canonical Git repository."""

    def __init__(self, *, clock: Clock = _utc_now) -> None:
        self.clock = clock

    @staticmethod
    def canonical_key(common_directory: str | Path) -> str:
        return os.path.normcase(str(Path(common_directory).resolve()))

    @classmethod
    def database_path(cls, common_directory: str | Path) -> Path:
        return Path(cls.canonical_key(common_directory)) / "nero-core" / "write-lease.db"

    def acquire(
        self,
        common_directory: str | Path,
        *,
        owner: str,
        task_id: str | None,
        ttl_seconds: int = 120,
    ) -> LeaseAcquisition:
        repository_key = self.canonical_key(common_directory)
        ttl = max(5, min(int(ttl_seconds), 3600))
        now_dt = _as_utc(self.clock())
        now = _iso(now_dt)
        expires = _iso(now_dt + timedelta(seconds=ttl))
        token = secrets.token_urlsafe(32)
        with self._connect(repository_key) as conn:
            conn.execute("BEGIN IMMEDIATE")
            expired = self._take_expired(conn, repository_key, now_dt)
            row = conn.execute(
                "SELECT * FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            if row is not None:
                active = self._from_row(row)
                self._history(
                    conn,
                    "lease.denied",
                    active,
                    now,
                    {"requested_owner": owner, "requested_task_id": task_id},
                )
                conn.commit()
                return LeaseAcquisition(
                    grant=None,
                    active=active,
                    expired=expired,
                )
            fence = int(
                conn.execute("INSERT INTO lease_generation DEFAULT VALUES").lastrowid
            )
            lease_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO repository_write_lease(
                       repository_key, lease_id, fencing_token, owner, task_id,
                       token_hash, acquired_at, heartbeat_at, expires_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    repository_key,
                    lease_id,
                    fence,
                    owner,
                    task_id,
                    _token_hash(token),
                    now,
                    now,
                    expires,
                ),
            )
            lease = Lease(
                repository_key,
                lease_id,
                fence,
                owner,
                task_id,
                now,
                now,
                expires,
            )
            self._history(conn, "lease.acquired", lease, now, {})
            conn.commit()
        return LeaseAcquisition(
            grant=LeaseGrant(lease=lease, token=token),
            active=lease,
            expired=expired,
        )

    def observe(self, common_directory: str | Path) -> LeaseObservation:
        repository_key = self.canonical_key(common_directory)
        now = _as_utc(self.clock())
        with self._connect(repository_key) as conn:
            conn.execute("BEGIN IMMEDIATE")
            expired = self._take_expired(conn, repository_key, now)
            row = conn.execute(
                "SELECT * FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            conn.commit()
        return LeaseObservation(
            active=self._from_row(row) if row else None,
            expired=expired,
        )

    def peek(self, common_directory: str | Path) -> LeaseObservation:
        """Read lease state without expiring rows or appending history.

        Safe-mode views use this path so a damaged Core audit chain cannot
        cause even automatic lease-cleanup mutations in the coordination DB.
        """
        repository_key = self.canonical_key(common_directory)
        path = self.database_path(repository_key)
        if not path.exists():
            return LeaseObservation(active=None)
        uri = path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(
            uri,
            uri=True,
            timeout=5.0,
            factory=_ClosingConnection,
        ) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
        if row is None:
            return LeaseObservation(active=None)
        lease = self._from_row(row)
        if _parse(lease.expires_at) <= _as_utc(self.clock()):
            return LeaseObservation(active=None, expired=lease)
        return LeaseObservation(active=lease)

    def heartbeat(
        self,
        common_directory: str | Path,
        lease_id: str,
        fencing_token: int,
        token: str,
        *,
        ttl_seconds: int = 120,
    ) -> Lease:
        repository_key = self.canonical_key(common_directory)
        ttl = max(5, min(int(ttl_seconds), 3600))
        now_dt = _as_utc(self.clock())
        now = _iso(now_dt)
        expires = _iso(now_dt + timedelta(seconds=ttl))
        with self._connect(repository_key) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._take_expired(conn, repository_key, now_dt)
            row = conn.execute(
                "SELECT * FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            if not self._matches(row, lease_id, fencing_token, token):
                conn.rollback()
                raise LeaseRegistryError("lease token is invalid or expired")
            conn.execute(
                """UPDATE repository_write_lease
                   SET heartbeat_at = ?, expires_at = ?
                   WHERE repository_key = ? AND lease_id = ?
                         AND fencing_token = ?""",
                (now, expires, repository_key, lease_id, int(fencing_token)),
            )
            lease = Lease(
                repository_key=repository_key,
                lease_id=lease_id,
                fencing_token=int(fencing_token),
                owner=row["owner"],
                task_id=row["task_id"],
                acquired_at=row["acquired_at"],
                heartbeat_at=now,
                expires_at=expires,
            )
            self._history(conn, "lease.heartbeat", lease, now, {})
            conn.commit()
        return lease

    def validate(
        self,
        common_directory: str | Path,
        lease_id: str,
        fencing_token: int,
        token: str,
    ) -> Lease:
        repository_key = self.canonical_key(common_directory)
        now = _as_utc(self.clock())
        with self._connect(repository_key) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._take_expired(conn, repository_key, now)
            row = conn.execute(
                "SELECT * FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            if not self._matches(row, lease_id, fencing_token, token):
                conn.rollback()
                raise LeaseRegistryError("lease token is invalid or expired")
            lease = self._from_row(row)
            conn.commit()
        return lease

    @contextmanager
    def completion_fence(
        self,
        common_directory: str | Path,
        lease_id: str,
        fencing_token: int,
        token: str,
    ) -> Iterator[Lease]:
        """Hold the canonical lease lock across an authoritative Core commit.

        Validation alone is subject to a validate-then-use race. This guard
        keeps a write transaction open in the canonical lease database while
        the caller commits completion in Core state, so an expired lease cannot
        be replaced by a higher fencing generation during that commit.
        """

        repository_key = self.canonical_key(common_directory)
        conn = self._connect(repository_key)
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = _as_utc(self.clock())
            self._take_expired(conn, repository_key, now)
            row = conn.execute(
                "SELECT * FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            if not self._matches(row, lease_id, fencing_token, token):
                conn.rollback()
                raise LeaseRegistryError("lease token is invalid or expired")
            lease = self._from_row(row)
            yield lease
            # BEGIN IMMEDIATE prevents another registry writer from replacing
            # the row between the validation above and the Core commit.
            current = conn.execute(
                "SELECT * FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            if not self._matches(current, lease_id, fencing_token, token):
                raise LeaseRegistryError("lease fence changed during completion")
            self._history(
                conn,
                "lease.completion_fenced",
                lease,
                _iso(self.clock()),
                {},
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def release(
        self,
        common_directory: str | Path,
        lease_id: str,
        fencing_token: int,
        token: str,
    ) -> tuple[bool, Lease | None]:
        repository_key = self.canonical_key(common_directory)
        with self._connect(repository_key) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            ).fetchone()
            lease = self._from_row(row) if row else None
            if not self._matches(row, lease_id, fencing_token, token):
                if lease:
                    self._history(
                        conn,
                        "lease.release_denied",
                        lease,
                        _iso(self.clock()),
                        {"requested_lease_id": lease_id},
                    )
                conn.commit()
                return False, lease
            conn.execute(
                "DELETE FROM repository_write_lease WHERE repository_key = ?",
                (repository_key,),
            )
            self._history(conn, "lease.released", lease, _iso(self.clock()), {})
            conn.commit()
        return True, lease

    def _connect(self, repository_key: str) -> sqlite3.Connection:
        path = self.database_path(repository_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=5.0, factory=_ClosingConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA synchronous = FULL")
        conn.executescript(REGISTRY_SCHEMA)
        return conn

    def _take_expired(
        self, conn: sqlite3.Connection, repository_key: str, now: datetime
    ) -> Lease | None:
        row = conn.execute(
            "SELECT * FROM repository_write_lease WHERE repository_key = ?",
            (repository_key,),
        ).fetchone()
        if row is None or _parse(row["expires_at"]) > now:
            return None
        lease = RepositoryLeaseRegistry._from_row(row)
        conn.execute(
            "DELETE FROM repository_write_lease WHERE repository_key = ?",
            (repository_key,),
        )
        self._history(conn, "lease.expired", lease, _iso(now), {})
        return lease

    @staticmethod
    def _matches(
        row: sqlite3.Row | None,
        lease_id: str,
        fencing_token: int,
        token: str,
    ) -> bool:
        return bool(
            row is not None
            and row["lease_id"] == lease_id
            and int(row["fencing_token"]) == int(fencing_token)
            and secrets.compare_digest(row["token_hash"], _token_hash(token))
        )

    @staticmethod
    def _history(
        conn: sqlite3.Connection,
        event_type: str,
        lease: Lease,
        occurred_at: str,
        payload: dict,
    ) -> None:
        conn.execute(
            """INSERT INTO lease_history(
                   event_type, repository_key, lease_id, fencing_token, owner,
                   task_id, occurred_at, payload_json
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_type,
                lease.repository_key,
                lease.lease_id,
                lease.fencing_token,
                lease.owner,
                lease.task_id,
                occurred_at,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            ),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Lease:
        return Lease(
            repository_key=row["repository_key"],
            lease_id=row["lease_id"],
            fencing_token=int(row["fencing_token"]),
            owner=row["owner"],
            task_id=row["task_id"],
            acquired_at=row["acquired_at"],
            heartbeat_at=row["heartbeat_at"],
            expires_at=row["expires_at"],
        )
