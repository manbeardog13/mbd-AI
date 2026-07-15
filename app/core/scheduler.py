"""Deterministic manual scheduler with a repository-global write lease."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .adapters import ManualWorkerAdapter
from .contracts import AgentResult, GitState, Lease, Task, TaskPacket, TaskStatus
from .git_service import GitService
from .store import CoreStore, StoreError


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
        TaskStatus.COMPLETE,
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


class Scheduler:
    def __init__(
        self,
        store: CoreStore,
        git: GitService,
        adapters: Mapping[str, ManualWorkerAdapter],
        *,
        lease_ttl_seconds: int = 120,
    ) -> None:
        self.store = store
        self.git = git
        self.adapters = dict(adapters)
        self.lease_ttl_seconds = lease_ttl_seconds
        self._lease_tokens: dict[str, tuple[str, str]] = {}

    def assign(
        self,
        task_id: str,
        adapter_id: str,
        *,
        bounded_context: Mapping[str, Any] | None = None,
    ) -> Assignment:
        task = self.store.get_task(task_id)
        if task is None:
            raise ScheduleError(f"unknown task: {task_id}")
        if task.status is not TaskStatus.QUEUED:
            raise ScheduleError(f"task {task_id} is {task.status.value}, not queued")
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
                task_id, TaskStatus.BLOCKED, blocker=blocker, actor="nero-scheduler"
            )
            raise ScheduleError(blocker)

        initial = self.git.inspect(task.repository, last_fetch_at=None)
        last_fetch = self.store.get_meta(self._fetch_key(initial.common_directory))
        state = self.git.inspect(task.repository, last_fetch_at=last_fetch)
        lease: Lease | None = None
        lease_owner: str | None = None
        token: str | None = None
        if task.write_required:
            blocker = self._write_blocker(state)
            if blocker:
                self.store.transition_task(
                    task_id, TaskStatus.BLOCKED, blocker=blocker, actor="nero-scheduler"
                )
                raise ScheduleError(blocker)
            lease_owner = f"{adapter_id}:{task_id}"
            grant = self.store.acquire_lease(
                state.common_directory,
                owner=lease_owner,
                task_id=task_id,
                ttl_seconds=self.lease_ttl_seconds,
                actor="nero-scheduler",
            )
            if grant is None:
                active = self.store.current_lease(state.common_directory)
                blocker = (
                    f"repository write lease is held by {active.owner} until "
                    f"{active.expires_at}"
                    if active
                    else "repository write lease acquisition failed"
                )
                self.store.transition_task(
                    task_id, TaskStatus.BLOCKED, blocker=blocker, actor="nero-scheduler"
                )
                raise ScheduleError(blocker)
            lease = grant.lease
            token = grant.token
            state = replace(state, active_write_lease=lease.as_dict())

        try:
            assigned = self.store.assign_task(
                task_id,
                adapter_id=adapter_id,
                branch=state.branch,
                worktree=state.worktree,
                actor="nero-scheduler",
            )
            context = {
                "git_relationship": state.relationship,
                "remote_state_fresh": state.remote_state_fresh,
                "clean": state.clean,
                "remote_writes_allowed": False,
                **dict(bounded_context or {}),
            }
            packet = adapter.prepare_packet(
                assigned, lease_owner=lease_owner, bounded_context=context
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
                    "remote_writes_allowed": False,
                    "bounded_context_keys": sorted(packet.bounded_context),
                },
            )
            if token:
                self._lease_tokens[task_id] = (state.common_directory, token)
            return Assignment(assigned, packet, state, lease)
        except Exception as exc:
            if token:
                self.store.release_lease(
                    state.common_directory, token, actor="nero-scheduler"
                )
            current = self.store.get_task(task_id)
            if current and current.status is TaskStatus.PREPARING:
                self.store.transition_task(
                    task_id,
                    TaskStatus.FAILED,
                    blocker=f"packet preparation failed: {exc}",
                    actor="nero-scheduler",
                )
            raise

    def transition(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        blocker: str | None = None,
        result_payload: Mapping[str, Any] | None = None,
    ) -> Task:
        task = self.store.get_task(task_id)
        if task is None:
            raise ScheduleError(f"unknown task: {task_id}")
        if status not in ALLOWED_TRANSITIONS[task.status]:
            raise ScheduleError(
                f"invalid task transition: {task.status.value} -> {status.value}"
            )
        result: AgentResult | None = None
        if result_payload is not None:
            if not task.assigned_adapter:
                raise ScheduleError("task has no assigned adapter for result normalization")
            adapter = self.adapters.get(task.assigned_adapter)
            if adapter is None:
                raise ScheduleError("assigned adapter is unavailable")
            result = adapter.normalize_result(result_payload)
        transitioned = self.store.transition_task(
            task_id,
            status,
            blocker=blocker,
            result=result,
            actor="nero-scheduler",
        )
        if task.write_required and status in {
            TaskStatus.COMPLETE,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            self._release_known_lease(task_id)
        return transitioned

    def retry(self, task_id: str) -> Task:
        task = self.store.get_task(task_id)
        if task is None:
            raise ScheduleError(f"unknown task: {task_id}")
        if task.status not in {TaskStatus.FAILED, TaskStatus.BLOCKED, TaskStatus.PAUSED}:
            raise ScheduleError("only failed, blocked, or paused tasks can be retried")
        return self.store.transition_task(
            task_id, TaskStatus.QUEUED, blocker=None, actor="nero-scheduler"
        )

    def _release_known_lease(self, task_id: str) -> None:
        known = self._lease_tokens.pop(task_id, None)
        if known is None:
            self.store.record_event(
                "lease.release_deferred",
                actor="nero-scheduler",
                task_id=task_id,
                payload={
                    "reason": "lease token unavailable after restart; expiry is authoritative"
                },
            )
            return
        repository_key, token = known
        self.store.release_lease(repository_key, token, actor="nero-scheduler")

    @staticmethod
    def _write_blocker(state: GitState) -> str | None:
        if not state.remote_state_fresh:
            return "write task blocked until a successful fresh fetch"
        if state.detached_head:
            return "write task blocked on detached HEAD"
        if not state.upstream:
            return "write task blocked because the local branch has no upstream"
        if state.conflict_count:
            return f"write task blocked by {state.conflict_count} unresolved conflict(s)"
        if not state.clean:
            return "write task blocked because the worktree is dirty"
        if state.behind:
            return (
                f"write task blocked because {state.branch} is {state.behind} commits "
                f"behind {state.upstream}"
            )
        return None

    @staticmethod
    def _fetch_key(common_directory: str) -> str:
        return f"git.last_fetch:{str(Path(common_directory).resolve()).casefold()}"


def fetch_metadata_key(common_directory: str) -> str:
    return Scheduler._fetch_key(common_directory)
