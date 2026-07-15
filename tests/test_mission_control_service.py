"""End-to-end offline orchestration tests for Mission Control M1."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.contracts import RiskLevel, TaskStatus, WorkerStatus
from app.core.git_service import GitService
from app.core.scheduler import ScheduleError
from app.core.service import MissionControlService


NOW = "2026-07-15T12:00:00+00:00"


def git(cwd: Path, *args: str, check: bool = True):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


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
        for repo in (self.repo,):
            git(repo, "config", "user.name", "Nero Test")
            git(repo, "config", "user.email", "nero-test@example.invalid")
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
        self.core = MissionControlService(
            self.repo,
            self.root / "core.db",
            git=GitService(clock=lambda: NOW, freshness_seconds=300),
            lease_ttl_seconds=300,
        )
        self.core.initialize()
        self.core.git_state(refresh_remote=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_read_only_task_packet_and_state_machine(self) -> None:
        task = self.core.queue_task(
            objective="Inspect branch relationship",
            acceptance_criteria=("name local and upstream branches",),
        )
        assignment = self.core.assign_task(task.task_id, "codex")
        self.assertIsNone(assignment.lease)
        self.assertFalse(assignment.packet.write_allowed)
        self.assertEqual(assignment.packet.provider, "OpenAI")
        self.assertEqual(
            self.core.workers()[1].status,
            WorkerStatus.PREPARING,
        )
        self.core.transition_task(task.task_id, TaskStatus.RUNNING)
        self.core.transition_task(task.task_id, TaskStatus.VERIFYING)
        completed = self.core.transition_task(
            task.task_id,
            TaskStatus.COMPLETE,
            result={
                "summary": "relationship verified",
                "tests_run": ["git fixture"],
            },
        )
        self.assertEqual(completed.last_result.summary, "relationship verified")
        self.assertTrue(self.core.health()["ok"])

    def test_exactly_one_write_worker_then_handoff(self) -> None:
        first = self.core.queue_task(
            objective="First local write",
            write_required=True,
            acceptance_criteria=("lease held",),
        )
        second = self.core.queue_task(
            objective="Second local write",
            write_required=True,
            acceptance_criteria=("wait for lease",),
        )
        first_assignment = self.core.assign_task(first.task_id, "claude")
        self.assertIsNotNone(first_assignment.lease)
        self.assertTrue(first_assignment.packet.write_allowed)
        with self.assertRaisesRegex(ScheduleError, "write lease is held"):
            self.core.assign_task(second.task_id, "codex")
        self.assertEqual(
            self.core.store.get_task(second.task_id).status, TaskStatus.BLOCKED
        )

        self.core.transition_task(first.task_id, TaskStatus.RUNNING)
        self.core.transition_task(first.task_id, TaskStatus.COMPLETE)
        self.core.retry_task(second.task_id)
        second_assignment = self.core.assign_task(second.task_id, "codex")
        self.assertIsNotNone(second_assignment.lease)
        self.assertNotEqual(
            first_assignment.lease.owner, second_assignment.lease.owner
        )

    def test_dirty_write_task_fails_closed_and_is_journaled(self) -> None:
        task = self.core.queue_task(
            objective="Write on a dirty tree", write_required=True
        )
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaisesRegex(ScheduleError, "worktree is dirty"):
            self.core.assign_task(task.task_id, "codex")
        blocked = self.core.store.get_task(task.task_id)
        self.assertEqual(blocked.status, TaskStatus.BLOCKED)
        event_types = [event.event_type for event in self.core.events(task_id=task.task_id)]
        self.assertIn("task.transitioned", event_types)

    def test_behind_write_task_fails_closed(self) -> None:
        task = self.core.queue_task(
            objective="Write while behind", write_required=True
        )
        (self.other / "state.txt").write_text("remote\n", encoding="utf-8")
        git(self.other, "add", "state.txt")
        git(self.other, "commit", "-m", "remote")
        git(self.other, "push", "origin", "main")
        state = self.core.git_state(refresh_remote=True)
        self.assertEqual(state.behind, 1)
        with self.assertRaisesRegex(ScheduleError, "1 commits behind"):
            self.core.assign_task(task.task_id, "claude")

    def test_dependency_blocks_until_complete(self) -> None:
        prerequisite = self.core.queue_task(objective="Prerequisite")
        dependent = self.core.queue_task(
            objective="Dependent", dependencies=(prerequisite.task_id,)
        )
        with self.assertRaisesRegex(ScheduleError, "incomplete dependencies"):
            self.core.assign_task(dependent.task_id, "codex")

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

    def test_overview_exposes_operator_state(self) -> None:
        overview = self.core.overview()
        self.assertEqual(overview["identity"], "Nero Core")
        self.assertEqual(overview["launch_mode"], "manual")
        self.assertFalse(overview["remote_mutations_enabled"])
        self.assertEqual(overview["verification"]["confidence"], "verified")


if __name__ == "__main__":
    unittest.main()
