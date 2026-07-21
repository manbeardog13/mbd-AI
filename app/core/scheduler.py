"""Deterministic scheduler with CAS tasks and a repository-global write lease."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .adapters import (
    AdapterError,
    ManualWorkerAdapter,
    validate_bounded_context,
)
from .contracts import AgentResult, GitState, Lease, Task, TaskPacket, TaskStatus
from .git_service import FetchReceipt, GitInspectionError, GitService
from .lease_registry import (
    LeaseGrant,
    LeaseRegistryError,
    RepositoryLeaseRegistry,
)
from .store import (
    CoreStore,
    SafeModeError,
    StoreConflict,
    StoreError,
)


class ScheduleError(RuntimeError):
    """Raised when an assignment or state transition fails closed."""


@dataclass(frozen=True, slots=True)
class Assignment:
    task: Task
    packet: TaskPacket
    git_state: GitState
    lease: Lease | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.as_dict(),
            "packet": self.packet.as_dict(),
            "git_state": self.git_state.as_dict(),
            "lease": self.lease.as_dict() if self.lease else None,
        }


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.QUEUED: {
        TaskStatus.PREPARING,
        TaskStatus.BLOCKED,
        TaskStatus.PAUSED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PREPARING: {
        TaskStatus.RUNNING,
        TaskStatus.WAITING,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.PAUSED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.WAITING,
        TaskStatus.VERIFYING,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.PAUSED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING: {
        TaskStatus.RUNNING,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
        TaskStatus.PAUSED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETE,
        TaskStatus.FAILED,
        TaskStatus.BLOCKED,
    },
    TaskStatus.BLOCKED: {TaskStatus.QUEUED, TaskStatus.PAUSED, TaskStatus.CANCELLED},
    TaskStatus.PAUSED: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETE: set(),
    TaskStatus.CANCELLED: set(),
}

ACTIVE_WRITE_STATUSES = {
    TaskStatus.PREPARING,
    TaskStatus.RUNNING,
    TaskStatus.WAITING,
    TaskStatus.VERIFYING,
}
RELEASE_STATUSES = {
    TaskStatus.BLOCKED,
    TaskStatus.PAUSED,
    TaskStatus.FAILED,
    TaskStatus.COMPLETE,
    TaskStatus.CANCELLED,
}
RESERVED_CONTEXT_KEYS = {
    "gitrelationship",
    "remotestatefresh",
    "clean",
    "remotewritesallowed",
    "writeallowed",
    "leaseowner",
    "leaseid",
    "leasefencingtoken",
    "leaseexpiresat",
}


class Scheduler:
    def __init__(
        self,
        store: CoreStore,
        git: GitService,
        adapters: Mapping[str, ManualWorkerAdapter],
        *,
        lease_registry: RepositoryLeaseRegistry | None = None,
        lease_ttl_seconds: int = 120,
    ) -> None:
        self.store = store
        self.git = git
        self.adapters = dict(adapters)
        self.lease_registry = lease_registry or RepositoryLeaseRegistry()
        self.lease_ttl_seconds = lease_ttl_seconds
        self._task_credentials: dict[str, LeaseGrant] = {}

    def assign(
        self,
        task_id: str,
        adapter_id: str,
        *,
        expected_version: int,
        bounded_context: Mapping[str, Any] | None = None,
    ) -> Assignment:
        user_context = dict(bounded_context or {})
        self._event(
            "worker.assignment.requested",
            task_id=task_id,
            payload={"adapter": adapter_id, "expected_version": expected_version},
        )
        credential: LeaseGrant | None = None
        claimed: Task | None = None
        state: GitState | None = None
        try:
            self._validate_context(user_context)
            task = self.store.get_task(task_id)
            if task is None:
                raise ScheduleError(f"unknown task: {task_id}")
            if task.status is not TaskStatus.QUEUED:
                raise ScheduleError(
                    f"task {task_id} is {task.status.value}, not queued"
                )
            if task.version != int(expected_version):
                raise ScheduleError(
                    f"task version changed: expected {expected_version}, "
                    f"found {task.version}"
                )
            adapter = self.adapters.get(adapter_id)
            if adapter is None:
                raise ScheduleError(f"unknown adapter: {adapter_id}")

            incomplete = [
                dependency
                for dependency in task.dependencies
                if (dep := self.store.get_task(dependency)) is None
                or dep.status is not TaskStatus.COMPLETE
            ]
            if incomplete:
                blocker = "incomplete dependencies: " + ", ".join(incomplete)
                self.store.transition_task(
                    task_id,
                    TaskStatus.BLOCKED,
                    expected_status=task.status,
                    expected_version=task.version,
                    blocker=blocker,
                    actor="nero-scheduler",
                )
                raise ScheduleError(blocker)

            state = self._git_state(task.repository)
            if task.write_required:
                blocker = self._write_blocker(state)
                if blocker:
                    self.store.transition_task(
                        task_id,
                        TaskStatus.BLOCKED,
                        expected_status=task.status,
                        expected_version=task.version,
                        blocker=blocker,
                        actor="nero-scheduler",
                    )
                    raise ScheduleError(blocker)
                owner = f"{adapter_id}:{task_id}"
                acquisition = self.lease_registry.acquire(
                    state.common_directory,
                    owner=owner,
                    task_id=task_id,
                    ttl_seconds=self.lease_ttl_seconds,
                )
                if acquisition.expired:
                    self._lease_event("lease.expired", acquisition.expired)
                if acquisition.grant is None:
                    active = acquisition.active
                    self._event(
                        "lease.denied",
                        task_id=task_id,
                        payload={
                            "repository_key": state.common_directory,
                            "requested_owner": owner,
                            "active_owner": active.owner if active else None,
                            "active_task_id": active.task_id if active else None,
                            "expires_at": active.expires_at if active else None,
                        },
                    )
                    if active is None or active.task_id != task_id:
                        blocker = (
                            f"repository write lease is held by {active.owner} until "
                            f"{active.expires_at}"
                            if active
                            else "repository write lease acquisition failed"
                        )
                        self.store.transition_task(
                            task_id,
                            TaskStatus.BLOCKED,
                            expected_status=task.status,
                            expected_version=task.version,
                            blocker=blocker,
                            actor="nero-scheduler",
                        )
                    else:
                        blocker = "assignment is already in progress for this task"
                    raise ScheduleError(blocker)
                credential = acquisition.grant
                self._lease_event("lease.acquired", credential.lease)

            claimed = self.store.assign_task(
                task_id,
                adapter_id=adapter_id,
                branch=state.branch,
                worktree=state.worktree,
                expected_version=task.version,
                actor="nero-scheduler",
            )

            if credential:
                # Re-check after the cross-database claim. Any policy drift
                # compensates by releasing the canonical lease and blocking.
                state = self._git_state(task.repository)
                blocker = self._write_blocker(state)
                if blocker:
                    self._release_credential(task_id, credential)
                    credential = None
                    claimed = self.store.transition_task(
                        task_id,
                        TaskStatus.BLOCKED,
                        expected_status=claimed.status,
                        expected_version=claimed.version,
                        blocker=blocker,
                        actor="nero-scheduler",
                    )
                    raise ScheduleError(blocker)

            lease = credential.lease if credential else None
            context = {
                **user_context,
                "git_relationship": state.relationship,
                "remote_state_fresh": state.remote_state_fresh,
                "clean": state.clean,
                "remote_writes_allowed": False,
            }
            packet = adapter.prepare_packet(
                claimed,
                lease_owner=lease.owner if lease else None,
                lease_id=lease.lease_id if lease else None,
                lease_fencing_token=lease.fencing_token if lease else None,
                lease_expires_at=lease.expires_at if lease else None,
                bounded_context=context,
            )
            self.store.record_event(
                "worker.packet_prepared",
                actor="nero-scheduler",
                task_id=task_id,
                payload={
                    "adapter": adapter_id,
                    "provider": adapter.provider,
                    "context_version": packet.context_version,
                    "write_allowed": packet.write_allowed,
                    "action_time_lease_validation_required": True,
                    "remote_writes_allowed": False,
                    "bounded_context_keys": sorted(packet.bounded_context),
                },
            )
            if credential:
                self._task_credentials[task_id] = credential
                state = replace(
                    state, active_write_lease=credential.lease.as_dict()
                )
            return Assignment(claimed, packet, state, lease)
        except SafeModeError:
            if credential:
                self._release_credential(task_id, credential)
            raise
        except (
            AdapterError,
            GitInspectionError,
            LeaseRegistryError,
            StoreConflict,
            StoreError,
            ScheduleError,
        ) as exc:
            if credential and task_id not in self._task_credentials:
                self._release_credential(task_id, credential)
            if claimed and claimed.status is TaskStatus.PREPARING:
                current = self.store.get_task(task_id)
                if current and current.status is TaskStatus.PREPARING:
                    try:
                        self.store.transition_task(
                            task_id,
                            TaskStatus.FAILED,
                            expected_status=current.status,
                            expected_version=current.version,
                            blocker="assignment failed before a worker packet was issued",
                            actor="nero-scheduler",
                        )
                    except StoreError:
                        pass
            self._event(
                "worker.assignment.denied",
                task_id=task_id,
                payload={"reason": self._reason_code(exc), "adapter": adapter_id},
                best_effort=True,
            )
            if isinstance(exc, ScheduleError):
                raise
            raise ScheduleError(str(exc)) from exc

    def transition(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        expected_version: int,
        blocker: str | None = None,
        result_payload: Mapping[str, Any] | None = None,
    ) -> Task:
        self._event(
            "task.transition.requested",
            task_id=task_id,
            payload={"to": status.value, "expected_version": expected_version},
        )
        try:
            task = self.store.get_task(task_id)
            if task is None:
                raise ScheduleError(f"unknown task: {task_id}")
            if task.version != int(expected_version):
                raise ScheduleError(
                    f"task version changed: expected {expected_version}, "
                    f"found {task.version}"
                )
            if status not in ALLOWED_TRANSITIONS[task.status]:
                raise ScheduleError(
                    f"invalid task transition: {task.status.value} -> {status.value}"
                )

            result: AgentResult | None = None
            if result_payload is not None:
                if not task.assigned_adapter:
                    raise ScheduleError(
                        "task has no assigned adapter for result normalization"
                    )
                adapter = self.adapters.get(task.assigned_adapter)
                if adapter is None:
                    raise ScheduleError("assigned adapter is unavailable")
                result = adapter.normalize_result(result_payload)
            if status is TaskStatus.COMPLETE:
                if result is None:
                    raise ScheduleError(
                        "verified completion requires a normalized worker result"
                    )
                if not result.tests_run:
                    raise ScheduleError(
                        "verified completion requires explicit verification evidence"
                    )

            if task.write_required and status in ACTIVE_WRITE_STATUSES | {
                TaskStatus.COMPLETE
            }:
                self._validate_task_lease(task)
                if status is TaskStatus.COMPLETE:
                    state = self._git_state(task.repository)
                    if (
                        state.branch != task.branch
                        or state.worktree != task.worktree
                        or state.conflict_count
                    ):
                        raise ScheduleError(
                            "write-task completion rejected because branch, "
                            "worktree, or conflict state changed"
                        )

            transitioned = self.store.transition_task(
                task_id,
                status,
                expected_status=task.status,
                expected_version=task.version,
                blocker=blocker,
                result=result,
                actor="nero-scheduler",
            )
            if status is TaskStatus.COMPLETE:
                self.store.record_event(
                    "task.verification.completed",
                    actor="nero-scheduler",
                    task_id=task_id,
                    payload={
                        "evidence": list(result.tests_run),
                        "summary": result.summary,
                    },
                )
            if task.write_required and status in RELEASE_STATUSES:
                self._release_known_lease(task_id)
            return transitioned
        except SafeModeError:
            raise
        except (AdapterError, LeaseRegistryError, StoreConflict, StoreError, ScheduleError) as exc:
            self._event(
                "task.transition.denied",
                task_id=task_id,
                payload={"reason": self._reason_code(exc), "to": status.value},
                best_effort=True,
            )
            if isinstance(exc, ScheduleError):
                raise
            raise ScheduleError(str(exc)) from exc

    def retry(self, task_id: str, *, expected_version: int) -> Task:
        task = self.store.get_task(task_id)
        if task is None:
            raise ScheduleError(f"unknown task: {task_id}")
        if task.version != int(expected_version):
            raise ScheduleError(
                f"task version changed: expected {expected_version}, found {task.version}"
            )
        if task.status not in {
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.PAUSED,
        }:
            raise ScheduleError("only failed, blocked, or paused tasks can be retried")
        return self.store.transition_task(
            task_id,
            TaskStatus.QUEUED,
            expected_status=task.status,
            expected_version=task.version,
            blocker=None,
            actor="nero-scheduler",
        )

    def heartbeat(self, task_id: str, *, expected_version: int) -> Lease:
        task = self.store.get_task(task_id)
        if task is None:
            raise ScheduleError(f"unknown task: {task_id}")
        if task.version != int(expected_version):
            raise ScheduleError(
                f"task version changed: expected {expected_version}, found {task.version}"
            )
        if not task.write_required or task.status not in ACTIVE_WRITE_STATUSES:
            raise ScheduleError("task has no active write lease to renew")
        credential = self._task_credentials.get(task_id)
        if credential is None:
            # Credentials intentionally remain process-local. A second Core
            # process may observe the shared task database, but it must never
            # revoke another live process's canonical lease simply because it
            # does not possess that secret. Canonical expiry/revocation is the
            # authority for declaring lease loss.
            raise ScheduleError("write lease credential is owned by another Core process")
        lease = credential.lease
        try:
            renewed = self.lease_registry.heartbeat(
                lease.repository_key,
                lease.lease_id,
                lease.fencing_token,
                credential.token,
                ttl_seconds=self.lease_ttl_seconds,
            )
        except LeaseRegistryError as exc:
            self._task_credentials.pop(task_id, None)
            self._block_lost_lease(task, "write lease expired or was revoked")
            raise ScheduleError(str(exc)) from exc
        self._task_credentials[task_id] = LeaseGrant(renewed, credential.token)
        self._lease_event("lease.heartbeat", renewed)
        return renewed

    def reconcile_write_leases(self) -> None:
        for task in self.store.list_tasks():
            if not task.write_required or task.status not in ACTIVE_WRITE_STATUSES:
                continue
            try:
                discovery = self.git.inspect(task.repository)
                observation = self.lease_registry.observe(
                    discovery.common_directory
                )
                if observation.expired:
                    self._lease_event("lease.expired", observation.expired)
                active = observation.active
                credential = self._task_credentials.get(task.task_id)
                if active and active.task_id == task.task_id:
                    # A matching unexpired registry row is sufficient for
                    # observation. Only the owning process can renew or use it
                    # because the bearer token is never persisted in Core.
                    if credential and (
                        active.lease_id != credential.lease.lease_id
                        or active.fencing_token != credential.lease.fencing_token
                    ):
                        self._task_credentials.pop(task.task_id, None)
                    continue
                self._task_credentials.pop(task.task_id, None)
                self._block_lost_lease(
                    task,
                    "write lease expired, was revoked, or belongs to another task",
                )
            except (StoreConflict, StoreError, LeaseRegistryError):
                continue

    def observe_lease(self, common_directory: str) -> Lease | None:
        observation = self.lease_registry.observe(common_directory)
        if observation.expired:
            self._lease_event("lease.expired", observation.expired)
        return observation.active

    def _git_state(self, repository: str) -> GitState:
        discovery = self.git.inspect(repository)
        raw = self.store.get_meta(fetch_metadata_key(discovery.common_directory))
        receipt = FetchReceipt.parse(raw)
        return self.git.inspect(repository, fetch_receipt=receipt)

    def _validate_task_lease(self, task: Task) -> Lease:
        credential = self._task_credentials.get(task.task_id)
        if credential is None:
            raise ScheduleError("write lease credential is unavailable")
        lease = credential.lease
        try:
            return self.lease_registry.validate(
                lease.repository_key,
                lease.lease_id,
                lease.fencing_token,
                credential.token,
            )
        except LeaseRegistryError as exc:
            raise ScheduleError(str(exc)) from exc

    def _release_known_lease(self, task_id: str) -> None:
        credential = self._task_credentials.pop(task_id, None)
        if credential is None:
            self._event(
                "lease.release_deferred",
                task_id=task_id,
                payload={
                    "reason": "lease credential unavailable; canonical expiry is authoritative"
                },
            )
            return
        self._release_credential(task_id, credential)

    def _release_credential(self, task_id: str, credential: LeaseGrant) -> None:
        lease = credential.lease
        released, active = self.lease_registry.release(
            lease.repository_key,
            lease.lease_id,
            lease.fencing_token,
            credential.token,
        )
        self._event(
            "lease.released" if released else "lease.release_denied",
            task_id=task_id,
            payload={
                "repository_key": lease.repository_key,
                "lease_id": lease.lease_id,
                "fencing_token": lease.fencing_token,
                "active_lease_id": active.lease_id if active else None,
            },
            best_effort=True,
        )

    def _block_lost_lease(self, task: Task, reason: str) -> None:
        current = self.store.get_task(task.task_id)
        if current is None or current.status not in ACTIVE_WRITE_STATUSES:
            return
        self.store.transition_task(
            task.task_id,
            TaskStatus.BLOCKED,
            expected_status=current.status,
            expected_version=current.version,
            blocker=reason,
            actor="nero-scheduler",
        )
        self._event(
            "lease.revoked",
            task_id=task.task_id,
            payload={"reason": reason},
            best_effort=True,
        )

    def _lease_event(self, event_type: str, lease: Lease) -> None:
        self._event(
            event_type,
            task_id=lease.task_id,
            payload={
                "repository_key": lease.repository_key,
                "lease_id": lease.lease_id,
                "fencing_token": lease.fencing_token,
                "owner": lease.owner,
                "expires_at": lease.expires_at,
            },
        )

    def _event(
        self,
        event_type: str,
        *,
        task_id: str | None,
        payload: dict[str, Any],
        best_effort: bool = False,
    ) -> None:
        try:
            self.store.record_event(
                event_type,
                actor="nero-scheduler",
                task_id=task_id,
                payload=payload,
            )
        except StoreError:
            if not best_effort:
                raise

    @staticmethod
    def _validate_context(context: Mapping[str, Any]) -> None:
        validate_bounded_context(context)
        reserved = _reserved_paths(context)
        if reserved:
            raise ScheduleError(
                "bounded context cannot override Core-owned fields at: "
                + ", ".join(reserved)
            )

    @staticmethod
    def _write_blocker(state: GitState) -> str | None:
        if not state.remote_state_fresh:
            return "write task blocked until a successful fresh fetch"
        if state.detached_head:
            return "write task blocked on detached HEAD"
        if not state.upstream:
            return "write task blocked because the local branch has no upstream"
        if state.conflict_count:
            return (
                f"write task blocked by {state.conflict_count} unresolved conflict(s)"
            )
        if not state.clean:
            return "write task blocked because the worktree is dirty"
        if state.behind:
            return (
                f"write task blocked because {state.branch} is {state.behind} commits "
                f"behind {state.upstream}"
            )
        return None

    @staticmethod
    def _reason_code(exc: Exception) -> str:
        if isinstance(exc, StoreConflict):
            return "state_conflict"
        if isinstance(exc, LeaseRegistryError):
            return "lease_invalid"
        if isinstance(exc, AdapterError):
            return "context_rejected"
        text = str(exc).lower()
        if "version" in text or "transition" in text or "not queued" in text:
            return "state_conflict"
        if "lease" in text:
            return "lease_unavailable"
        if "dependenc" in text:
            return "dependency_incomplete"
        return "policy_rejected"


def _normalized_context_key(value: Any) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def _reserved_paths(value: Any, path: str = "context") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if _normalized_context_key(key) in RESERVED_CONTEXT_KEYS:
                found.append(child)
            else:
                found.extend(_reserved_paths(nested, child))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found.extend(_reserved_paths(nested, f"{path}[{index}]"))
    return sorted(found)


def fetch_metadata_key(common_directory: str) -> str:
    return (
        "git.fetch_receipt:"
        + str(Path(common_directory).resolve()).casefold()
    )
