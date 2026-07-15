"""Adversarial verification-authority tests for Mission Control M2."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.contracts import (
    RiskLevel,
    TaskStatus,
    VerificationBackendCapabilities,
    VerificationRun,
    VerificationStatus,
)
from app.core.scheduler import ScheduleError
from app.core.lease_registry import RepositoryLeaseRegistry
from app.core.service import MissionControlService
from app.core.store import CoreStore, SafeModeError, StoreConflict
from app.core.verification import (
    DisabledRunner,
    VerificationExecutionResult,
    VerificationPolicyError,
    VerificationProfileRegistry,
    bounded_execution_result,
)


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=True,
    )


def isolated_capabilities(
    *,
    backend_id: str = "test.isolated.v1",
    test_only: bool = True,
) -> VerificationBackendCapabilities:
    return VerificationBackendCapabilities(
        backend_id=backend_id,
        backend_version="1",
        execution_available=True,
        isolation_level="test-fixture",
        os_family="windows",
        network_disabled=True,
        rootfs_readonly=True,
        snapshot_readonly=True,
        runs_as_nonroot=True,
        host_credentials_unavailable=True,
        host_devices_unavailable=True,
        docker_socket_unavailable=True,
        child_process_limit=True,
        memory_limit_supported=True,
        cpu_limit_supported=True,
        timeout_supported=True,
        output_limit_supported=True,
        no_new_privileges=True,
        capabilities_dropped=True,
        test_only=test_only,
    )


def canonical_json(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def rehash_event_chain(conn: sqlite3.Connection) -> None:
    """Rehash a deliberately tampered fixture so semantic checks are exercised."""
    conn.row_factory = sqlite3.Row
    previous = "GENESIS"
    rows = conn.execute("SELECT * FROM core_events ORDER BY sequence").fetchall()
    for row in rows:
        payload = json.loads(row["payload_json"])
        material = canonical_json(
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "actor": row["actor"],
                "task_id": row["task_id"],
                "payload": payload,
                "created_at": row["created_at"],
                "previous_hash": previous,
            }
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        conn.execute(
            "UPDATE core_events SET previous_hash=?, event_hash=? WHERE sequence=?",
            (previous, digest, row["sequence"]),
        )
        previous = digest


class FakeRunner:
    """Test-only injection; this type deliberately does not live in app/."""

    def __init__(
        self,
        *,
        result: VerificationExecutionResult | None = None,
        capabilities: VerificationBackendCapabilities | None = None,
        on_run=None,
    ) -> None:
        self._result = result or VerificationExecutionResult(
            status=VerificationStatus.PASSED,
            exit_code=0,
            detail="deterministic injected result",
        )
        self._capabilities = capabilities or isolated_capabilities()
        self._on_run = on_run
        self.calls: list[dict[str, str]] = []

    @property
    def capabilities(self) -> VerificationBackendCapabilities:
        return self._capabilities

    def run(self, profile, *, run_id: str, task_id: str, worktree: str):
        self.calls.append(
            {
                "profile_id": profile.profile_id,
                "run_id": run_id,
                "task_id": task_id,
                "worktree": worktree,
            }
        )
        if self._on_run is not None:
            self._on_run(task_id, worktree)
        return self._result


class BlockingFakeRunner(FakeRunner):
    def __init__(self) -> None:
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()

    def run(self, profile, *, run_id: str, task_id: str, worktree: str):
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise RuntimeError("blocking test runner timed out")
        return super().run(
            profile,
            run_id=run_id,
            task_id=task_id,
            worktree=worktree,
        )


class CapabilityChangingFakeRunner(FakeRunner):
    def __init__(self) -> None:
        super().__init__()
        self.changed = False

    @property
    def capabilities(self) -> VerificationBackendCapabilities:
        original = super().capabilities
        if not self.changed:
            return original
        return isolated_capabilities(
            backend_id="test.changed-after-run.v1",
            test_only=True,
        )

    def run(self, profile, *, run_id: str, task_id: str, worktree: str):
        result = super().run(
            profile,
            run_id=run_id,
            task_id=task_id,
            worktree=worktree,
        )
        self.changed = True
        return result


class FinalCapabilityDirtyingRunner(FakeRunner):
    """Mutates a tracked file from Core's final backend-controlled call."""

    def __init__(self, tracked_file: Path) -> None:
        super().__init__()
        self.tracked_file = tracked_file
        self.capability_accesses = 0
        self.capability_accesses_at_run: int | None = None
        self.armed = False
        self.dirtied = False

    @property
    def capabilities(self) -> VerificationBackendCapabilities:
        self.capability_accesses += 1
        if self.armed and not self.dirtied:
            self.dirtied = True
            self.tracked_file.write_text(
                "dirtied by final capability access\n",
                encoding="utf-8",
            )
        return self._capabilities

    def run(self, profile, *, run_id: str, task_id: str, worktree: str):
        self.capability_accesses_at_run = self.capability_accesses
        result = super().run(
            profile,
            run_id=run_id,
            task_id=task_id,
            worktree=worktree,
        )
        self.armed = True
        return result


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


class PostValidationExpiryRunner(FakeRunner):
    """Expires and replaces a lease after Core's post-run validation."""

    def __init__(
        self,
        clock: MutableClock,
        registry: RepositoryLeaseRegistry,
    ) -> None:
        super().__init__()
        self.clock = clock
        self.registry = registry
        self.common_directory: str | None = None
        self.armed = False
        self.triggered = False
        self.successor = None

    @property
    def capabilities(self) -> VerificationBackendCapabilities:
        if self.armed and not self.triggered:
            self.triggered = True
            self.clock.value += timedelta(seconds=6)
            outcome = []

            def acquire_successor() -> None:
                outcome.append(
                    self.registry.acquire(
                        self.common_directory or "",
                        owner="codex:successor",
                        task_id="successor-task",
                        ttl_seconds=5,
                    )
                )

            thread = threading.Thread(target=acquire_successor)
            thread.start()
            thread.join(timeout=10)
            if thread.is_alive() or not outcome:
                raise RuntimeError("successor lease race did not finish")
            self.successor = outcome[0]
        return self._capabilities

    def run(self, profile, *, run_id: str, task_id: str, worktree: str):
        result = super().run(
            profile,
            run_id=run_id,
            task_id=task_id,
            worktree=worktree,
        )
        self.armed = True
        return result


