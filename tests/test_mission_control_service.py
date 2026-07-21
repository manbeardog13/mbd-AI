"""End-to-end offline orchestration tests for Mission Control M1."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.contracts import RiskLevel, TaskStatus, WorkerStatus
from app.core.git_service import GitService
from app.core.lease_registry import RepositoryLeaseRegistry
from app.core.scheduler import ScheduleError
from app.core.service import MissionControlService
from app.core.store import SafeModeError


NOW = "2026-07-15T12:00:00+00:00"


def git(cwd: Path, *args: str, check: bool = True):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


class MissionControlServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "repo"
        self.other = self.root / "other"
        subprocess.run(
            ["git", "init", "--bare", "--initial-branch=main", str(self.remote)],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "init", "--initial-branch=main", str(self.repo)],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        git(self.repo, "config", "user.name", "Nero Test")
        git(self.repo, "config", "user.email", "nero-test@example.invalid")
        (self.repo / "state.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "state.txt")
        git(self.repo, "commit", "-m", "base")
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-u", "origin", "main")
        subprocess.run(
            ["git", "clone", str(self.remote), str(self.other)],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        git(self.other, "config", "user.name", "Nero Test")
        git(self.other, "config", "user.email", "nero-test@example.invalid")
        self.db = self.root / "core.db"
        self.core = MissionControlService(
            self.repo,
            self.db,
            git=GitService(clock=lambda: NOW, freshness_seconds=300),
            lease_ttl_seconds=300,
        )
        self.core.initialize()
        self.core.git_state(refresh_remote=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def transition(self, task, status, result=None):
        return self.core.transition_task(
            task.task_id,
            status,
            expected_version=task.version,
            result=result,
        )

    def test_read_only_task_packet_and_verified_state_machine(self) -> None:
        task = self.core.queue_task(
            objective="Inspect branch relationship",
            acceptance_criteria=("name local and upstream branches",),
        )
        assignment = self.core.assign_task(
            task.task_id, "codex", expected_version=task.version
        )
        self.assertIsNone(assignment.lease)
        self.assertFalse(assignment.packet.write_allowed)
        self.assertEqual(assignment.packet.provider, "OpenAI")
        self.assertEqual(self.core.workers()[1].status, WorkerStatus.PREPARING)
        running = self.transition(assignment.task, TaskStatus.RUNNING)
        verifying = self.transition(running, TaskStatus.VERIFYING)
        completed = self.transition(
            verifying,
            TaskStatus.COMPLETE,
            result={
                "summary": "relationship verified",
                "tests_run": ["real temporary Git fixture"],
            },
        )
        self.assertEqual(completed.last_result.summary, "relationship verified")
        self.assertTrue(self.core.health()["ok"])
        self.assertEqual(
            len(
                self.core.events(
                    event_type="task.verification.completed",
                    task_id=task.task_id,
                )
            ),
            1,
        )

    def test_running_task_cannot_complete_directly_and_lease_stays_held(self) -> None:
        first = self.core.queue_task(objective="First local write", write_required=True)
        second = self.core.queue_task(
            objective="Second local write", write_required=True
        )
        assignment = self.core.assign_task(
            first.task_id, "claude", expected_version=first.version
        )
        running = self.transition(assignment.task, TaskStatus.RUNNING)
        with self.assertRaisesRegex(ScheduleError, "invalid task transition"):
            self.core.transition_task(
                running.task_id,
                TaskStatus.COMPLETE,
                expected_version=running.version,
                result={"summary": "not verified", "tests_run": ["none"]},
            )
        self.assertEqual(
            self.core.store.get_task(running.task_id).status, TaskStatus.RUNNING
        )
        with self.assertRaisesRegex(ScheduleError, "write lease is held"):
            self.core.assign_task(
                second.task_id, "codex", expected_version=second.version
            )
        denied = self.core.events(
            event_type="task.transition.denied", task_id=running.task_id
        )
        self.assertEqual(denied[0].payload["reason"], "state_conflict")

    def test_verified_completion_releases_lease_for_handoff(self) -> None:
        first = self.core.queue_task(objective="First write", write_required=True)
        second = self.core.queue_task(objective="Second write", write_required=True)
        assignment = self.core.assign_task(
            first.task_id, "claude", expected_version=first.version
        )
        running = self.transition(assignment.task, TaskStatus.RUNNING)
        verifying = self.transition(running, TaskStatus.VERIFYING)
        completed = self.transition(
            verifying,
            TaskStatus.COMPLETE,
            result={"summary": "verified", "tests_run": ["unit suite"]},
        )
        self.assertEqual(completed.status, TaskStatus.COMPLETE)
        second_assignment = self.core.assign_task(
            second.task_id, "codex", expected_version=second.version
        )
        self.assertIsNotNone(second_assignment.lease)
        self.assertGreater(
            second_assignment.lease.fencing_token,
            assignment.lease.fencing_token,
        )

    def test_dirty_write_task_fails_closed_and_is_journaled(self) -> None:
        task = self.core.queue_task(
            objective="Write on a dirty tree", write_required=True
        )
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(ScheduleError, "worktree is dirty"):
            self.core.assign_task(
                task.task_id, "codex", expected_version=task.version
            )
        blocked = self.core.store.get_task(task.task_id)
        self.assertEqual(blocked.status, TaskStatus.BLOCKED)
        event_types = [
            event.event_type for event in self.core.events(task_id=task.task_id)
        ]
        self.assertIn("task.transitioned", event_types)
        self.assertIn("worker.assignment.denied", event_types)

    def test_behind_write_task_fails_closed(self) -> None:
        task = self.core.queue_task(objective="Write while behind", write_required=True)
        (self.other / "state.txt").write_text("remote\n", encoding="utf-8")
        git(self.other, "add", "state.txt")
        git(self.other, "commit", "-m", "remote")
        git(self.other, "push", "origin", "main")
        state = self.core.git_state(refresh_remote=True)
        self.assertEqual(state.behind, 1)
        with self.assertRaisesRegex(ScheduleError, "1 commits behind"):
            self.core.assign_task(
                task.task_id, "claude", expected_version=task.version
            )

    def test_dependency_blocks_until_complete(self) -> None:
        prerequisite = self.core.queue_task(objective="Prerequisite")
        dependent = self.core.queue_task(
            objective="Dependent", dependencies=(prerequisite.task_id,)
        )
        with self.assertRaisesRegex(ScheduleError, "incomplete dependencies"):
            self.core.assign_task(
                dependent.task_id, "codex", expected_version=dependent.version
            )

    def test_reserved_or_secret_context_never_claims_task_or_lease(self) -> None:
        task = self.core.queue_task(objective="Protected", write_required=True)
        for context in (
            {"Remote-Writes-Allowed": True},
            {"nested": [{"api_token": "do-not-echo"}]},
        ):
            with self.assertRaises((ScheduleError, ValueError)):
                self.core.assign_task(
                    task.task_id,
                    "codex",
                    expected_version=task.version,
                    bounded_context=context,
                )
            current = self.core.store.get_task(task.task_id)
            self.assertEqual(current.status, TaskStatus.QUEUED)
            self.assertIsNone(
                self.core.lease_registry.observe(
                    self.core.git.inspect(self.repo).common_directory
                ).active
            )

    def test_remote_approval_is_visible_but_never_executes(self) -> None:
        before = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        approval = self.core.request_approval(
            action="git.push",
            summary="Would push main to origin/main",
            risk=RiskLevel.HIGH,
        )
        self.core.decide_approval(
            approval.approval_id, approved=True, note="M1 evidence only"
        )
        after = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(before, after)
        self.assertEqual(self.core.health()["remote_mutation_capabilities"], [])
        event = self.core.events(event_type="remote_mutation.not_executed")[0]
        self.assertEqual(event.payload["action"], "git.push")

    def test_fetch_receipt_authentication_survives_restart(self) -> None:
        restarted = MissionControlService(
            self.repo,
            self.db,
            git=GitService(clock=lambda: NOW, freshness_seconds=300),
        )
        restarted.initialize()
        state = restarted.git_state(refresh_remote=False)
        self.assertTrue(state.remote_state_fresh)
        self.assertEqual(state.authentication, "fetch_authenticated")

    def test_second_core_observer_does_not_revoke_live_writer(self) -> None:
        task = self.core.queue_task(objective="Live writer", write_required=True)
        assignment = self.core.assign_task(
            task.task_id, "codex", expected_version=task.version
        )
        observer = MissionControlService(
            self.repo,
            self.db,
            git=GitService(clock=lambda: NOW, freshness_seconds=300),
            lease_ttl_seconds=300,
        )
        observer.initialize()

        observed = next(
            item for item in observer.tasks() if item.task_id == task.task_id
        )
        self.assertEqual(observed.status, TaskStatus.PREPARING)
        self.assertEqual(observer.overview()["active_step"], "preparing")
        renewed = self.core.heartbeat_task_lease(
            task.task_id, expected_version=assignment.task.version
        )
        self.assertEqual(renewed.lease_id, assignment.lease.lease_id)
        self.assertEqual(
            self.core.store.get_task(task.task_id).status, TaskStatus.PREPARING
        )

    def test_failed_fetch_overwrites_success_receipt(self) -> None:
        git(
            self.repo,
            "remote",
            "set-url",
            "origin",
            str(self.root / "missing.git"),
        )
        failed = self.core.git_state(refresh_remote=True)
        self.assertFalse(failed.remote_state_fresh)
        later = self.core.git_state(refresh_remote=False)
        self.assertFalse(later.remote_state_fresh)
        self.assertIsNone(later.ahead)
        self.assertEqual(later.authentication, "remote_unavailable")

    def test_expired_active_task_is_blocked_before_handoff(self) -> None:
        clock = MutableClock()
        core = MissionControlService(
            self.repo,
            self.root / "expiry.db",
            git=GitService(clock=lambda: NOW, freshness_seconds=300),
            lease_registry=RepositoryLeaseRegistry(clock=clock),
            lease_ttl_seconds=5,
        )
        core.initialize()
        core.git_state(refresh_remote=True)
        first = core.queue_task(objective="Expiring write", write_required=True)
        assignment = core.assign_task(
            first.task_id, "codex", expected_version=first.version
        )
        running = core.transition_task(
            first.task_id,
            TaskStatus.RUNNING,
            expected_version=assignment.task.version,
        )
        clock.value += timedelta(seconds=6)
        tasks = core.tasks()
        expired = next(task for task in tasks if task.task_id == running.task_id)
        self.assertEqual(expired.status, TaskStatus.BLOCKED)
        second = core.queue_task(objective="Successor", write_required=True)
        successor = core.assign_task(
            second.task_id, "claude", expected_version=second.version
        )
        self.assertGreater(
            successor.lease.fencing_token, assignment.lease.fencing_token
        )

    def test_two_worktrees_and_two_state_databases_share_one_writer(self) -> None:
        extra = self.root / "extra"
        git(self.repo, "worktree", "add", "-b", "extra", str(extra))
        git(extra, "branch", "--set-upstream-to=origin/main", "extra")
        other_core = MissionControlService(
            extra,
            self.root / "other-core.db",
            git=GitService(clock=lambda: NOW, freshness_seconds=300),
        )
        other_core.initialize()
        other_core.git_state(refresh_remote=True)
        first = self.core.queue_task(objective="Main writer", write_required=True)
        second = other_core.queue_task(objective="Extra writer", write_required=True)
        assigned = self.core.assign_task(
            first.task_id, "codex", expected_version=first.version
        )
        self.assertIsNotNone(assigned.lease)
        with self.assertRaisesRegex(ScheduleError, "write lease is held"):
            other_core.assign_task(
                second.task_id, "claude", expected_version=second.version
            )
        main_common = self.core.git.inspect(self.repo).common_directory
        extra_common = other_core.git.inspect(extra).common_directory
        self.assertEqual(main_common, extra_common)
        self.assertNotEqual(self.core.store.db_path, other_core.store.db_path)

    def test_event_chain_failure_enforces_service_safe_mode(self) -> None:
        with closing(sqlite3.connect(self.core.store.db_path)) as conn:
            conn.execute("DROP TRIGGER core_events_no_update")
            conn.execute("UPDATE core_events SET event_hash='tampered' WHERE sequence=1")
            conn.commit()
        health = self.core.health()
        self.assertFalse(health["ok"])
        self.assertEqual(health["mode"], "safe_mode")
        self.assertIsNotNone(self.core.git_state(refresh_remote=False).branch)
        with self.assertRaises(SafeModeError):
            self.core.queue_task(objective="must fail")
        with self.assertRaises(SafeModeError):
            self.core.git_state(refresh_remote=True)

    def test_safe_mode_rejects_heartbeat_before_registry_mutation(self) -> None:
        clock = MutableClock()
        core = MissionControlService(
            self.repo,
            self.root / "safe-heartbeat.db",
            git=GitService(clock=lambda: NOW, freshness_seconds=300),
            lease_registry=RepositoryLeaseRegistry(clock=clock),
            lease_ttl_seconds=60,
        )
        core.initialize()
        core.git_state(refresh_remote=True)
        task = core.queue_task(objective="Guarded heartbeat", write_required=True)
        assignment = core.assign_task(
            task.task_id, "codex", expected_version=task.version
        )
        registry_path = core.lease_registry.database_path(
            core.git.inspect(self.repo).common_directory
        )
        clock.value += timedelta(seconds=10)
        with closing(sqlite3.connect(registry_path)) as conn:
            before_row = conn.execute(
                "SELECT heartbeat_at, expires_at FROM repository_write_lease"
            ).fetchone()
            before_history = conn.execute(
                "SELECT COUNT(*) FROM lease_history"
            ).fetchone()[0]
        with closing(sqlite3.connect(core.store.db_path)) as conn:
            conn.execute("DROP TRIGGER core_events_no_update")
            conn.execute("UPDATE core_events SET event_hash='tampered' WHERE sequence=1")
            conn.commit()

        with self.assertRaises(SafeModeError):
            core.heartbeat_task_lease(
                task.task_id, expected_version=assignment.task.version
            )

        with closing(sqlite3.connect(registry_path)) as conn:
            after_row = conn.execute(
                "SELECT heartbeat_at, expires_at FROM repository_write_lease"
            ).fetchone()
            after_history = conn.execute(
                "SELECT COUNT(*) FROM lease_history"
            ).fetchone()[0]
        self.assertEqual(after_row, before_row)
        self.assertEqual(after_history, before_history)

    def test_overview_separates_audit_integrity_from_task_verification(self) -> None:
        overview = self.core.overview()
        self.assertEqual(overview["identity"], "Nero Core")
        self.assertEqual(overview["launch_mode"], "manual")
        self.assertFalse(overview["remote_mutations_enabled"])
        self.assertEqual(
            overview["verification"]["confidence"], "audit_integrity_verified"
        )


if __name__ == "__main__":
    unittest.main()
