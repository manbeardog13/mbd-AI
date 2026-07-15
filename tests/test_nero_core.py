"""Offline tests for typed Core state, adapters, events, and write leases."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.adapters import AdapterError, ClaudeAdapter, CodexAdapter
from app.core.contracts import (
    AgentResult,
    ApprovalStatus,
    MemoryRecord,
    RiskLevel,
    TaskStatus,
)
from app.core.store import CoreStore


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


class NeroCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.clock = MutableClock()
        self.store = CoreStore(self.root / "core.db", clock=self.clock)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_required_contracts_are_serializable(self) -> None:
        memory = MemoryRecord(
            memory_id="m1",
            scope="handoff",
            content="bounded fact",
            source="operator",
            provenance={"receipt": "r1"},
            created_at="2026-07-15T12:00:00+00:00",
        )
        result = AgentResult(summary="done", files_changed=("a.py",))
        self.assertEqual(memory.as_dict()["scope"], "handoff")
        self.assertEqual(result.as_dict()["files_changed"], ["a.py"])
        json.dumps(memory.as_dict())

    def test_task_mutation_and_event_chain_are_atomic(self) -> None:
        task = self.store.create_task(
            objective="Inspect repository",
            repository=self.root,
            acceptance_criteria=("state measured",),
        )
        assigned = self.store.assign_task(
            task.task_id,
            adapter_id="codex",
            branch="main",
            worktree=str(self.root),
        )
        completed = self.store.transition_task(
            task.task_id,
            TaskStatus.COMPLETE,
            result=AgentResult(summary="verified"),
        )
        self.assertEqual(assigned.status, TaskStatus.PREPARING)
        self.assertEqual(completed.status, TaskStatus.COMPLETE)
        self.assertEqual(completed.last_result.summary, "verified")
        self.assertEqual(
            [event.event_type for event in reversed(self.store.list_events())],
            ["task.queued", "task.assigned", "task.transitioned"],
        )
        self.assertTrue(self.store.verify_event_chain()[0])

    def test_event_rows_are_append_only(self) -> None:
        event = self.store.record_event("test.event", payload={"ok": True})
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE core_events SET actor = 'tamper' WHERE sequence = ?",
                    (event.sequence,),
                )
        self.assertTrue(self.store.verify_event_chain()[0])

    def test_approval_records_decision_without_operation(self) -> None:
        approval = self.store.request_approval(
            action="git.push",
            summary="Push local branch to origin",
            risk=RiskLevel.HIGH,
            requested_by="operator",
        )
        decided = self.store.decide_approval(
            approval.approval_id,
            approved=True,
            decided_by="operator",
            note="approval evidence only",
        )
        self.assertEqual(decided.status, ApprovalStatus.APPROVED)
        event = self.store.list_events(event_type="approval.decided")[0]
        self.assertFalse(event.payload["remote_operation_executed"])

    def test_exactly_one_concurrent_write_lease(self) -> None:
        barrier = threading.Barrier(8)
        grants: list[object] = []
        lock = threading.Lock()

        def contender(index: int) -> None:
            contender_store = CoreStore(self.store.db_path, clock=self.clock)
            contender_store.initialize()
            barrier.wait()
            grant = contender_store.acquire_lease(
                "repo-common-dir", owner=f"worker-{index}", task_id=f"t-{index}"
            )
            with lock:
                grants.append(grant)

        threads = [threading.Thread(target=contender, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sum(grant is not None for grant in grants), 1)
        self.assertEqual(len(self.store.list_events(event_type="lease.acquired")), 1)
        self.assertEqual(len(self.store.list_events(event_type="lease.denied")), 7)

    def test_lease_survives_restart_then_expires_predictably(self) -> None:
        grant = self.store.acquire_lease(
            "repo-common-dir", owner="codex:t1", task_id="t1", ttl_seconds=10
        )
        self.assertIsNotNone(grant)
        restarted = CoreStore(self.store.db_path, clock=self.clock)
        restarted.initialize()
        self.assertEqual(restarted.current_lease("repo-common-dir").owner, "codex:t1")
        self.clock.value += timedelta(seconds=11)
        self.assertIsNone(restarted.current_lease("repo-common-dir"))
        self.assertEqual(len(restarted.list_events(event_type="lease.expired")), 1)

    def test_lease_token_is_hashed_and_required(self) -> None:
        grant = self.store.acquire_lease(
            "repo-common-dir", owner="codex:t1", task_id="t1"
        )
        self.assertIsNotNone(grant)
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            persisted = conn.execute(
                "SELECT token_hash FROM core_write_leases"
            ).fetchone()[0]
        self.assertNotEqual(persisted, grant.token)
        self.assertFalse(self.store.release_lease("repo-common-dir", "wrong"))
        self.assertTrue(self.store.release_lease("repo-common-dir", grant.token))

    def test_worker_adapters_are_workers_not_remote_writers(self) -> None:
        task = self.store.create_task(
            objective="Review patch",
            repository=self.root,
            acceptance_criteria=("return normalized result",),
            write_required=True,
        )
        task = self.store.assign_task(
            task.task_id,
            adapter_id="claude",
            branch="main",
            worktree=str(self.root),
        )
        claude = ClaudeAdapter()
        codex = CodexAdapter()
        packet = claude.prepare_packet(task, lease_owner=None)
        self.assertFalse(packet.write_allowed)
        self.assertFalse(claude.descriptor().remote_writes)
        self.assertFalse(codex.descriptor().remote_writes)
        result = codex.normalize_result(
            {"summary": "checked", "tests_run": ["unit"]}
        )
        self.assertEqual(result.tests_run, ("unit",))
        with self.assertRaises(AdapterError):
            claude.prepare_packet(
                task,
                lease_owner="claude:t1",
                bounded_context={"credentials": "secret"},
            )


if __name__ == "__main__":
    unittest.main()