class PostClaimExplodingRunner(FakeRunner):
    """Raises only after its result, exercising Core's claimed-run recovery."""

    def __init__(self) -> None:
        super().__init__()
        self.explode = False

    @property
    def capabilities(self) -> VerificationBackendCapabilities:
        if self.explode:
            raise RuntimeError("raw-post-claim-secret-must-not-be-recorded")
        return super().capabilities

    def run(self, profile, *, run_id: str, task_id: str, worktree: str):
        result = super().run(
            profile,
            run_id=run_id,
            task_id=task_id,
            worktree=worktree,
        )
        self.explode = True
        return result


class DirtyFinalCapabilityExplodingRunner(PostClaimExplodingRunner):
    """Dirties the worktree immediately before its final capability failure."""

    def __init__(self, tracked_file: Path) -> None:
        super().__init__()
        self.tracked_file = tracked_file
        self.dirtied = False

    @property
    def capabilities(self) -> VerificationBackendCapabilities:
        if self.explode and not self.dirtied:
            self.dirtied = True
            self.tracked_file.write_text(
                "hostile final capability mutation\n",
                encoding="utf-8",
            )
        return super().capabilities


class NestedProfileMutatingRunner(FakeRunner):
    """Mutates the backend's shallow-frozen profile copy."""

    def __init__(self, *, raise_after_mutation: bool) -> None:
        super().__init__()
        self.raise_after_mutation = raise_after_mutation
        self.received_profile = None

    def run(self, profile, *, run_id: str, task_id: str, worktree: str):
        self.received_profile = profile
        profile.harness_files[0]["path"] = "hostile/rebound-harness.py"
        profile.harness_files[0]["sha256"] = "0" * 64
        if self.raise_after_mutation:
            raise RuntimeError("hostile profile mutation failure")
        return super().run(
            profile,
            run_id=run_id,
            task_id=task_id,
            worktree=worktree,
        )


