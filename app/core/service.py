"""Explicitly launched Nero Core composition service for Mission Control."""
from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .adapters import ManualWorkerAdapter, default_adapters
from .contracts import (
    AttentionItem,
    ApprovalStatus,
    Event,
    GitState,
    Lease,
    RiskLevel,
    Task,
    TaskStatus,
    VerificationBackendCapabilities,
    VerificationProfile,
    VerificationRun,
    VerificationStatus,
    WorkerDescriptor,
    WorkerStatus,
)
from .git_service import FetchReceipt, GitInspectionError, GitService
from .lease_registry import RepositoryLeaseRegistry
from .scheduler import Assignment, ScheduleError, Scheduler, fetch_metadata_key
from .store import CoreStore, SafeModeError, StoreConflict, StoreError
from .verification import (
    DisabledRunner,
    VerificationExecutionResult,
    VerificationPolicyError,
    VerificationProfileRegistry,
    VerificationRunner,
    bounded_execution_result,
    canonical_digest,
    validate_backend_capabilities,
)


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
        verification_registry: VerificationProfileRegistry | None = None,
        verification_runner: VerificationRunner | None = None,
        authorized_verification_backends: frozenset[str] | None = None,
        allow_test_backend_authority: bool = False,
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
        self.verification_registry = (
            verification_registry or VerificationProfileRegistry()
        )
        self.verification_runner = verification_runner or DisabledRunner()
        self.authorized_verification_backends = (
            frozenset()
            if authorized_verification_backends is None
            else frozenset(authorized_verification_backends)
        )
        self.allow_test_backend_authority = bool(allow_test_backend_authority)
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
        self._reconcile_abandoned_verifications()
        self.scheduler.reconcile_write_leases()
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
        if not chain_ok:
            receipt = None
        observation = (
            self.lease_registry.observe(discovery.common_directory)
            if refresh_remote and chain_ok
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
                    version=2,
                    repository_key=discovery.common_directory,
                    tracking_remote=discovery.remote_name,
                    remote_url=discovery.remote_url,
                    remote_fingerprint=None,
                    upstream=discovery.upstream,
                    merge_ref=discovery.tracked_merge_ref,
                    upstream_oid=None,
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
        verification_profile_id: str | None = None,
    ) -> Task:
        self._require_started()
        state = self.git_state(refresh_remote=False)
        profile = (
            self.verification_registry.get(verification_profile_id)
            if verification_profile_id
            else None
        )
        task = self.store.create_task(
            objective=objective,
            repository=state.repository,
            priority=priority,
            dependencies=dependencies,
            acceptance_criteria=acceptance_criteria,
            write_required=write_required,
            branch=state.branch,
            worktree=state.worktree,
            context_version="mission-control-m2",
            actor="operator",
        )
        if profile is None:
            return task
        return self.store.bind_verification_profile(
            task.task_id,
            profile=profile,
            expected_version=task.version,
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
        task = self.store.get_task(task_id)
        if task is None:
            raise ScheduleError(f"unknown task: {task_id}")
        profile_fields = (
            task.verification_profile_id,
            task.verification_profile_version,
            task.verification_profile_digest,
        )
        if any(value is not None for value in profile_fields):
            if not all(value is not None for value in profile_fields):
                raise VerificationPolicyError(
                    "task verification profile binding is incomplete"
                )
            self.verification_registry.resolve(
                task.verification_profile_id or "",
                version=task.verification_profile_version,
                digest=task.verification_profile_digest,
            )
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
        return self.store.list_tasks()

    def reconcile(self) -> dict[str, Any]:
        """Run protected lifecycle reconciliation; observational GETs stay pure."""

        self._require_started()
        self._reconcile_if_writable()
        chain_ok, message = self.store.verify_event_chain()
        return {
            "reconciliation_attempted": bool(chain_ok),
            "internal_state_ok": bool(chain_ok),
            "message": message,
        }

    def verification_profiles(self) -> dict[str, Any]:
        """Return the content-addressed catalog and backend capability claim."""
        self._require_started()
        capabilities = validate_backend_capabilities(
            self.verification_runner.capabilities
        )
        return {
            "catalog_digest": self.verification_registry.catalog_digest(),
            "profiles": [
                profile.as_dict()
                for profile in self.verification_registry.profiles()
            ],
            "backend": capabilities.as_dict(),
            "execution_available": capabilities.execution_available,
            "production_default": type(self.verification_runner) is DisabledRunner,
        }

    def bind_verification_profile(
        self,
        task_id: str,
        profile_id: str,
        *,
        expected_version: int,
    ) -> Task:
        self._require_started()
        profile = self.verification_registry.get(profile_id)
        return self.store.bind_verification_profile(
            task_id,
            profile=profile,
            expected_version=expected_version,
            actor="operator",
        )

    def verification_runs(
        self,
        *,
        task_id: str | None = None,
        status: VerificationStatus | str | None = None,
        limit: int = 100,
    ) -> list[VerificationRun]:
        self._require_started()
        normalized = VerificationStatus(status) if status is not None else None
        return self.store.list_verification_runs(
            task_id=task_id,
            status=normalized,
            limit=max(1, min(int(limit), 500)),
        )

    def verification_run(self, run_id: str) -> VerificationRun | None:
        self._require_started()
        return self.store.get_verification_run(run_id)

    def run_verification(
        self,
        task_id: str,
        *,
        expected_version: int,
    ) -> VerificationRun:
        """Claim, bind, and terminalize one Core-owned verification attempt."""
        self._require_started()
        task = self.store.get_task(task_id)
        if task is None:
            raise ScheduleError(f"unknown task: {task_id}")
        if task.version != int(expected_version):
            raise ScheduleError(
                f"task version changed: expected {expected_version}, found {task.version}"
            )
        if task.status is not TaskStatus.VERIFYING:
            raise ScheduleError("Core verification requires VERIFYING task state")
        if not all(
            (
                task.verification_profile_id,
                task.verification_profile_version is not None,
                task.verification_profile_digest,
            )
        ):
            raise ScheduleError("task has no pinned verification profile")
        profile = self.verification_registry.resolve(
            task.verification_profile_id,
            version=task.verification_profile_version,
            digest=task.verification_profile_digest,
        )
        before = self.scheduler.verification_git_state(task)
        self._require_bound_workspace(task, before)
        lease_before = self.scheduler.validate_verification_lease(task)
        self._require_bound_lease(task, before, lease_before)
        capabilities_before = validate_backend_capabilities(
            self.verification_runner.capabilities
        )
        requested_at = self._now()
        run_id = str(uuid4())
        attempt = self.store.next_verification_attempt(task_id)
        run = VerificationRun(
            run_id=run_id,
            task_id=task_id,
            task_version=task.version,
            attempt=attempt,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            profile_digest=profile.manifest_digest,
            status=VerificationStatus.RUNNING,
            authoritative=False,
            backend_id=capabilities_before.backend_id,
            backend_version=capabilities_before.backend_version,
            backend_capabilities=capabilities_before.as_dict(),
            repository_key=before.common_directory,
            repository=before.repository,
            worktree=before.worktree,
            branch=before.branch,
            head_before=self._head_for_state(before),
            head_after=None,
            clean_before=before.clean,
            clean_after=False,
            lease_id=lease_before.lease_id if lease_before else None,
            lease_fencing_token=(
                lease_before.fencing_token if lease_before else None
            ),
            requested_at=requested_at,
            started_at=requested_at,
            completed_at=None,
            evidence={},
            evidence_hash=None,
            error_code=None,
            version=0,
        )
        claimed = self.store.begin_verification_run(
            run,
            expected_task_status=TaskStatus.VERIFYING,
            expected_task_version=task.version,
            actor="nero-verification",
        )

        try:
            return self._finish_verification_claim(
                task=task,
                profile=profile,
                before=before,
                lease_before=lease_before,
                capabilities_before=capabilities_before,
                claimed=claimed,
            )
        except Exception as original:
            # Once Core has claimed the task/version, every ordinary internal
            # failure must be converted into a durable non-authoritative
            # terminal receipt. The exception text is deliberately not stored.
            try:
                return self._fail_closed_verification_claim(
                    task=task,
                    profile=profile,
                    before=before,
                    lease_before=lease_before,
                    capabilities_before=capabilities_before,
                    claimed=claimed,
                )
            except Exception:
                raise original

    def _finish_verification_claim(
        self,
        *,
        task: Task,
        profile: VerificationProfile,
        before: GitState,
        lease_before: Lease | None,
        capabilities_before: VerificationBackendCapabilities,
        claimed: VerificationRun,
    ) -> VerificationRun:
        backend_profile = replace(
            profile,
            harness_files=tuple(dict(item) for item in profile.harness_files),
        )
        try:
            execution = self.verification_runner.run(
                backend_profile,
                run_id=claimed.run_id,
                task_id=task.task_id,
                worktree=before.worktree,
            )
            if not isinstance(execution, VerificationExecutionResult):
                raise TypeError("backend returned an invalid result contract")
            execution = bounded_execution_result(execution)
        except Exception:
            execution = VerificationExecutionResult(
                status=VerificationStatus.ERROR,
                error_code="VERIFICATION_BACKEND_ERROR",
                detail="The verification backend returned an internal error.",
            )

        # This is the final backend-controlled call. Every task, profile, Git,
        # and lease measurement happens afterward, so backend cleanup cannot
        # mutate the workspace after Core's closing snapshot.
        capabilities_after = validate_backend_capabilities(
            self.verification_runner.capabilities
        )
        capabilities_changed = bool(
            capabilities_after.as_dict() != capabilities_before.as_dict()
        )
        backend_authorized, missing_capabilities = (
            self.verification_registry.backend_satisfies(
                profile,
                capabilities_after,
                authorized_backend_ids=self.authorized_verification_backends,
                allow_test_authority=self.allow_test_backend_authority,
            )
        )

        drift: list[str] = []
        try:
            after = self.scheduler.verification_git_state(task)
        except GitInspectionError:
            after = before
            drift.append("git_inspection_failed")
        if not after.inspection_ok or after.errors:
            drift.append("git_inspection_failed")
        current = self.store.get_task(task.task_id)
        if current is None or current.status is not TaskStatus.VERIFYING:
            drift.append("task_state_changed")
        elif current.version != task.version + 1:
            drift.append("task_version_changed")
        elif (
            current.verification_profile_id != profile.profile_id
            or current.verification_profile_version != profile.version
            or current.verification_profile_digest != profile.manifest_digest
        ):
            drift.append("task_profile_changed")
        try:
            self.verification_registry.resolve(
                profile.profile_id,
                version=profile.version,
                digest=profile.manifest_digest,
            )
        except VerificationPolicyError:
            drift.append("profile_drift")
        if self._workspace_changed(before, after):
            drift.append("workspace_drift")
        lease_after: Lease | None = None
        if task.write_required:
            try:
                lease_after = self.scheduler.validate_verification_lease(
                    current or task
                )
            except ScheduleError:
                drift.append("lease_lost")
            if (
                lease_before is None
                or lease_after is None
                or lease_before.lease_id != lease_after.lease_id
                or lease_before.fencing_token != lease_after.fencing_token
                or not self._lease_matches(task, after, lease_after)
            ):
                drift.append("lease_fence_changed")
        if capabilities_changed:
            drift.append("backend_capabilities_changed")
        completed_at = self._now()

        authoritative = bool(
            execution.status is VerificationStatus.PASSED
            and backend_authorized
            and not drift
        )
        terminal_status = execution.status
        error_code = execution.error_code
        if execution.status is VerificationStatus.PASSED and not authoritative:
            terminal_status = VerificationStatus.BLOCKED
            error_code = (
                "VERIFICATION_STATE_DRIFT"
                if drift
                else "VERIFICATION_BACKEND_NOT_AUTHORIZED"
            )
        elif drift:
            terminal_status = VerificationStatus.STALE
            error_code = "VERIFICATION_STATE_DRIFT"

        task_terminal_status = (
            TaskStatus.COMPLETE
            if authoritative
            else (
                TaskStatus.FAILED
                if terminal_status
                in {VerificationStatus.FAILED, VerificationStatus.TIMED_OUT}
                else TaskStatus.BLOCKED
            )
        )
        evidence = self._verification_evidence(
            claimed=claimed,
            profile=profile,
            before=before,
            after=after,
            capabilities_before=capabilities_before,
            backend_authorized=backend_authorized,
            missing_capabilities=missing_capabilities,
            drift=drift,
            execution=execution,
            terminal_status=terminal_status,
            authoritative=authoritative,
            completed_at=completed_at,
        )
        completion_fence = (
            self.scheduler.fence_verification_completion(task)
            if authoritative and task.write_required
            else nullcontext()
        )
        with completion_fence:
            finalized, _ = self.store.finalize_verification_run(
                claimed.run_id,
                expected_run_version=claimed.version,
                status=terminal_status,
                authoritative=authoritative,
                head_after=self._head_for_state(after),
                clean_after=after.clean,
                workspace_after=self._workspace_snapshot(after),
                completed_at=completed_at,
                evidence=evidence,
                evidence_hash=canonical_digest(evidence),
                error_code=error_code,
                task_terminal_status=task_terminal_status,
                blocker=(
                    None
                    if authoritative
                    else self._verification_blocker(
                        terminal_status, error_code, missing_capabilities, drift
                    )
                ),
                actor="nero-verification",
            )
        if task.write_required:
            self.scheduler.release_verification_lease(task.task_id)
        return finalized

    def _fail_closed_verification_claim(
        self,
        *,
        task: Task,
        profile: VerificationProfile,
        before: GitState,
        lease_before: Lease | None,
        capabilities_before: VerificationBackendCapabilities,
        claimed: VerificationRun,
    ) -> VerificationRun:
        persisted = self.store.get_verification_run(claimed.run_id)
        if persisted is None:
            raise StoreError("claimed verification run disappeared")
        if persisted.status is not VerificationStatus.RUNNING:
            if task.write_required:
                try:
                    self.scheduler.release_verification_lease(task.task_id)
                except Exception:
                    pass
            return persisted
        recovery_drift = ["internal_error"]
        try:
            after = self.scheduler.verification_git_state(task)
        except Exception:
            after = before
            recovery_drift.append("recovery_workspace_unavailable")
        if self._workspace_changed(before, after):
            recovery_drift.append("workspace_drift")
        if not after.inspection_ok or after.errors:
            recovery_drift.append("git_inspection_failed")
        completed_at = self._now()
        execution = VerificationExecutionResult(
            status=VerificationStatus.ERROR,
            error_code="VERIFICATION_INTERNAL_ERROR",
            detail=(
                "Core recovered an internal verification failure; no pass was accepted."
            ),
        )
        evidence = self._verification_evidence(
            claimed=claimed,
            profile=profile,
            before=before,
            after=after,
            capabilities_before=capabilities_before,
            backend_authorized=False,
            missing_capabilities=("internal_error",),
            drift=sorted(set(recovery_drift)),
            execution=execution,
            terminal_status=VerificationStatus.ERROR,
            authoritative=False,
            completed_at=completed_at,
        )
        finalized, _ = self.store.finalize_verification_run(
            claimed.run_id,
            expected_run_version=claimed.version,
            status=VerificationStatus.ERROR,
            authoritative=False,
            head_after=self._head_for_state(after),
            clean_after=after.clean,
            workspace_after=self._workspace_snapshot(after),
            completed_at=completed_at,
            evidence=evidence,
            evidence_hash=canonical_digest(evidence),
            error_code="VERIFICATION_INTERNAL_ERROR",
            task_terminal_status=TaskStatus.BLOCKED,
            blocker=(
                "Core recovered an internal verification failure; "
                "the run is non-authoritative"
            ),
            actor="nero-verification",
        )
        if task.write_required:
            self.scheduler.release_verification_lease(task.task_id)
        return finalized

    def _verification_evidence(
        self,
        *,
        claimed: VerificationRun,
        profile: VerificationProfile,
        before: GitState,
        after: GitState,
        capabilities_before: VerificationBackendCapabilities,
        backend_authorized: bool,
        missing_capabilities: tuple[str, ...],
        drift: list[str],
        execution: VerificationExecutionResult,
        terminal_status: VerificationStatus,
        authoritative: bool,
        completed_at: str,
    ) -> dict[str, Any]:
        return {
            "binding": {
                "run_id": claimed.run_id,
                "task_id": claimed.task_id,
                "task_version": claimed.task_version,
                "attempt": claimed.attempt,
                "profile_id": claimed.profile_id,
                "profile_version": claimed.profile_version,
                "profile_digest": claimed.profile_digest,
                "backend_id": claimed.backend_id,
                "backend_version": claimed.backend_version,
                "repository_key": claimed.repository_key,
                "lease_id": claimed.lease_id,
                "lease_fencing_token": claimed.lease_fencing_token,
            },
            "profile": profile.as_dict(),
            "backend": {
                "capabilities": capabilities_before.as_dict(),
                "authorized": bool(backend_authorized),
                "missing_capabilities": list(missing_capabilities),
            },
            "workspace_before": self._workspace_snapshot(before),
            "workspace_after": self._workspace_snapshot(after),
            "drift": sorted(set(drift)),
            "runner_result": execution.as_evidence(),
            "final_status": terminal_status.value,
            "authoritative": bool(authoritative),
            "requested_at": claimed.requested_at,
            "completed_at": completed_at,
        }

    def attention(self, *, after_sequence: int = 0, limit: int = 100) -> dict[str, Any]:
        """Project durable events into a cursor-based local notification feed."""
        self._require_started()
        bounded_limit = max(1, min(int(limit), 500))
        current_sequence = self.store.latest_event_sequence()
        current_tasks = {
            task.task_id: task
            for task in self.store.list_tasks()
        }
        items: list[AttentionItem] = []
        cursor = max(0, int(after_sequence))
        processed_sequence = cursor
        while processed_sequence < current_sequence and len(items) < bounded_limit:
            batch = self.store.list_events_after(
                after_sequence=processed_sequence,
                through_sequence=current_sequence,
                limit=500,
            )
            if not batch:
                break
            for event in batch:
                processed_sequence = event.sequence
                item = self._attention_item(event)
                if item is not None:
                    if item.kind == "milestone" and item.requires_action:
                        current_task = current_tasks.get(item.task_id or "")
                        item = replace(
                            item,
                            requires_action=bool(
                                current_task is not None
                                and current_task.status.value == item.status
                                and current_task.updated_at == item.created_at
                            ),
                        )
                    items.append(item)
                    if len(items) >= bounded_limit:
                        break
            if len(batch) < 500:
                break
        next_cursor = min(processed_sequence, current_sequence)
        pending = self.store.list_approvals(status=ApprovalStatus.PENDING)
        return {
            "current_sequence": current_sequence,
            "next_cursor": next_cursor,
            "pending_approval_count": len(pending),
            "pending_approvals": [approval.as_dict() for approval in pending],
            "items": [item.as_dict() for item in items],
            "local_only": True,
        }

    def workers(self) -> list[WorkerDescriptor]:
        self._require_started()
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
                        "Mission Control records local approval evidence but "
                        "exposes no remote mutation executor"
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
        capabilities = self.verification_runner.capabilities
        latest_runs = self.store.list_verification_runs(limit=1)
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
                    "internal_chain_consistent"
                    if chain_ok
                    else "internal_chain_inconsistent"
                ),
                "active_task_status": active.status.value if active else "none",
            },
            "trusted_verification": {
                "catalog_digest": self.verification_registry.catalog_digest(),
                "profile_count": len(self.verification_registry.profiles()),
                "backend_id": capabilities.backend_id,
                "execution_available": capabilities.execution_available,
                "isolation_level": capabilities.isolation_level,
                "latest_run": latest_runs[0].as_dict() if latest_runs else None,
                "completion_authority": "core_receipt_only",
            },
            "internal_state_health": "consistent" if chain_ok else "inconsistent",
            "pending_approvals": len(pending),
            "task_counts": self._task_counts(tasks),
            "remote_mutations_enabled": False,
            "host_presence_autostart": False,
        }

    def health(self) -> dict[str, Any]:
        self._require_started()
        chain_ok, message = self.store.verify_event_chain()
        repository_inspection_ok = True
        repository_errors: list[str] = []
        try:
            discovery = self.git.inspect(self.repository)
            repository_inspection_ok = discovery.inspection_ok
            repository_errors = list(discovery.errors)
            coordination_db = str(
                self.lease_registry.database_path(discovery.common_directory)
            )
        except GitInspectionError:
            repository_inspection_ok = False
            repository_errors = ["repository inspection unavailable"]
            coordination_db = "unavailable"
        return {
            "internal_state_ok": chain_ok,
            "scope": "internal Core schema, event, and verification consistency",
            "mode": "normal" if chain_ok else "safe_mode",
            "event_chain": message,
            "database": str(self.store.db_path),
            "coordination_database": coordination_db,
            "repository_inspection_ok": repository_inspection_ok,
            "repository_errors": repository_errors,
            "repository": self.repository,
            "adapters": sorted(self.adapters),
            "verification_backend": self.verification_runner.capabilities.as_dict(),
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
            self._reconcile_abandoned_verifications()
            self.scheduler.reconcile_write_leases()

    def _reconcile_abandoned_verifications(self) -> None:
        """Seal crashed M2 DisabledRunner claims without stealing live backends."""
        if type(self.verification_runner) is not DisabledRunner:
            return
        now = datetime.now(UTC)
        for run in self.store.list_verification_runs(
            status=VerificationStatus.RUNNING,
            limit=500,
        ):
            try:
                started = datetime.fromisoformat(run.started_at)
                if started.tzinfo is None:
                    started = started.replace(tzinfo=UTC)
                if (now - started.astimezone(UTC)).total_seconds() < 30:
                    continue
                self._interrupt_abandoned_verification(run)
            except (ValueError, StoreConflict, StoreError, ScheduleError):
                continue

    def _interrupt_abandoned_verification(self, run: VerificationRun) -> None:
        task = self.store.get_task(run.task_id)
        if task is None or task.status is not TaskStatus.VERIFYING:
            return
        try:
            current = self.scheduler.verification_git_state(task)
            workspace_after = self._workspace_snapshot(current)
            head_after = self._head_for_state(current)
            clean_after = current.clean
            recovery_drift = ["core_process_interrupted"]
            workspace_before = {
                "repository_key": run.repository_key,
                "repository": run.repository,
                "worktree": run.worktree,
                "branch": run.branch,
                "head": run.head_before,
                "clean": run.clean_before,
                "conflict_count": 0,
                "detached_head": False,
            }
            if workspace_after != workspace_before:
                recovery_drift.append("workspace_drift")
            if not current.inspection_ok or current.errors:
                recovery_drift.append("git_inspection_failed")
        except Exception:
            workspace_before = {
                "repository_key": run.repository_key,
                "repository": run.repository,
                "worktree": run.worktree,
                "branch": run.branch,
                "head": run.head_before,
                "clean": run.clean_before,
                "conflict_count": 0,
                "detached_head": False,
            }
            workspace_after = dict(workspace_before)
            head_after = run.head_before
            clean_after = run.clean_before
            recovery_drift = [
                "core_process_interrupted",
                "recovery_workspace_unavailable",
            ]
        recovery_drift = sorted(set(recovery_drift))
        completed_at = self._now()
        empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        evidence: dict[str, Any] = {
            "binding": {
                "run_id": run.run_id,
                "task_id": run.task_id,
                "task_version": run.task_version,
                "attempt": run.attempt,
                "profile_id": run.profile_id,
                "profile_version": run.profile_version,
                "profile_digest": run.profile_digest,
                "backend_id": run.backend_id,
                "backend_version": run.backend_version,
                "repository_key": run.repository_key,
                "lease_id": run.lease_id,
                "lease_fencing_token": run.lease_fencing_token,
            },
            "profile": {
                "profile_id": run.profile_id,
                "version": run.profile_version,
                "manifest_digest": run.profile_digest,
                "recovery_projection_only": True,
            },
            "backend": {
                "capabilities": run.backend_capabilities,
                "authorized": False,
                "missing_capabilities": ["core_process_interrupted"],
            },
            "workspace_before": workspace_before,
            "workspace_after": workspace_after,
            "drift": recovery_drift,
            "runner_result": {
                "status": VerificationStatus.INTERRUPTED.value,
                "exit_code": None,
                "duration_ms": 0,
                "stdout_sha256": empty_hash,
                "stderr_sha256": empty_hash,
                "stdout_excerpt": "",
                "stderr_excerpt": "",
                "output_truncated": False,
                "error_code": "VERIFICATION_PROCESS_INTERRUPTED",
                "detail": (
                    "A prior Core process ended before the verification claim "
                    "was sealed. No pass was accepted."
                ),
            },
            "final_status": VerificationStatus.INTERRUPTED.value,
            "authoritative": False,
            "requested_at": run.requested_at,
            "completed_at": completed_at,
        }
        self.store.finalize_verification_run(
            run.run_id,
            expected_run_version=run.version,
            status=VerificationStatus.INTERRUPTED,
            authoritative=False,
            head_after=head_after,
            clean_after=clean_after,
            workspace_after=workspace_after,
            completed_at=completed_at,
            evidence=evidence,
            evidence_hash=canonical_digest(evidence),
            error_code="VERIFICATION_PROCESS_INTERRUPTED",
            task_terminal_status=TaskStatus.BLOCKED,
            blocker=(
                "A prior Core process ended before verification completed; "
                "the claim was sealed as non-authoritative"
            ),
            actor="nero-verification-recovery",
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds")

    @staticmethod
    def _normalized_path(value: str | Path) -> str:
        return os.path.normcase(os.path.abspath(os.fspath(value)))

    @classmethod
    def _head_for_state(cls, state: GitState) -> str | None:
        target = cls._normalized_path(state.worktree)
        for entry in state.worktrees:
            worktree = entry.get("worktree")
            if worktree and cls._normalized_path(worktree) == target:
                head = entry.get("HEAD")
                return str(head) if head else None
        return None

    @classmethod
    def _workspace_snapshot(cls, state: GitState) -> dict[str, Any]:
        return {
            "repository_key": state.common_directory,
            "repository": state.repository,
            "worktree": state.worktree,
            "branch": state.branch,
            "head": cls._head_for_state(state),
            "clean": state.clean,
            "conflict_count": state.conflict_count,
            "detached_head": state.detached_head,
        }

    @classmethod
    def _require_bound_workspace(cls, task: Task, state: GitState) -> None:
        if not state.inspection_ok or state.errors:
            raise ScheduleError(
                "verification rejected because required Git state could not be measured safely"
            )
        if state.detached_head:
            raise ScheduleError("verification rejected on detached HEAD")
        if task.branch != state.branch:
            raise ScheduleError("verification branch binding changed")
        if not task.worktree or cls._normalized_path(task.worktree) != cls._normalized_path(
            state.worktree
        ):
            raise ScheduleError("verification worktree binding changed")
        if state.conflict_count:
            raise ScheduleError("verification rejected with unresolved conflicts")
        if not state.clean:
            raise ScheduleError("verification requires a clean worktree snapshot")
        if cls._head_for_state(state) is None:
            raise ScheduleError("verification requires an exact Git HEAD binding")

    @classmethod
    def _workspace_changed(cls, before: GitState, after: GitState) -> bool:
        return bool(
            before.common_directory != after.common_directory
            or cls._normalized_path(before.repository)
            != cls._normalized_path(after.repository)
            or cls._normalized_path(before.worktree)
            != cls._normalized_path(after.worktree)
            or before.branch != after.branch
            or cls._head_for_state(before) != cls._head_for_state(after)
            or not before.clean
            or not after.clean
            or before.conflict_count
            or after.conflict_count
            or after.detached_head
            or not after.inspection_ok
            or bool(after.errors)
        )

    @staticmethod
    def _lease_matches(task: Task, state: GitState, lease: Lease | None) -> bool:
        if not task.write_required:
            return lease is None
        return bool(
            lease is not None
            and lease.repository_key == state.common_directory
            and lease.task_id == task.task_id
            and lease.lease_id
            and lease.fencing_token > 0
        )

    @classmethod
    def _require_bound_lease(
        cls, task: Task, state: GitState, lease: Lease | None
    ) -> None:
        if not cls._lease_matches(task, state, lease):
            raise ScheduleError(
                "verification lease is not bound to this task and repository"
            )

    @staticmethod
    def _verification_blocker(
        status: VerificationStatus,
        error_code: str | None,
        missing_capabilities: tuple[str, ...],
        drift: list[str],
    ) -> str:
        if status is VerificationStatus.BACKEND_UNAVAILABLE:
            return (
                "approved isolated verification backend unavailable; "
                "no authoritative result was accepted"
            )
        if drift:
            return "verification invalidated by bound state drift: " + ", ".join(
                sorted(set(drift))
            )
        if missing_capabilities:
            return "verification backend is not authoritative for this profile"
        if status is VerificationStatus.TIMED_OUT:
            return "Core verification timed out"
        if status is VerificationStatus.FAILED:
            return "Core verification checks failed"
        return f"Core verification did not pass ({error_code or status.value})"

    @staticmethod
    def _attention_item(event: Event) -> AttentionItem | None:
        payload = event.payload
        if event.event_type == "approval.requested":
            return AttentionItem(
                sequence=event.sequence,
                event_id=event.event_id,
                event_hash=event.event_hash,
                kind="approval",
                status="pending",
                title="Approval requested",
                summary=str(payload.get("summary") or payload.get("action") or "Review required"),
                requires_action=True,
                task_id=event.task_id,
                verification_run_id=None,
                created_at=event.created_at,
            )
        if event.event_type == "approval.decided":
            return AttentionItem(
                sequence=event.sequence,
                event_id=event.event_id,
                event_hash=event.event_hash,
                kind="approval",
                status=str(payload.get("status") or "decided"),
                title="Approval decided",
                summary=str(payload.get("action") or "Decision recorded"),
                requires_action=False,
                task_id=event.task_id,
                verification_run_id=None,
                created_at=event.created_at,
            )
        if event.event_type == "verification.recorded":
            status = str(payload.get("status") or "recorded")
            return AttentionItem(
                sequence=event.sequence,
                event_id=event.event_id,
                event_hash=event.event_hash,
                kind="verification",
                status=status,
                title=f"Core verification {status.replace('_', ' ')}",
                summary=(
                    "Authoritative completion evidence recorded."
                    if payload.get("authoritative")
                    else "Verification evidence recorded; completion was not authorized."
                ),
                requires_action=not bool(payload.get("authoritative")),
                task_id=event.task_id,
                verification_run_id=(
                    str(payload["run_id"]) if payload.get("run_id") else None
                ),
                created_at=event.created_at,
            )
        if event.event_type == "task.transitioned":
            status = str(payload.get("to") or "")
            if status not in {
                TaskStatus.COMPLETE.value,
                TaskStatus.BLOCKED.value,
                TaskStatus.FAILED.value,
            }:
                return None
            return AttentionItem(
                sequence=event.sequence,
                event_id=event.event_id,
                event_hash=event.event_hash,
                kind="milestone",
                status=status,
                title=f"Task {status}",
                summary=str(payload.get("blocker") or "Task state changed."),
                requires_action=status in {
                    TaskStatus.BLOCKED.value,
                    TaskStatus.FAILED.value,
                },
                task_id=event.task_id,
                verification_run_id=None,
                created_at=event.created_at,
            )
        return None

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
    "VerificationPolicyError",
    "canonical_core_db",
]
