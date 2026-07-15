"""Explicitly launched Nero Core composition service for Mission Control."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .adapters import ManualWorkerAdapter, default_adapters
from .contracts import (
    ApprovalStatus,
    GitState,
    Lease,
    RiskLevel,
    Task,
    TaskStatus,
    WorkerDescriptor,
    WorkerStatus,
)
from .git_service import FetchReceipt, GitInspectionError, GitService
from .lease_registry import RepositoryLeaseRegistry
from .scheduler import Assignment, ScheduleError, Scheduler, fetch_metadata_key
from .store import CoreStore, SafeModeError, StoreConflict, StoreError


REMOTE_MUTATIONS = {
    "git.push",
    "git.pull",
    "git.merge",
    "git.rebase",
    "git.delete_branch",
}


def canonical_core_db(repository: str | Path, git: GitService | None = None) -> Path:
    """Return the one production Core database shared by all Git worktrees."""
    inspector = git or GitService()
    state = inspector.inspect(repository)
    return Path(state.common_directory) / "nero-core" / "mission-control.db"


class MissionControlService:
    """Owns deterministic orchestration state; workers remain replaceable."""

    def __init__(
        self,
        repository: str | Path,
        db_path: str | Path | None = None,
        *,
        git: GitService | None = None,
        adapters: Mapping[str, ManualWorkerAdapter] | None = None,
        lease_registry: RepositoryLeaseRegistry | None = None,
        lease_ttl_seconds: int = 120,
    ) -> None:
        self.repository = str(Path(repository).resolve())
        self.git = git or GitService()
        resolved_db = (
            Path(db_path).resolve()
            if db_path is not None
            else canonical_core_db(self.repository, self.git).resolve()
        )
        self.store = CoreStore(resolved_db)
        self.adapters = dict(adapters or default_adapters())
        self.lease_registry = lease_registry or RepositoryLeaseRegistry()
        self.scheduler = Scheduler(
            self.store,
            self.git,
            self.adapters,
            lease_registry=self.lease_registry,
            lease_ttl_seconds=lease_ttl_seconds,
        )
        self._started = False

    def initialize(self) -> None:
        if self._started:
            return
        self.store.initialize()
        self._started = True
        valid, _ = self.store.verify_event_chain()
        if not valid:
            return
        self.store.record_event(
            "core.started",
            actor="nero-core",
            payload={
                "repository": self.repository,
                "mode": "manual",
                "remote_mutations_enabled": False,
                "host_presence_autostart": False,
                "coordination": "git-common-directory",
            },
        )

    def git_state(self, *, refresh_remote: bool = False) -> GitState:
        self._require_started()
        discovery = self.git.inspect(self.repository)
        key = fetch_metadata_key(discovery.common_directory)
        receipt = FetchReceipt.parse(self.store.get_meta(key))
        chain_ok, _ = self.store.verify_event_chain()
        observation = (
            self.lease_registry.observe(discovery.common_directory)
            if chain_ok
            else self.lease_registry.peek(discovery.common_directory)
        )
        active = observation.active
        if refresh_remote:
            # This event-chain write is the safe-mode guard. A corrupt journal
            # stops before any fetch metadata mutation occurs.
            self.store.record_event(
                "git.fetch.requested",
                actor="operator",
                payload={
                    "repository": discovery.repository,
                    "tracking_remote": discovery.remote_name,
                    "upstream": discovery.upstream,
                },
            )
        try:
            state = self.git.inspect(
                self.repository,
                fetch_remote=refresh_remote,
                fetch_receipt=receipt,
                active_write_lease=active.as_dict() if active else None,
            )
        except GitInspectionError as exc:
            if refresh_remote:
                attempted = datetime.now(UTC).isoformat(timespec="milliseconds")
                failed_receipt = FetchReceipt(
                    version=1,
                    repository_key=discovery.common_directory,
                    tracking_remote=discovery.remote_name,
                    remote_url=discovery.remote_url,
                    upstream=discovery.upstream,
                    attempted_at=attempted,
                    succeeded=False,
                    fetched_at=None,
                    authentication="inspection_failed",
                )
                self.store.set_meta(
                    key,
                    json.dumps(
                        failed_receipt.as_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    event_type="git.fetch.failed",
                    actor="nero-git",
                    payload={
                        "tracking_remote": discovery.remote_name,
                        "upstream": discovery.upstream,
                        "authentication": "inspection_failed",
                        "errors": [str(exc)],
                    },
                )
            raise
        if refresh_remote:
            if state.fetch_receipt is None:  # pragma: no cover - invariant
                raise GitInspectionError("Git refresh did not produce a fetch receipt")
            event_type = (
                "git.fetch.completed"
                if state.remote_state_fresh
                else "git.fetch.failed"
            )
            self.store.set_meta(
                key,
                json.dumps(
                    state.fetch_receipt,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                event_type=event_type,
                actor="nero-git",
                payload={
                    "tracking_remote": state.remote_name,
                    "remote_url": state.remote_url,
                    "upstream": state.upstream,
                    "authentication": state.authentication,
                    "relationship": state.relationship,
                    "errors": list(state.errors),
                },
            )
        return state

    def queue_task(
        self,
        *,
        objective: str,
        priority: int = 50,
        dependencies: tuple[str, ...] = (),
        acceptance_criteria: tuple[str, ...] = (),
        write_required: bool = False,
    ) -> Task:
        self._require_started()
        state = self.git_state(refresh_remote=False)
        return self.store.create_task(
            objective=objective,
            repository=self.repository,
            priority=priority,
            dependencies=dependencies,
            acceptance_criteria=acceptance_criteria,
            write_required=write_required,
            branch=state.branch,
            worktree=state.worktree,
            context_version="mission-control-m1",
            actor="operator",
        )

    def assign_task(
        self,
        task_id: str,
        adapter_id: str,
        *,
        expected_version: int,
        bounded_context: Mapping[str, Any] | None = None,
    ) -> Assignment:
        self._require_started()
        return self.scheduler.assign(
            task_id,
            adapter_id,
            expected_version=expected_version,
            bounded_context=bounded_context,
        )

    def transition_task(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        expected_version: int,
        blocker: str | None = None,
        result: Mapping[str, Any] | None = None,
    ) -> Task:
        self._require_started()
        return self.scheduler.transition(
            task_id,
            status,
            expected_version=expected_version,
            blocker=blocker,
            result_payload=result,
        )

    def retry_task(self, task_id: str, *, expected_version: int) -> Task:
        self._require_started()
        return self.scheduler.retry(task_id, expected_version=expected_version)

    def heartbeat_task_lease(
        self, task_id: str, *, expected_version: int
    ) -> Lease:
        self._require_started()
        # Guard the canonical coordination mutation with the Core integrity
        # boundary. If the chain is corrupt, this fails before lease expiry or
        # history can change in the separate registry database.
        self.store.record_event(
            "lease.heartbeat.requested",
            actor="operator",
            task_id=task_id,
            payload={"expected_version": int(expected_version)},
        )
        return self.scheduler.heartbeat(
            task_id, expected_version=expected_version
        )

    def tasks(self) -> list[Task]:
        self._require_started()
        self._reconcile_if_writable()
        return self.store.list_tasks()

    def workers(self) -> list[WorkerDescriptor]:
        self._require_started()
        self._reconcile_if_writable()
        tasks = self.store.list_tasks()
        active_statuses = {
            TaskStatus.PREPARING,
            TaskStatus.RUNNING,
            TaskStatus.WAITING,
            TaskStatus.VERIFYING,
            TaskStatus.BLOCKED,
        }
        result: list[WorkerDescriptor] = []
        for adapter_id, adapter in sorted(self.adapters.items()):
            descriptor = adapter.descriptor()
            assigned = next(
                (
                    task
                    for task in tasks
                    if task.assigned_adapter == adapter_id
                    and task.status in active_statuses
                ),
                None,
            )
            if assigned:
                descriptor = replace(
                    descriptor,
                    status=WorkerStatus(assigned.status.value),
                    assigned_task=assigned.task_id,
                    last_result=assigned.last_result,
                )
            result.append(descriptor)
        return result

    def request_approval(
        self,
        *,
        action: str,
        summary: str,
        risk: RiskLevel,
    ):
        self._require_started()
        return self.store.request_approval(
            action=action,
            summary=summary,
            risk=risk,
            requested_by="operator",
        )

    def decide_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        note: str,
    ):
        self._require_started()
        approval = self.store.decide_approval(
            approval_id,
            approved=approved,
            decided_by="operator",
            note=note,
        )
        if approval.action in REMOTE_MUTATIONS:
            self.store.record_event(
                "remote_mutation.not_executed",
                actor="nero-core",
                payload={
                    "approval_id": approval.approval_id,
                    "action": approval.action,
                    "reason": (
                        "Milestone 1 is read-only; approval is evidence, "
                        "not execution"
                    ),
                },
            )
        return approval

    def approvals(self):
        self._require_started()
        return self.store.list_approvals()

    def events(
        self,
        *,
        event_type: str | None = None,
        task_id: str | None = None,
        limit: int = 200,
    ):
        self._require_started()
        return self.store.list_events(
            event_type=event_type, task_id=task_id, limit=limit
        )

    def overview(self) -> dict[str, Any]:
        self._require_started()
        self._reconcile_if_writable()
        tasks = self.store.list_tasks()
        active = next(
            (
                task
                for task in tasks
                if task.status
                not in {
                    TaskStatus.COMPLETE,
                    TaskStatus.CANCELLED,
                    TaskStatus.FAILED,
                }
            ),
            None,
        )
        pending = self.store.list_approvals(status=ApprovalStatus.PENDING)
        chain_ok, chain_message = self.store.verify_event_chain()
        return {
            "identity": "Nero Core",
            "authority": "local deterministic control plane",
            "launch_mode": "manual",
            "mission": (
                active.objective
                if active
                else "Keep repository state measured and safe"
            ),
            "active_step": active.status.value if active else "idle",
            "decision_state": (
                "safe_mode"
                if not chain_ok
                else ("approval_required" if pending else "within_policy")
            ),
            "verification": {
                "integrity_ok": chain_ok,
                "message": chain_message,
                "confidence": (
                    "audit_integrity_verified"
                    if chain_ok
                    else "audit_integrity_failed"
                ),
                "active_task_status": active.status.value if active else "none",
            },
            "system_health": "healthy" if chain_ok else "safe_mode",
            "pending_approvals": len(pending),
            "task_counts": self._task_counts(tasks),
            "remote_mutations_enabled": False,
            "host_presence_autostart": False,
        }

    def health(self) -> dict[str, Any]:
        self._require_started()
        chain_ok, message = self.store.verify_event_chain()
        try:
            discovery = self.git.inspect(self.repository)
            coordination_db = str(
                self.lease_registry.database_path(discovery.common_directory)
            )
        except GitInspectionError:
            coordination_db = "unavailable"
        return {
            "ok": chain_ok,
            "mode": "normal" if chain_ok else "safe_mode",
            "event_chain": message,
            "database": str(self.store.db_path),
            "coordination_database": coordination_db,
            "repository": self.repository,
            "adapters": sorted(self.adapters),
            "remote_mutation_capabilities": [],
            "legacy_app_unlocked": False,
        }

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError(
                "Mission Control must be initialized by its manual entrypoint"
            )

    def _reconcile_if_writable(self) -> None:
        """Reconcile only while Core's event chain is safe to mutate."""
        chain_ok, _ = self.store.verify_event_chain()
        if chain_ok:
            self.scheduler.reconcile_write_leases()

    @staticmethod
    def _task_counts(tasks: list[Task]) -> dict[str, int]:
        counts = {status.value: 0 for status in TaskStatus}
        for task in tasks:
            counts[task.status.value] += 1
        return counts


__all__ = [
    "GitInspectionError",
    "MissionControlService",
    "SafeModeError",
    "ScheduleError",
    "StoreConflict",
    "StoreError",
    "canonical_core_db",
]