class VerificationProfileAndRunnerTests(unittest.TestCase):
    def test_profile_digest_pins_the_reviewed_harness(self) -> None:
        registry = VerificationProfileRegistry(ROOT)
        first = registry.get(registry.PROFILE_ID)
        second = registry.get(registry.PROFILE_ID)
        harness = ROOT / first.harness_relative_path

        self.assertEqual(first, second)
        self.assertEqual(
            first.harness_sha256,
            hashlib.sha256(harness.read_bytes()).hexdigest(),
        )
        self.assertEqual(len(first.manifest_digest), 64)
        self.assertEqual(len(first.harness_files), 10)
        self.assertEqual(first.harness_files[0]["path"], first.harness_relative_path)
        for entry in first.harness_files:
            self.assertEqual(
                entry["sha256"],
                hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest(),
            )
        self.assertNotIn(str(ROOT), first.as_dict().values())
        self.assertIn("network_disabled", first.required_capabilities)

    def test_harness_change_invalidates_a_pinned_digest(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            source_profile = VerificationProfileRegistry(ROOT).get(
                VerificationProfileRegistry.PROFILE_ID
            )
            for entry in source_profile.harness_files:
                source = ROOT / entry["path"]
                destination = root / entry["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            registry = VerificationProfileRegistry(root)
            pinned = registry.get(registry.PROFILE_ID)
            closure_path = root / source_profile.harness_files[-1]["path"]
            closure_path.write_text(
                closure_path.read_text(encoding="utf-8")
                + "\n# changed closure fixture\n",
                encoding="utf-8",
            )

            changed = registry.get(registry.PROFILE_ID)
            self.assertNotEqual(changed.manifest_digest, pinned.manifest_digest)
            self.assertEqual(changed.harness_sha256, pinned.harness_sha256)
            self.assertNotEqual(changed.harness_files, pinned.harness_files)
            with self.assertRaisesRegex(VerificationPolicyError, "digest drift"):
                registry.resolve(
                    pinned.profile_id,
                    version=pinned.version,
                    digest=pinned.manifest_digest,
                )

    def test_disabled_runner_spawns_nothing_and_cannot_pass(self) -> None:
        profile = VerificationProfileRegistry(ROOT).profiles()[0]
        runner = DisabledRunner()
        with patch.object(
            subprocess,
            "Popen",
            side_effect=AssertionError("production verifier tried to spawn"),
        ) as popen:
            result = runner.run(
                profile,
                run_id="run-disabled",
                task_id="task-disabled",
                worktree=str(ROOT),
            )

        self.assertEqual(result.status, VerificationStatus.BACKEND_UNAVAILABLE)
        self.assertEqual(result.error_code, "VERIFICATION_BACKEND_DISABLED")
        self.assertFalse(runner.capabilities.execution_available)
        self.assertFalse(runner.capabilities.test_only)
        popen.assert_not_called()

    def test_backend_authority_is_core_owned_not_runner_claimed(self) -> None:
        registry = VerificationProfileRegistry(ROOT)
        profile = registry.profiles()[0]
        capabilities = isolated_capabilities()

        allowed, missing = registry.backend_satisfies(
            profile,
            capabilities,
            authorized_backend_ids=frozenset(),
            allow_test_authority=True,
        )
        self.assertFalse(allowed)
        self.assertIn("backend_authorization", missing)

        allowed, missing = registry.backend_satisfies(
            profile,
            capabilities,
            authorized_backend_ids=frozenset({capabilities.backend_id}),
            allow_test_authority=False,
        )
        self.assertFalse(allowed)
        self.assertIn("test_only_backend", missing)

        allowed, missing = registry.backend_satisfies(
            profile,
            capabilities,
            authorized_backend_ids=frozenset({capabilities.backend_id}),
            allow_test_authority=True,
        )
        self.assertTrue(allowed)
        self.assertEqual(missing, ())

    def test_pass_requires_an_explicit_zero_exit_code(self) -> None:
        for exit_code in (None, False, 7):
            with self.subTest(exit_code=exit_code):
                normalized = bounded_execution_result(
                    VerificationExecutionResult(
                        status=VerificationStatus.PASSED,
                        exit_code=exit_code,
                    )
                )
                self.assertEqual(normalized.status, VerificationStatus.ERROR)
                self.assertEqual(
                    normalized.error_code,
                    "VERIFICATION_RESULT_INVALID",
                )


class MissionControlVerificationServiceTests(unittest.TestCase):
    """Service-level tests are filled against the M2 composition contract."""

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
        git(self.repo, "config", "user.name", "Nero Verification Test")
        git(self.repo, "config", "user.email", "nero-verification@example.invalid")
        (self.repo / "state.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "state.txt")
        git(self.repo, "commit", "-m", "base")
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-u", "origin", "main")
        self.db = self.root / "mission-control.db"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _service(self, **kwargs) -> MissionControlService:
        service = MissionControlService(self.repo, self.db, **kwargs)
        service.initialize()
        service.git_state(refresh_remote=True)
        return service

    def _authoritative_service(self, runner: FakeRunner | None = None):
        selected = runner or FakeRunner()
        service = self._service(
            verification_runner=selected,
            authorized_verification_backends=frozenset(
                {selected.capabilities.backend_id}
            ),
            allow_test_backend_authority=True,
        )
        return service, selected

    def _claim_running(
        self,
        service: MissionControlService,
        verifying,
        *,
        timestamp: str,
    ) -> VerificationRun:
        profile = service.verification_registry.resolve(
            verifying.verification_profile_id,
            version=verifying.verification_profile_version,
            digest=verifying.verification_profile_digest,
        )
        state = service.scheduler.verification_git_state(verifying)
        capabilities = service.verification_runner.capabilities
        return service.store.begin_verification_run(
            VerificationRun(
                run_id=str(uuid4()),
                task_id=verifying.task_id,
                task_version=verifying.version,
                attempt=1,
                profile_id=profile.profile_id,
                profile_version=profile.version,
                profile_digest=profile.manifest_digest,
                status=VerificationStatus.RUNNING,
                authoritative=False,
                backend_id=capabilities.backend_id,
                backend_version=capabilities.backend_version,
                backend_capabilities=capabilities.as_dict(),
                repository_key=state.common_directory,
                repository=state.repository,
                worktree=state.worktree,
                branch=state.branch,
                head_before=service._head_for_state(state),
                head_after=None,
                clean_before=state.clean,
                clean_after=False,
                lease_id=None,
                lease_fencing_token=None,
                requested_at=timestamp,
                started_at=timestamp,
                completed_at=None,
                evidence={},
                evidence_hash=None,
                error_code=None,
                version=0,
            ),
            expected_task_version=verifying.version,
        )

    def _to_verifying(self, service: MissionControlService, *, write: bool = False):
        profile = service.verification_profiles()["profiles"][0]
        task = service.queue_task(
            objective="Verify the exact repository snapshot",
            write_required=write,
            verification_profile_id=profile["profile_id"],
        )
        assignment = service.assign_task(
            task.task_id,
            "codex",
            expected_version=task.version,
        )
        running = service.transition_task(
            task.task_id,
            TaskStatus.RUNNING,
            expected_version=assignment.task.version,
        )
        verifying = service.transition_task(
            task.task_id,
            TaskStatus.VERIFYING,
            expected_version=running.version,
            result={
                "summary": "worker says tests pass",
                "tests_run": ["this is advisory prose, not authority"],
            },
        )
        return verifying, assignment

    def test_manual_tests_run_and_direct_complete_never_complete(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        with self.assertRaisesRegex(ScheduleError, "completion is owned by Core"):
            service.transition_task(
                verifying.task_id,
                TaskStatus.COMPLETE,
                expected_version=verifying.version,
                result={"summary": "claimed", "tests_run": ["claimed"]},
            )
        current = service.store.get_task(verifying.task_id)
        self.assertEqual(current.status, TaskStatus.VERIFYING)
        self.assertIsNone(current.verified_run_id)

    def test_production_default_records_unavailable_non_authoritative_run(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        self.assertEqual(run.status, VerificationStatus.BACKEND_UNAVAILABLE)
        self.assertFalse(run.authoritative)
        self.assertEqual(run.error_code, "VERIFICATION_BACKEND_DISABLED")
        self.assertEqual(len(service.verification_runs(task_id=verifying.task_id)), 1)
        task = service.store.get_task(verifying.task_id)
        self.assertNotEqual(task.status, TaskStatus.COMPLETE)
        self.assertIsNone(task.verified_run_id)
        self.assertTrue(service.store.verify_event_chain()[0])

    def test_stale_task_version_is_rejected_before_claim(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        with self.assertRaisesRegex(ScheduleError, "version changed"):
            service.run_verification(
                verifying.task_id,
                expected_version=verifying.version - 1,
            )
        self.assertEqual(service.verification_runs(task_id=verifying.task_id), [])

    def test_explicit_test_injection_proves_the_trusted_completion_projection(self) -> None:
        service, runner = self._authoritative_service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        task = service.store.get_task(verifying.task_id)

        self.assertEqual(run.status, VerificationStatus.PASSED)
        self.assertTrue(run.authoritative)
        self.assertEqual(task.status, TaskStatus.COMPLETE)
        self.assertEqual(task.verified_run_id, run.run_id)
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(run.evidence["binding"]["task_id"], task.task_id)
        self.assertEqual(
            run.evidence["binding"]["profile_digest"],
            task.verification_profile_digest,
        )
        self.assertEqual(
            run.evidence_hash,
            service.store.calculate_evidence_hash(run.evidence),
        )
        self.assertTrue(service.store.verify_event_chain()[0])

    def test_truthy_string_boolean_capabilities_cannot_authorize_or_complete(
        self,
    ) -> None:
        raw = isolated_capabilities().as_dict()
        for name, value in tuple(raw.items()):
            if type(value) is bool:
                raw[name] = "false"
        capabilities = VerificationBackendCapabilities(**raw)
        self.assertIs(type(capabilities), VerificationBackendCapabilities)

        profile = VerificationProfileRegistry(ROOT).profiles()[0]
        allowed, missing = VerificationProfileRegistry.backend_satisfies(
            profile,
            capabilities,
            authorized_backend_ids=frozenset({capabilities.backend_id}),
            allow_test_authority=True,
        )
        self.assertFalse(allowed)
        self.assertEqual(missing, ("capability_contract",))

        service, _ = self._authoritative_service()
        verifying, _ = self._to_verifying(service)
        service.verification_runner = FakeRunner(capabilities=capabilities)
        with self.assertRaisesRegex(
            VerificationPolicyError,
            "capability field is not boolean",
        ):
            service.run_verification(
                verifying.task_id,
                expected_version=verifying.version,
            )
        task = service.store.get_task(verifying.task_id)
        self.assertEqual(task.status, TaskStatus.VERIFYING)
        self.assertIsNone(task.verified_run_id)
        self.assertEqual(service.verification_runs(task_id=verifying.task_id), [])

    def test_pass_with_boolean_false_exit_code_is_invalid_and_non_authoritative(
        self,
    ) -> None:
        runner = FakeRunner(
            result=VerificationExecutionResult(
                status=VerificationStatus.PASSED,
                exit_code=False,
            )
        )
        service, _ = self._authoritative_service(runner)
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        task = service.store.get_task(verifying.task_id)

        self.assertEqual(run.status, VerificationStatus.ERROR)
        self.assertFalse(run.authoritative)
        self.assertEqual(run.error_code, "VERIFICATION_RESULT_INVALID")
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertIsNone(task.verified_run_id)

    def test_final_backend_capability_access_cannot_dirty_workspace_unobserved(
        self,
    ) -> None:
        runner = FinalCapabilityDirtyingRunner(self.repo / "state.txt")
        service = self._service(
            verification_runner=runner,
            authorized_verification_backends=frozenset(
                {runner._capabilities.backend_id}
            ),
            allow_test_backend_authority=True,
        )
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        task = service.store.get_task(verifying.task_id)

        self.assertTrue(runner.dirtied)
        self.assertEqual(
            runner.capability_accesses,
            runner.capability_accesses_at_run + 1,
        )
        self.assertFalse(run.authoritative)
        self.assertEqual(run.status, VerificationStatus.BLOCKED)
        self.assertEqual(run.error_code, "VERIFICATION_STATE_DRIFT")
        self.assertIn("workspace_drift", run.evidence["drift"])
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertIsNone(task.verified_run_id)

    def test_runner_pass_without_core_authorization_is_blocked(self) -> None:
        runner = FakeRunner()
        service = self._service(verification_runner=runner)
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        task = service.store.get_task(verifying.task_id)

        self.assertEqual(run.status, VerificationStatus.BLOCKED)
        self.assertFalse(run.authoritative)
        self.assertEqual(run.error_code, "VERIFICATION_BACKEND_NOT_AUTHORIZED")
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertIsNone(task.verified_run_id)

    def test_git_drift_during_runner_invalidates_a_pass(self) -> None:
        runner = FakeRunner(
            on_run=lambda _task_id, worktree: (
                Path(worktree) / "runner-drift.txt"
            ).write_text("drift\n", encoding="utf-8")
        )
        service, _ = self._authoritative_service(runner)
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )

        self.assertFalse(run.authoritative)
        self.assertEqual(run.status, VerificationStatus.BLOCKED)
        self.assertEqual(run.error_code, "VERIFICATION_STATE_DRIFT")
        self.assertIn("workspace_drift", run.evidence["drift"])
        self.assertIsNone(service.store.get_task(verifying.task_id).verified_run_id)

    def test_wrong_bound_branch_is_rejected_before_a_run_claim(self) -> None:
        service, _ = self._authoritative_service()
        verifying, _ = self._to_verifying(service)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                "UPDATE core_tasks SET branch='forged-branch' WHERE task_id=?",
                (verifying.task_id,),
            )
            conn.commit()

        with self.assertRaisesRegex(ScheduleError, "branch binding changed"):
            service.run_verification(
                verifying.task_id,
                expected_version=verifying.version,
            )
        self.assertEqual(service.verification_runs(task_id=verifying.task_id), [])

    def test_lease_fence_loss_during_runner_invalidates_a_pass(self) -> None:
        holder: dict[str, MissionControlService] = {}

        def release_lease(task_id: str, _worktree: str) -> None:
            holder["service"].scheduler.release_verification_lease(task_id)

        runner = FakeRunner(on_run=release_lease)
        service, _ = self._authoritative_service(runner)
        holder["service"] = service
        verifying, assignment = self._to_verifying(service, write=True)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )

        self.assertIsNotNone(assignment.lease)
        self.assertFalse(run.authoritative)
        self.assertEqual(run.error_code, "VERIFICATION_STATE_DRIFT")
        self.assertTrue(
            {"lease_lost", "lease_fence_changed"}.issubset(run.evidence["drift"])
        )
        self.assertIsNone(service.store.get_task(verifying.task_id).verified_run_id)

    def test_expired_lease_replaced_after_validation_cannot_complete(self) -> None:
        clock = MutableClock()
        registry = RepositoryLeaseRegistry(clock=clock)
        runner = PostValidationExpiryRunner(clock, registry)
        service = MissionControlService(
            self.repo,
            self.db,
            lease_registry=registry,
            lease_ttl_seconds=5,
            verification_runner=runner,
            authorized_verification_backends=frozenset(
                {runner._capabilities.backend_id}
            ),
            allow_test_backend_authority=True,
        )
        service.initialize()
        service.git_state(refresh_remote=True)
        runner.common_directory = service.git.inspect(self.repo).common_directory
        verifying, assignment = self._to_verifying(service, write=True)

        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        task = service.store.get_task(verifying.task_id)

        self.assertIsNotNone(assignment.lease)
        self.assertTrue(runner.triggered)
        self.assertIsNotNone(runner.successor)
        self.assertIsNotNone(runner.successor.grant)
        self.assertGreater(
            runner.successor.grant.lease.fencing_token,
            assignment.lease.fencing_token,
        )
        self.assertFalse(run.authoritative)
        self.assertNotEqual(run.status, VerificationStatus.PASSED)
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertIsNone(task.verified_run_id)
        active = registry.observe(runner.common_directory).active
        self.assertEqual(active.lease_id, runner.successor.grant.lease.lease_id)

    def test_backend_capability_drift_during_runner_invalidates_a_pass(self) -> None:
        runner = CapabilityChangingFakeRunner()
        service, _ = self._authoritative_service(runner)
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )

        self.assertFalse(run.authoritative)
        self.assertEqual(run.error_code, "VERIFICATION_STATE_DRIFT")
        self.assertIn("backend_capabilities_changed", run.evidence["drift"])

    def test_post_claim_internal_error_is_sanitized_terminal_and_releases_lease(self) -> None:
        runner = PostClaimExplodingRunner()
        service, _ = self._authoritative_service(runner)
        verifying, assignment = self._to_verifying(service, write=True)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        task = service.store.get_task(verifying.task_id)

        self.assertIsNotNone(assignment.lease)
        self.assertEqual(run.status, VerificationStatus.ERROR)
        self.assertEqual(run.error_code, "VERIFICATION_INTERNAL_ERROR")
        self.assertFalse(run.authoritative)
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertIsNone(task.verified_run_id)
        self.assertNotIn(
            "raw-post-claim-secret-must-not-be-recorded",
            canonical_json(run.evidence),
        )
        self.assertIn(run.run_id, canonical_json(run.evidence))
        self.assertEqual(
            service.verification_runs(status=VerificationStatus.RUNNING),
            [],
        )
        common = service.git.inspect(self.repo).common_directory
        self.assertIsNone(service.lease_registry.observe(common).active)
        self.assertTrue(service.store.verify_event_chain()[0])

    def test_dirty_final_capability_failure_seals_claim_and_releases_lease(
        self,
    ) -> None:
        runner = DirtyFinalCapabilityExplodingRunner(self.repo / "state.txt")
        service, _ = self._authoritative_service(runner)
        verifying, assignment = self._to_verifying(service, write=True)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        task = service.store.get_task(verifying.task_id)

        self.assertIsNotNone(assignment.lease)
        self.assertTrue(runner.dirtied)
        self.assertEqual(run.status, VerificationStatus.ERROR)
        self.assertEqual(run.error_code, "VERIFICATION_INTERNAL_ERROR")
        self.assertFalse(run.authoritative)
        self.assertIn("internal_error", run.evidence["drift"])
        self.assertIn("workspace_drift", run.evidence["drift"])
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertIsNone(task.verified_run_id)
        self.assertEqual(
            service.verification_runs(status=VerificationStatus.RUNNING),
            [],
        )
        common = service.git.inspect(self.repo).common_directory
        self.assertIsNone(service.lease_registry.observe(common).active)
        self.assertTrue(service.store.verify_event_chain()[0])

    def test_backend_profile_nested_mutation_never_rebinds_core_profile(
        self,
    ) -> None:
        for mode in ("return", "raise"):
            with self.subTest(backend_outcome=mode):
                runner = NestedProfileMutatingRunner(
                    raise_after_mutation=mode == "raise"
                )
                service = MissionControlService(
                    self.repo,
                    self.root / f"profile-mutation-{mode}.db",
                    verification_runner=runner,
                    authorized_verification_backends=frozenset(
                        {runner._capabilities.backend_id}
                    ),
                    allow_test_backend_authority=True,
                )
                service.initialize()
                service.git_state(refresh_remote=True)
                pristine = service.verification_registry.profiles()[0]
                pristine_entry = dict(pristine.harness_files[0])
                verifying, assignment = self._to_verifying(service, write=True)

                run = service.run_verification(
                    verifying.task_id,
                    expected_version=verifying.version,
                )
                task = service.store.get_task(verifying.task_id)

                self.assertIsNotNone(assignment.lease)
                self.assertEqual(
                    runner.received_profile.harness_files[0]["path"],
                    "hostile/rebound-harness.py",
                )
                self.assertEqual(pristine.harness_files[0], pristine_entry)
                resolved = service.verification_registry.resolve(
                    pristine.profile_id,
                    version=pristine.version,
                    digest=pristine.manifest_digest,
                )
                self.assertEqual(resolved.harness_files[0], pristine_entry)
                self.assertEqual(
                    run.evidence["profile"]["harness_files"][0],
                    pristine_entry,
                )
                self.assertEqual(
                    service.verification_runs(status=VerificationStatus.RUNNING),
                    [],
                )
                self.assertEqual(
                    service.store.list_tasks(status=TaskStatus.VERIFYING),
                    [],
                )
                common = service.git.inspect(self.repo).common_directory
                self.assertIsNone(service.lease_registry.observe(common).active)
                if mode == "return":
                    self.assertTrue(run.authoritative)
                    self.assertEqual(run.status, VerificationStatus.PASSED)
                    self.assertEqual(task.status, TaskStatus.COMPLETE)
                else:
                    self.assertFalse(run.authoritative)
                    self.assertEqual(run.status, VerificationStatus.ERROR)
                    self.assertEqual(
                        run.error_code,
                        "VERIFICATION_BACKEND_ERROR",
                    )
                    self.assertEqual(task.status, TaskStatus.BLOCKED)
                self.assertTrue(service.store.verify_event_chain()[0])

    def test_repository_allows_only_one_active_run_claim(self) -> None:
        runner = BlockingFakeRunner()
        service, _ = self._authoritative_service(runner)
        first, _ = self._to_verifying(service)
        second, _ = self._to_verifying(service)
        outcome: list[object] = []

        def run_first() -> None:
            try:
                outcome.append(
                    service.run_verification(
                        first.task_id,
                        expected_version=first.version,
                    )
                )
            except BaseException as exc:
                outcome.append(exc)

        thread = threading.Thread(target=run_first)
        thread.start()
        self.assertTrue(runner.entered.wait(timeout=10))
        try:
            with self.assertRaisesRegex(StoreConflict, "active or prior claim"):
                service.run_verification(
                    second.task_id,
                    expected_version=second.version,
                )
        finally:
            runner.release.set()
            thread.join(timeout=10)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(outcome), 1)
        self.assertFalse(isinstance(outcome[0], BaseException), outcome)
        self.assertEqual(len(service.verification_runs(task_id=first.task_id)), 1)
        self.assertEqual(service.verification_runs(task_id=second.task_id), [])

    def test_terminal_run_rows_reject_update_and_delete(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )

        with closing(sqlite3.connect(self.db)) as conn:
            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "terminal verification runs are immutable"
            ):
                conn.execute(
                    "UPDATE core_verification_runs SET error_code='forged' "
                    "WHERE run_id=?",
                    (run.run_id,),
                )
        with closing(sqlite3.connect(self.db)) as conn:
            with self.assertRaisesRegex(
                sqlite3.IntegrityError, "verification runs are append-only"
            ):
                conn.execute(
                    "DELETE FROM core_verification_runs WHERE run_id=?",
                    (run.run_id,),
                )
        self.assertTrue(service.store.verify_event_chain()[0])

    def test_evidence_tamper_is_detected_against_hash_and_event(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TRIGGER core_verification_runs_terminal_no_update")
            conn.execute(
                "UPDATE core_verification_runs SET evidence_json='{}' WHERE run_id=?",
                (run.run_id,),
            )
            conn.executescript(
                """
                CREATE TRIGGER core_verification_runs_terminal_no_update
                BEFORE UPDATE ON core_verification_runs
                WHEN OLD.status <> 'running' OR NEW.status = 'running'
                BEGIN
                    SELECT RAISE(
                        ABORT, 'terminal verification runs are immutable'
                    );
                END;
                """
            )
            conn.commit()

        auditor = CoreStore(self.db)
        valid, message = auditor.verify_event_chain()
        self.assertFalse(valid)
        self.assertIn("verification evidence", message)
        with self.assertRaisesRegex(SafeModeError, "read-only safe mode"):
            auditor.create_task(objective="tamper must block", repository=self.repo)

    def test_rehashed_evidence_cannot_change_semantic_row_binding(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        def mutate_profile_manifest(evidence):
            profile = evidence["profile"]
            profile["harness_relative_path"] = "forged/runner.py"
            profile["harness_sha256"] = "0" * 64
            profile["harness_files"][0]["path"] = "forged/runner.py"
            profile["required_capabilities"] = []

        mutations = {
            "task binding": lambda evidence: evidence["binding"].__setitem__(
                "task_id", "forged-semantic-task"
            ),
            "profile binding": lambda evidence: evidence["profile"].__setitem__(
                "manifest_digest", "forged-profile-digest"
            ),
            "workspace binding": lambda evidence: evidence[
                "workspace_before"
            ].__setitem__("head", "forged-git-head"),
            "backend binding": lambda evidence: evidence["backend"][
                "capabilities"
            ].__setitem__("backend_id", "forged-backend"),
            "full profile manifest": mutate_profile_manifest,
        }
        for index, (label, mutate) in enumerate(mutations.items()):
            with self.subTest(binding=label):
                tampered = self.root / f"semantic-tamper-{index}.db"
                shutil.copy2(self.db, tampered)
                with closing(sqlite3.connect(tampered)) as conn:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(
                        "SELECT evidence_json FROM core_verification_runs "
                        "WHERE run_id=?",
                        (run.run_id,),
                    ).fetchone()
                    evidence = json.loads(row["evidence_json"])
                    mutate(evidence)
                    forged_hash = hashlib.sha256(
                        canonical_json(evidence).encode("utf-8")
                    ).hexdigest()

                    conn.execute(
                        "DROP TRIGGER core_verification_runs_terminal_no_update"
                    )
                    conn.execute("DROP TRIGGER core_events_no_update")
                    conn.execute(
                        "UPDATE core_verification_runs "
                        "SET evidence_json=?, evidence_hash=? WHERE run_id=?",
                        (canonical_json(evidence), forged_hash, run.run_id),
                    )
                    event = conn.execute(
                        "SELECT sequence, payload_json FROM core_events "
                        "WHERE event_type='verification.recorded' AND task_id=?",
                        (verifying.task_id,),
                    ).fetchone()
                    payload = json.loads(event["payload_json"])
                    payload["evidence_hash"] = forged_hash
                    payload["receipt"]["evidence_hash"] = forged_hash
                    conn.execute(
                        "UPDATE core_events SET payload_json=? WHERE sequence=?",
                        (canonical_json(payload), event["sequence"]),
                    )
                    rehash_event_chain(conn)
                    conn.executescript(
                        """
                        CREATE TRIGGER core_events_no_update
                        BEFORE UPDATE ON core_events BEGIN
                            SELECT RAISE(ABORT, 'core events are append-only');
                        END;
                        CREATE TRIGGER core_verification_runs_terminal_no_update
                        BEFORE UPDATE ON core_verification_runs
                        WHEN OLD.status <> 'running' OR NEW.status = 'running'
                        BEGIN
                            SELECT RAISE(
                                ABORT, 'terminal verification runs are immutable'
                            );
                        END;
                        """
                    )
                    conn.commit()

                valid, message = CoreStore(tampered).verify_event_chain()
                self.assertFalse(valid, label)
                self.assertIn("evidence", message)

    def test_rehashed_workspace_after_row_cannot_rebind_immutable_location(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        with closing(sqlite3.connect(self.db)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT evidence_json FROM core_verification_runs WHERE run_id=?",
                (run.run_id,),
            ).fetchone()
            evidence = json.loads(row["evidence_json"])
            workspace_after = evidence["workspace_after"]
            workspace_after.update(
                {
                    "repository": "C:/forged/repository",
                    "worktree": "C:/forged/worktree",
                    "branch": "forged-branch",
                    "conflict_count": 9,
                    "detached_head": True,
                }
            )
            forged_hash = hashlib.sha256(
                canonical_json(evidence).encode("utf-8")
            ).hexdigest()
            conn.execute("DROP TRIGGER core_verification_runs_terminal_no_update")
            conn.execute("DROP TRIGGER core_events_no_update")
            conn.execute(
                "UPDATE core_verification_runs SET workspace_after_json=?, "
                "evidence_json=?, evidence_hash=? WHERE run_id=?",
                (
                    canonical_json(workspace_after),
                    canonical_json(evidence),
                    forged_hash,
                    run.run_id,
                ),
            )
            event = conn.execute(
                "SELECT sequence, payload_json FROM core_events "
                "WHERE event_type='verification.recorded' AND task_id=?",
                (verifying.task_id,),
            ).fetchone()
            payload = json.loads(event["payload_json"])
            payload["evidence_hash"] = forged_hash
            payload["receipt"]["evidence_hash"] = forged_hash
            payload["receipt"]["workspace_after"] = workspace_after
            conn.execute(
                "UPDATE core_events SET payload_json=? WHERE sequence=?",
                (canonical_json(payload), event["sequence"]),
            )
            rehash_event_chain(conn)
            conn.executescript(
                """
                CREATE TRIGGER core_events_no_update
                BEFORE UPDATE ON core_events BEGIN
                    SELECT RAISE(ABORT, 'core events are append-only');
                END;
                CREATE TRIGGER core_verification_runs_terminal_no_update
                BEFORE UPDATE ON core_verification_runs
                WHEN OLD.status <> 'running' OR NEW.status = 'running'
                BEGIN
                    SELECT RAISE(
                        ABORT, 'terminal verification runs are immutable'
                    );
                END;
                """
            )
            conn.commit()

        valid, message = CoreStore(self.db).verify_event_chain()
        self.assertFalse(valid)
        self.assertIn("final workspace binding", message)

    def test_running_run_requires_exact_task_projection(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        claimed = self._claim_running(
            service,
            verifying,
            timestamp="2026-07-15T12:00:00.000+00:00",
        )
        mutations = {
            "status": ("status='running'", ()),
            "version": ("version=version+4", ()),
            "repository": ("repository=?", ("C:/forged/repository",)),
            "worktree": ("worktree=?", ("C:/forged/worktree",)),
            "branch": ("branch=?", ("forged-branch",)),
        }
        for index, (label, (assignment, parameters)) in enumerate(mutations.items()):
            with self.subTest(task_projection=label):
                tampered = self.root / f"running-projection-{index}.db"
                shutil.copy2(self.db, tampered)
                with closing(sqlite3.connect(tampered)) as conn:
                    conn.execute(
                        f"UPDATE core_tasks SET {assignment} WHERE task_id=?",
                        (*parameters, verifying.task_id),
                    )
                    conn.commit()
                valid, message = CoreStore(tampered).verify_event_chain()
                self.assertFalse(valid)
                self.assertIn(
                    f"running verification task projection failed for run {claimed.run_id}",
                    message,
                )

    def test_terminal_receipt_and_task_transition_are_exactly_paired(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        cases = (
            ("recorded versions", "recorded", "verification receipt binding"),
            ("transition versions", "transition", "task transition binding"),
            ("missing transition", "delete", "missing its task transition"),
        )
        for index, (label, mutation, expected) in enumerate(cases):
            with self.subTest(event_binding=label):
                tampered = self.root / f"terminal-event-binding-{index}.db"
                shutil.copy2(self.db, tampered)
                with closing(sqlite3.connect(tampered)) as conn:
                    conn.row_factory = sqlite3.Row
                    if mutation == "delete":
                        conn.execute("DROP TRIGGER core_events_no_delete")
                        conn.execute("DROP TRIGGER core_events_no_update")
                        conn.execute(
                            "DELETE FROM core_events WHERE sequence=("
                            "SELECT sequence FROM core_events "
                            "WHERE event_type='task.transitioned' AND task_id=? "
                            "ORDER BY sequence DESC LIMIT 1)",
                            (verifying.task_id,),
                        )
                    else:
                        conn.execute("DROP TRIGGER core_events_no_update")
                        event_type = (
                            "verification.recorded"
                            if mutation == "recorded"
                            else "task.transitioned"
                        )
                        event = conn.execute(
                            "SELECT sequence, payload_json FROM core_events "
                            "WHERE event_type=? AND task_id=? "
                            "ORDER BY sequence DESC LIMIT 1",
                            (event_type, verifying.task_id),
                        ).fetchone()
                        payload = json.loads(event["payload_json"])
                        field = (
                            "from_task_version"
                            if mutation == "recorded"
                            else "from_version"
                        )
                        payload[field] = int(payload[field]) + 7
                        conn.execute(
                            "UPDATE core_events SET payload_json=? WHERE sequence=?",
                            (canonical_json(payload), event["sequence"]),
                        )
                    rehash_event_chain(conn)
                    if mutation == "delete":
                        conn.executescript(
                            """
                            CREATE TRIGGER core_events_no_update
                            BEFORE UPDATE ON core_events BEGIN
                                SELECT RAISE(ABORT, 'core events are append-only');
                            END;
                            CREATE TRIGGER core_events_no_delete
                            BEFORE DELETE ON core_events BEGIN
                                SELECT RAISE(ABORT, 'core events are append-only');
                            END;
                            """
                        )
                    else:
                        conn.executescript(
                            """
                            CREATE TRIGGER core_events_no_update
                            BEFORE UPDATE ON core_events BEGIN
                                SELECT RAISE(ABORT, 'core events are append-only');
                            END;
                            """
                        )
                    conn.commit()

                valid, message = CoreStore(tampered).verify_event_chain()
                self.assertFalse(valid)
                self.assertIn(expected, message)

    def test_running_row_without_matching_started_event_fails_integrity(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        claimed = self._claim_running(
            service,
            verifying,
            timestamp="2026-07-15T12:00:00.000+00:00",
        )
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TRIGGER core_events_no_delete")
            conn.execute(
                "DELETE FROM core_events WHERE event_type='verification.started' "
                "AND task_id=?",
                (verifying.task_id,),
            )
            conn.executescript(
                """
                CREATE TRIGGER core_events_no_delete
                BEFORE DELETE ON core_events BEGIN
                    SELECT RAISE(ABORT, 'core events are append-only');
                END;
                """
            )
            conn.commit()

        auditor = CoreStore(self.db)
        valid, message = auditor.verify_event_chain()
        self.assertFalse(valid)
        self.assertIn(claimed.run_id, message)
        self.assertIn("started", message)

    def test_orphan_started_event_without_running_row_fails_integrity(self) -> None:
        service = self._service()
        orphan = str(uuid4())
        service.store.record_event(
            "verification.started",
            actor="hostile-fixture",
            payload={"run_id": orphan},
        )
        valid, message = service.store.verify_event_chain()
        self.assertFalse(valid)
        self.assertIn(orphan, message)
        self.assertIn("row", message)

    def test_default_service_reconciles_abandoned_running_claim(self) -> None:
        original = self._service()
        verifying, _ = self._to_verifying(original)
        claimed = self._claim_running(
            original,
            verifying,
            timestamp="2020-01-01T00:00:00.000+00:00",
        )

        restarted = MissionControlService(self.repo, self.db)
        restarted.initialize()
        recovered = restarted.verification_run(claimed.run_id)
        task = restarted.store.get_task(verifying.task_id)

        self.assertEqual(recovered.status, VerificationStatus.INTERRUPTED)
        self.assertEqual(
            recovered.error_code,
            "VERIFICATION_PROCESS_INTERRUPTED",
        )
        self.assertFalse(recovered.authoritative)
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertIsNone(task.verified_run_id)
        self.assertEqual(
            restarted.verification_runs(status=VerificationStatus.RUNNING),
            [],
        )
        self.assertIn("core_process_interrupted", recovered.evidence["drift"])
        self.assertTrue(restarted.store.verify_event_chain()[0])

    def test_abandoned_dirty_workspace_is_sealed_interrupted_on_restart(
        self,
    ) -> None:
        original = self._service()
        verifying, _ = self._to_verifying(original)
        claimed = self._claim_running(
            original,
            verifying,
            timestamp="2020-01-01T00:00:00.000+00:00",
        )
        (self.repo / "state.txt").write_text(
            "dirty after abandoned claim\n",
            encoding="utf-8",
        )

        restarted = MissionControlService(self.repo, self.db)
        restarted.initialize()
        recovered = restarted.verification_run(claimed.run_id)
        task = restarted.store.get_task(verifying.task_id)

        self.assertEqual(recovered.status, VerificationStatus.INTERRUPTED)
        self.assertEqual(
            recovered.error_code,
            "VERIFICATION_PROCESS_INTERRUPTED",
        )
        self.assertFalse(recovered.authoritative)
        self.assertIn("core_process_interrupted", recovered.evidence["drift"])
        self.assertIn("workspace_drift", recovered.evidence["drift"])
        self.assertFalse(recovered.evidence["workspace_after"]["clean"])
        self.assertEqual(task.status, TaskStatus.BLOCKED)
        self.assertIsNone(task.verified_run_id)
        self.assertEqual(
            restarted.verification_runs(status=VerificationStatus.RUNNING),
            [],
        )
        self.assertEqual(
            restarted.store.list_tasks(status=TaskStatus.VERIFYING),
            [],
        )
        self.assertTrue(restarted.store.verify_event_chain()[0])

    def test_replayed_terminal_receipt_forces_safe_mode(self) -> None:
        service = self._service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        recorded = service.store.list_events(
            event_type="verification.recorded",
            task_id=verifying.task_id,
        )[0]
        service.store.record_event(
            "verification.recorded",
            actor="replay-attempt",
            task_id=verifying.task_id,
            payload=recorded.payload,
        )

        valid, message = service.store.verify_event_chain()
        self.assertFalse(valid)
        self.assertIn("duplicate verification.recorded", message)
        with self.assertRaisesRegex(SafeModeError, "read-only safe mode"):
            service.store.create_task(objective="blocked", repository=self.repo)

    def test_authoritative_run_and_completed_task_projection_cannot_diverge(self) -> None:
        service, _ = self._authoritative_service()
        verifying, _ = self._to_verifying(service)
        run = service.run_verification(
            verifying.task_id,
            expected_version=verifying.version,
        )
        self.assertTrue(run.authoritative)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                "UPDATE core_tasks SET verified_run_id=NULL WHERE task_id=?",
                (verifying.task_id,),
            )
            conn.commit()

        auditor = CoreStore(self.db)
        valid, message = auditor.verify_event_chain()
        self.assertFalse(valid)
        self.assertIn("verified run projection", message)
        with self.assertRaisesRegex(SafeModeError, "read-only safe mode"):
            auditor.create_task(objective="projection tamper", repository=self.repo)

    def test_profile_binding_is_immutable_and_digest_drift_fails_closed(self) -> None:
        service = self._service()
        profile = service.verification_profiles()["profiles"][0]
        task = service.queue_task(objective="Pinned profile")
        bound = service.bind_verification_profile(
            task.task_id,
            profile["profile_id"],
            expected_version=task.version,
        )
        same = service.bind_verification_profile(
            task.task_id,
            profile["profile_id"],
            expected_version=bound.version,
        )
        self.assertEqual(same.version, bound.version)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                "UPDATE core_tasks SET verification_profile_digest='forged' "
                "WHERE task_id=?",
                (task.task_id,),
            )
            conn.commit()
        self.assertFalse(service.store.verify_event_chain()[0])
        with self.assertRaisesRegex(VerificationPolicyError, "digest drift"):
            service.assign_task(
                task.task_id,
                "codex",
                expected_version=bound.version,
            )
        with self.assertRaisesRegex(SafeModeError, "read-only safe mode"):
            service.store.create_task(
                objective="mutation must remain blocked",
                repository=self.repo,
            )

    def test_attention_cursor_never_replays_previous_items(self) -> None:
        service = self._service()
        service.request_approval(
            action="verification.backend.enable",
            summary="Future isolated backend needs explicit approval",
            risk=RiskLevel.HIGH,
        )
        first = service.attention(after_sequence=0, limit=100)["items"]
        self.assertTrue(first)
        cursor = max(item["sequence"] for item in first)
        second = service.attention(after_sequence=cursor, limit=100)["items"]
        self.assertTrue(all(item["sequence"] > cursor for item in second))
        self.assertFalse(
            {item["event_id"] for item in first}
            & {item["event_id"] for item in second}
        )

    def test_attention_snapshot_excludes_concurrent_event_until_next_cursor(self) -> None:
        service = self._service()
        service.request_approval(
            action="snapshot.initial",
            summary="Initial actionable event",
            risk=RiskLevel.HIGH,
        )
        original = service.store.list_events_after
        injected = False

        def inject_after_snapshot(**kwargs):
            nonlocal injected
            if not injected:
                injected = True
                service.request_approval(
                    action="snapshot.concurrent",
                    summary="Concurrent actionable event",
                    risk=RiskLevel.HIGH,
                )
            return original(**kwargs)

        with patch.object(
            service.store,
            "list_events_after",
            side_effect=inject_after_snapshot,
        ):
            first = service.attention(after_sequence=0, limit=100)

        concurrent_event = service.store.list_events(
            event_type="approval.requested",
            limit=1,
        )[0]
        self.assertGreater(concurrent_event.sequence, first["current_sequence"])
        self.assertNotIn(
            concurrent_event.event_id,
            {item["event_id"] for item in first["items"]},
        )

        second = service.attention(
            after_sequence=first["next_cursor"],
            limit=100,
        )
        self.assertEqual(
            [
                item["event_id"]
                for item in second["items"]
                if item["event_id"] == concurrent_event.event_id
            ],
            [concurrent_event.event_id],
        )
        third = service.attention(
            after_sequence=second["next_cursor"],
            limit=100,
        )
        self.assertNotIn(
            concurrent_event.event_id,
            {item["event_id"] for item in third["items"]},
        )


if __name__ == "__main__":
    unittest.main()
