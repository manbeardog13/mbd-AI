"""HTTP contract tests for the manually launched Mission Control shell."""
from __future__ import annotations

import subprocess
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from mission_control import create_app


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=check,
    )


class MissionControlApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "repo"
        subprocess.run(
            ["git", "init", "--bare", "--initial-branch=main", str(self.remote)],
            cwd=self.root,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "init", "--initial-branch=main", str(self.repo)],
            cwd=self.root,
            capture_output=True,
            check=True,
        )
        git(self.repo, "config", "user.name", "Nero API Test")
        git(self.repo, "config", "user.email", "nero-api@example.invalid")
        (self.repo / "state.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "state.txt")
        git(self.repo, "commit", "-m", "base")
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-u", "origin", "main")
        self.app = create_app(self.repo, self.root / "mission-control.db")
        self.client_context = TestClient(
            self.app,
            base_url="http://127.0.0.1",
            headers={"X-Nero-Local": "1"},
        )
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temp.cleanup()

    def test_shell_health_and_policy_are_explicit(self) -> None:
        shell = self.client.get("/")
        self.assertEqual(shell.status_code, 200)
        self.assertIn("Nero Mission Control", shell.text)
        self.assertEqual(self.client.get("/assets/app.css").status_code, 200)
        self.assertEqual(self.client.get("/assets/app.js").status_code, 200)

        health = self.client.get("/api/mc/health").json()
        self.assertTrue(health["internal_state_ok"])
        self.assertTrue(health["repository_inspection_ok"])
        self.assertNotIn("ok", health)
        self.assertEqual(health["remote_mutation_capabilities"], [])
        policy = self.client.get("/api/mc/policy").json()
        self.assertEqual(policy["authority"], "Nero Core")
        self.assertEqual(policy["workers"], ["claude", "codex"])
        self.assertFalse(policy["remote_mutations_enabled"])
        self.assertFalse(policy["host_presence_autostart"])

    def test_git_relationship_is_withheld_until_explicit_refresh(self) -> None:
        before = self.client.get("/api/mc/git")
        self.assertEqual(before.status_code, 200)
        self.assertFalse(before.json()["remote_state_fresh"])
        self.assertIsNone(before.json()["ahead"])
        self.assertIsNone(before.json()["behind"])
        self.assertIn("until a successful fresh fetch", before.json()["relationship"])

        after = self.client.post("/api/mc/git/refresh")
        self.assertEqual(after.status_code, 200)
        state = after.json()
        self.assertTrue(state["remote_state_fresh"])
        self.assertEqual((state["ahead"], state["behind"]), (0, 0))
        self.assertEqual(
            state["relationship"],
            "Local branch main is 0 commits ahead and 0 commits behind upstream branch origin/main.",
        )
        event_types = [
            event["event_type"]
            for event in self.client.get("/api/mc/events?event_type=git.fetch.completed").json()["events"]
        ]
        self.assertEqual(event_types, ["git.fetch.completed"])

    def test_task_worker_and_timeline_contract(self) -> None:
        profile_id = self.client.get("/api/mc/verification/profiles").json()[
            "profiles"
        ][0]["profile_id"]
        queued = self.client.post(
            "/api/mc/tasks",
            json={
                "objective": "Inspect the repository",
                "acceptance_criteria": ["return measured evidence"],
                "write_required": False,
                "verification_profile_id": profile_id,
            },
        )
        self.assertEqual(queued.status_code, 201)
        task_id = queued.json()["task"]["task_id"]

        assignment = self.client.post(
            f"/api/mc/tasks/{task_id}/assign",
            json={
                "adapter_id": "codex",
                "expected_version": queued.json()["task"]["version"],
                "bounded_context": {"scope": "tests"},
            },
        )
        self.assertEqual(assignment.status_code, 200)
        packet = assignment.json()["assignment"]["packet"]
        self.assertEqual(packet["provider"], "OpenAI")
        self.assertFalse(packet["write_allowed"])
        workers = self.client.get("/api/mc/workers").json()["workers"]
        codex = next(worker for worker in workers if worker["adapter_id"] == "codex")
        self.assertEqual(codex["assigned_task"], task_id)

        version = assignment.json()["assignment"]["task"]["version"]
        for status in ("running", "verifying"):
            payload: dict[str, object] = {
                "status": status,
                "expected_version": version,
            }
            if status == "verifying":
                payload["result"] = {
                    "summary": "Measured evidence returned",
                    "tests_run": ["API fixture verified"],
                }
            response = self.client.post(
                f"/api/mc/tasks/{task_id}/transition", json=payload
            )
            self.assertEqual(response.status_code, 200)
            version = response.json()["task"]["version"]
        manual = self.client.post(
            f"/api/mc/tasks/{task_id}/transition",
            json={
                "status": "complete",
                "expected_version": version,
                "result": {
                    "summary": "manual claim",
                    "tests_run": ["manual claim"],
                },
            },
        )
        self.assertEqual(manual.status_code, 409)
        verified = self.client.post(
            f"/api/mc/tasks/{task_id}/verify",
            json={"expected_version": version},
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["run"]["status"], "backend_unavailable")
        self.assertFalse(verified.json()["run"]["authoritative"])
        events = self.client.get(f"/api/mc/events?task_id={task_id}").json()["events"]
        self.assertGreaterEqual(len(events), 5)
        self.assertTrue(all(event["task_id"] == task_id for event in events))

    def test_remote_approval_never_creates_a_remote_mutation(self) -> None:
        before = subprocess.run(
            ["git", "--git-dir", str(self.remote), "rev-parse", "refs/heads/main"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        requested = self.client.post(
            "/api/mc/approvals",
            json={
                "action": "git.push",
                "summary": "Evidence-only approval for origin/main",
                "risk": "high",
            },
        )
        self.assertEqual(requested.status_code, 201)
        self.assertFalse(requested.json()["executed"])
        approval_id = requested.json()["approval"]["approval_id"]
        decided = self.client.post(
            f"/api/mc/approvals/{approval_id}/decision",
            json={"approved": True, "note": "M1 evidence only"},
        )
        self.assertEqual(decided.status_code, 200)
        self.assertFalse(decided.json()["executed"])

        after = subprocess.run(
            ["git", "--git-dir", str(self.remote), "rev-parse", "refs/heads/main"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(before, after)
        self.assertEqual(self.client.post("/api/mc/git/push").status_code, 404)
        self.assertEqual(self.client.post("/api/mc/git/commit").status_code, 404)
        events = self.client.get(
            "/api/mc/events?event_type=remote_mutation.not_executed"
        ).json()["events"]
        self.assertEqual(events[0]["payload"]["action"], "git.push")

    def test_invalid_transitions_fail_closed(self) -> None:
        missing = self.client.post(
            "/api/mc/tasks/not-a-task/assign",
            json={"adapter_id": "codex", "expected_version": 0},
        )
        self.assertEqual(missing.status_code, 409)
        invalid = self.client.post(
            "/api/mc/tasks",
            json={"objective": "", "priority": 101, "write_required": False},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_stale_task_version_fails_closed_and_is_journaled(self) -> None:
        queued = self.client.post(
            "/api/mc/tasks",
            json={"objective": "Versioned task", "write_required": False},
        ).json()["task"]
        first = self.client.post(
            f"/api/mc/tasks/{queued['task_id']}/assign",
            json={"adapter_id": "codex", "expected_version": queued["version"]},
        )
        self.assertEqual(first.status_code, 200)
        stale = self.client.post(
            f"/api/mc/tasks/{queued['task_id']}/assign",
            json={"adapter_id": "claude", "expected_version": queued["version"]},
        )
        self.assertEqual(stale.status_code, 409)
        events = self.client.get(
            f"/api/mc/events?event_type=worker.assignment.denied&task_id={queued['task_id']}"
        ).json()["events"]
        self.assertEqual(events[0]["payload"]["reason"], "state_conflict")

    def test_safe_mode_blocks_mutating_http_routes(self) -> None:
        core = self.app.state.nero_core
        self.client.post("/api/mc/git/refresh")
        queued = self.client.post(
            "/api/mc/tasks",
            json={"objective": "lease guard", "write_required": True},
        ).json()["task"]
        assigned = self.client.post(
            f"/api/mc/tasks/{queued['task_id']}/assign",
            json={"adapter_id": "codex", "expected_version": queued["version"]},
        ).json()["assignment"]
        registry_path = core.lease_registry.database_path(
            core.git.inspect(self.repo).common_directory
        )
        with closing(sqlite3.connect(registry_path)) as conn:
            lease_before = conn.execute(
                "SELECT heartbeat_at, expires_at FROM repository_write_lease"
            ).fetchone()
            history_before = conn.execute(
                "SELECT COUNT(*) FROM lease_history"
            ).fetchone()[0]
        with closing(sqlite3.connect(core.store.db_path)) as conn:
            conn.execute("DROP TRIGGER core_events_no_update")
            conn.execute("UPDATE core_events SET event_hash='tampered' WHERE sequence=1")
            conn.commit()
        health = self.client.get("/api/mc/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["mode"], "safe_mode")
        task = self.client.post(
            "/api/mc/tasks",
            json={"objective": "must not queue", "write_required": False},
        )
        self.assertEqual(task.status_code, 503)
        refresh = self.client.post("/api/mc/git/refresh")
        self.assertEqual(refresh.status_code, 503)
        heartbeat = self.client.post(
            f"/api/mc/tasks/{queued['task_id']}/lease/heartbeat",
            json={"expected_version": assigned["task"]["version"]},
        )
        self.assertEqual(heartbeat.status_code, 503)
        with closing(sqlite3.connect(registry_path)) as conn:
            lease_after = conn.execute(
                "SELECT heartbeat_at, expires_at FROM repository_write_lease"
            ).fetchone()
            history_after = conn.execute(
                "SELECT COUNT(*) FROM lease_history"
            ).fetchone()[0]
        self.assertEqual(lease_after, lease_before)
        self.assertEqual(history_after, history_before)


if __name__ == "__main__":
    unittest.main()
