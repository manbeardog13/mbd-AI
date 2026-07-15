"""Typed contracts shared by Nero Core and replaceable worker adapters.

The contracts deliberately contain no model SDK types. Core state must remain
serializable, deterministic, and readable when no worker provider is available.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    WAITING = "waiting"
    VERIFYING = "verifying"
    BLOCKED = "blocked"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class WorkerStatus(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    WAITING = "waiting"
    VERIFYING = "verifying"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETE = "complete"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class RiskLevel(StrEnum):
    SAFE = "safe"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _jsonable(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class AgentResult:
    summary: str
    files_changed: tuple[str, ...] = ()
    tests_run: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    recommended_next_action: str = ""
    raw_reference: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    objective: str
    status: TaskStatus
    priority: int
    dependencies: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    write_required: bool
    repository: str
    branch: str | None
    worktree: str | None
    assigned_adapter: str | None
    context_version: str
    created_at: str
    updated_at: str
    version: int = 0
    last_result: AgentResult | None = None
    blocker: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class TaskPacket:
    packet_version: str
    context_version: str
    task_id: str
    provider: str
    objective: str
    acceptance_criteria: tuple[str, ...]
    repository: str
    branch: str | None
    worktree: str | None
    write_allowed: bool
    lease_owner: str | None
    lease_id: str | None
    lease_fencing_token: int | None
    lease_expires_at: str | None
    requires_action_time_lease_validation: bool
    bounded_context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class GitState:
    repository: str
    common_directory: str
    worktree: str
    branch: str | None
    detached_head: bool
    upstream: str | None
    remote_name: str | None
    remote_url: str | None
    remote_available: bool | None
    authentication: str
    push_permission: str
    last_fetch_at: str | None
    last_fetch_attempt_at: str | None
    fetch_receipt: dict[str, Any] | None
    remote_state_fresh: bool
    ahead: int | None
    behind: int | None
    relationship: str
    clean: bool
    modified_count: int
    untracked_count: int
    staged_count: int
    conflict_count: int
    conflict_files: tuple[str, ...]
    last_commit: str | None
    local_only_branches: tuple[str, ...]
    remote_only_branches: tuple[str, ...]
    worktrees: tuple[dict[str, str | None], ...]
    active_write_lease: dict[str, Any] | None
    pending_commit: bool
    pending_push: bool | None
    errors: tuple[str, ...] = ()

    @property
    def diverged(self) -> bool:
        return bool(self.ahead and self.behind)

    def as_dict(self) -> dict[str, Any]:
        data = _jsonable(asdict(self))
        data["diverged"] = self.diverged
        return data


@dataclass(frozen=True, slots=True)
class Approval:
    approval_id: str
    action: str
    summary: str
    risk: RiskLevel
    status: ApprovalStatus
    requested_by: str
    requested_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    decision_note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class Event:
    sequence: int
    event_id: str
    event_type: str
    actor: str
    task_id: str | None
    payload: dict[str, Any]
    created_at: str
    previous_hash: str
    event_hash: str

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    scope: str
    content: str
    source: str
    provenance: dict[str, Any]
    created_at: str
    expires_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class Lease:
    repository_key: str
    lease_id: str
    fencing_token: int
    owner: str
    task_id: str | None
    acquired_at: str
    heartbeat_at: str
    expires_at: str

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True, slots=True)
class WorkerDescriptor:
    adapter_id: str
    provider: str
    display_name: str
    status: WorkerStatus
    remote_writes: bool
    local_repository_access: bool
    assigned_task: str | None = None
    last_result: AgentResult | None = None

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))
