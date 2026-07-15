"""Hostile HTTP-contract tests for Mission Control M2 verification."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.core.contracts import RiskLevel
from mission_control import create_app


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=True,
    )


class MissionControlM2ApiTests(unittest.TestCase):
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
        git(self.repo, "config", "user.name", "Nero M2 API Test")
        git(self.repo, "config", "user.email", "nero-m2-api@example.invalid")
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

    def _queue_to_verifying(self) -> tuple[str, int]:
        catalog = self.client.get("/api/mc/verification/profiles").json()
        profile_id = catalog["profiles"][0]["profile_id"]
        queued = self.client.post(
            "/api/mc/tasks",
            json={
                "objective": "Exercise fixed verification API",
                "verification_profile_id": profile_id,
            },
        )
        self.assertEqual(queued.status_code, 201)
        task = queued.json()["task"]
        assigned = self.client.post(
            f"/api/mc/tasks/{task['task_id']}/assign",
            json={"adapter_id": "codex", "expected_version": task["version"]},
        )
        self.assertEqual(assigned.status_code, 200)
        task = assigned.json()["assignment"]["task"]
        for status in ("running", "verifying"):
            transitioned = self.client.post(
                f"/api/mc/tasks/{task['task_id']}/transition",
                json={
                    "status": status,
                    "expected_version": task["version"],
                    "result": (
                        {
                            "summary": "advisory worker report",
                            "tests_run": ["not trusted completion evidence"],
                        }
                        if status == "verifying"
                        else None
                    ),
                },
            )
            self.assertEqual(transitioned.status_code, 200)
            task = transitioned.json()["task"]
        return task["task_id"], task["version"]

    def test_request_models_reject_every_execution_selector(self) -> None:
        forbidden = {
            "command": "python",
            "args": ["-c", "print('owned')"],
            "env": {"TOKEN": "secret"},
            "executable": "cmd.exe",
            "path": "C:\\Windows\\System32",
            "backend": "fake",
        }
        for key, value in forbidden.items():
            with self.subTest(field=key):
                response = self.client.post(
                    "/api/mc/tasks/not-a-task/verify",
                    json={"expected_version": 0, key: value},
                )
                self.assertEqual(response.status_code, 422)

        task_create = self.client.post(
            "/api/mc/tasks",
            json={"objective": "must reject command", "command": "whoami"},
        )
        self.assertEqual(task_create.status_code, 422)
        policy = self.client.post(
            "/api/mc/tasks/not-a-task/verification-policy",
            json={"profile_id": "fixed", "expected_version": 0, "backend": "fake"},
        )
        self.assertEqual(policy.status_code, 422)

    def test_direct_complete_is_rejected_and_disabled_backend_cannot_pass(self) -> None:
        task_id, version = self._queue_to_verifying()
        manual = self.client.post(
            f"/api/mc/tasks/{task_id}/transition",
            json={
                "status": "complete",
                "expected_version": version,
                "result": {
                    "summary": "operator typed this",
                    "tests_run": ["operator typed this too"],
                },
            },
        )
        self.assertEqual(manual.status_code, 409)
        self.assertIn("Core verification", manual.json()["detail"])

        response = self.client.post(
            f"/api/mc/tasks/{task_id}/verify",
            json={"expected_version": version},
        )
        self.assertEqual(response.status_code, 200)
        run = response.json()["run"]
        self.assertEqual(run["status"], "backend_unavailable")
        self.assertFalse(run["authoritative"])
        self.assertEqual(run["error_code"], "VERIFICATION_BACKEND_DISABLED")
        self.assertEqual(
            self.client.get(f"/api/mc/verification/runs/{run['run_id']}").json()[
                "run"
            ]["evidence_hash"],
            run["evidence_hash"],
        )
        task = next(
            item
            for item in self.client.get("/api/mc/tasks").json()["tasks"]
            if item["task_id"] == task_id
        )
        self.assertEqual(task["status"], "blocked")
        self.assertIsNone(task["verified_run_id"])
        attention = self.client.get(
            "/api/mc/attention?after_sequence=0&limit=100"
        ).json()["items"]
        verification_item = next(
            item
            for item in attention
            if item["verification_run_id"] == run["run_id"]
        )
        self.assertEqual(verification_item["status"], "backend_unavailable")
        self.assertTrue(verification_item["requires_action"])

    def test_fake_runner_cannot_be_selected_by_environment(self) -> None:
        selector_names = {
            "NERO_VERIFICATION_RUNNER": "fake",
            "MISSION_CONTROL_VERIFICATION_RUNNER": "subprocess",
            "NERO_VERIFICATION_BACKEND": "docker",
        }
        with patch.dict(os.environ, selector_names, clear=False):
            app = create_app(self.repo, self.root / "environment-selector.db")
            with TestClient(
                app,
                base_url="http://127.0.0.1",
                headers={"X-Nero-Local": "1"},
            ) as client:
                catalog = client.get("/api/mc/verification/profiles").json()

        self.assertTrue(catalog["production_default"])
        self.assertFalse(catalog["execution_available"])
        self.assertEqual(catalog["backend"]["backend_id"], "nero.disabled.v1")
        self.assertFalse(catalog["backend"]["test_only"])

    def test_attention_cursor_is_monotonic_and_unknown_run_is_404(self) -> None:
        requested = self.client.post(
            "/api/mc/approvals",
            json={
                "action": "verification.backend.enable",
                "summary": "Review a future isolated backend",
                "risk": "high",
            },
        )
        self.assertEqual(requested.status_code, 201)
        first = self.client.get("/api/mc/attention?after_sequence=0&limit=100").json()
        self.assertGreaterEqual(first["pending_approval_count"], 1)
        self.assertTrue(first["items"])
        cursor = first["next_cursor"]
        second = self.client.get(
            f"/api/mc/attention?after_sequence={cursor}&limit=100"
        ).json()
        self.assertTrue(
            all(item["sequence"] > cursor for item in second["items"])
        )
        self.assertFalse(
            {item["event_id"] for item in first["items"]}
            & {item["event_id"] for item in second["items"]}
        )
        self.assertEqual(
            self.client.get("/api/mc/verification/runs/not-a-run").status_code,
            404,
        )

    def test_superseded_block_event_is_not_still_actionable(self) -> None:
        created = self.client.post(
            "/api/mc/tasks",
            json={"objective": "Resolve a temporary blocker"},
        ).json()["task"]
        assigned = self.client.post(
            f"/api/mc/tasks/{created['task_id']}/assign",
            json={"adapter_id": "codex", "expected_version": created["version"]},
        ).json()["assignment"]["task"]
        running = self.client.post(
            f"/api/mc/tasks/{created['task_id']}/transition",
            json={"status": "running", "expected_version": assigned["version"]},
        ).json()["task"]
        blocked = self.client.post(
            f"/api/mc/tasks/{created['task_id']}/transition",
            json={
                "status": "blocked",
                "expected_version": running["version"],
                "blocker": "temporary blocker",
            },
        ).json()["task"]

        while_blocked = self.client.get(
            "/api/mc/attention?after_sequence=0&limit=100"
        ).json()["items"]
        blocked_item = next(
            item
            for item in while_blocked
            if item["task_id"] == created["task_id"]
            and item["status"] == "blocked"
        )
        self.assertTrue(blocked_item["requires_action"])

        retried = self.client.post(
            f"/api/mc/tasks/{created['task_id']}/retry",
            json={"expected_version": blocked["version"]},
        )
        self.assertEqual(retried.status_code, 200)
        after_retry = self.client.get(
            "/api/mc/attention?after_sequence=0&limit=100"
        ).json()["items"]
        resolved_item = next(
            item
            for item in after_retry
            if item["event_id"] == blocked_item["event_id"]
        )
        self.assertFalse(resolved_item["requires_action"])

    def test_loopback_host_and_mutation_origin_boundary(self) -> None:
        evil_host = self.client.get(
            "/api/mc/health",
            headers={"Host": "evil.example"},
        )
        self.assertEqual(evil_host.status_code, 400)

        hostile_origin = self.client.post(
            "/api/mc/git/refresh",
            headers={
                "Host": "127.0.0.1:8765",
                "Origin": "http://evil.example",
                "X-Nero-Local": "1",
            },
        )
        self.assertEqual(hostile_origin.status_code, 403)

        cross_port_origin = self.client.post(
            "/api/mc/git/refresh",
            headers={
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:9999",
                "X-Nero-Local": "1",
            },
        )
        self.assertEqual(cross_port_origin.status_code, 403)

        missing_header = self.client.post(
            "/api/mc/git/refresh",
            headers={
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:8765",
                "X-Nero-Local": "",
            },
        )
        self.assertEqual(missing_header.status_code, 403)

        accepted = self.client.post(
            "/api/mc/git/refresh",
            headers={
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:8765",
                "X-Nero-Local": "1",
            },
        )
        self.assertEqual(accepted.status_code, 200)

    def test_external_api_discovery_is_disabled_and_get_routes_are_pure(self) -> None:
        self.assertEqual(self.client.get("/api/docs").status_code, 404)
        self.assertEqual(self.client.get("/openapi.json").status_code, 404)

        core = self.app.state.nero_core
        before_sequence = core.store.latest_event_sequence()
        with patch.object(
            core, "_reconcile_abandoned_verifications"
        ) as abandoned, patch.object(
            core.scheduler, "reconcile_write_leases"
        ) as leases:
            for path in (
                "/api/mc/overview",
                "/api/mc/tasks",
                "/api/mc/workers",
                "/api/mc/git",
            ):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)
            abandoned.assert_not_called()
            leases.assert_not_called()
            self.assertEqual(core.store.latest_event_sequence(), before_sequence)

            unprotected = self.client.post(
                "/api/mc/reconcile",
                headers={"X-Nero-Local": ""},
            )
            self.assertEqual(unprotected.status_code, 403)
            protected = self.client.post(
                "/api/mc/reconcile",
                headers={"Origin": "http://127.0.0.1"},
            )
            self.assertEqual(protected.status_code, 200)
            self.assertTrue(protected.json()["reconciliation_attempted"])
            self.assertTrue(protected.json()["internal_state_ok"])
            abandoned.assert_called_once_with()
            leases.assert_called_once_with()

    def test_attention_paginates_more_than_one_hundred_items_without_loss(self) -> None:
        core = self.app.state.nero_core
        for index in range(125):
            core.request_approval(
                action=f"fixture.review.{index}",
                summary=f"Actionable pagination fixture {index}",
                risk=RiskLevel.HIGH,
            )
        expected = {
            event.event_id
            for event in core.events(event_type="approval.requested", limit=1000)
        }
        self.assertEqual(len(expected), 125)

        cursor = 0
        collected: list[str] = []
        observed_sequences: list[int] = []
        current_sequence = None
        for _ in range(10):
            page = self.client.get(
                f"/api/mc/attention?after_sequence={cursor}&limit=37"
            )
            self.assertEqual(page.status_code, 200)
            feed = page.json()
            current_sequence = feed["current_sequence"]
            items = feed["items"]
            self.assertLessEqual(len(items), 37)
            self.assertTrue(all(item["sequence"] > cursor for item in items))
            collected.extend(item["event_id"] for item in items)
            observed_sequences.extend(item["sequence"] for item in items)
            next_cursor = feed["next_cursor"]
            self.assertGreater(next_cursor, cursor)
            cursor = next_cursor
            if cursor == current_sequence:
                break

        self.assertEqual(cursor, current_sequence)
        self.assertEqual(len(collected), len(set(collected)))
        self.assertEqual(observed_sequences, sorted(observed_sequences))
        self.assertEqual(set(collected), expected)


if __name__ == "__main__":
    unittest.main()
