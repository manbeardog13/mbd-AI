"""Offline tests for typed Core state, CAS tasks, adapters, and event safety."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import UTC, datetime
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
from app.core.store import CoreStore, SafeModeError, StoreConflict


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
            expected_version=task.version,
        )
        completed = self.store.transition_task(
            task.task_id,
            TaskStatus.COMPLETE,
            expected_status=assigned.status,
            expected_version=assigned.version,
            result=AgentResult(summary="verified", tests_run=("unit",)),
        )
        self.assertEqual(assigned.status, TaskStatus.PREPARING)
        self.assertEqual(assigned.version, 1)
        self.assertEqual(completed.version, 2)
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

    def test_corrupt_event_chain_enforces_read_only_safe_mode(self) -> None:
        self.store.record_event("test.event", payload={"ok": True})
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            conn.execute("DROP TRIGGER core_events_no_update")
            conn.execute("UPDATE core_events SET event_hash = 'tampered'")
            conn.commit()
        self.assertFalse(self.store.verify_event_chain()[0])
        with self.assertRaisesRegex(SafeModeError, "read-only safe mode"):
            self.store.create_task(objective="must not write", repository=self.root)
        self.assertEqual(self.store.list_tasks(), [])

    def test_malformed_event_payload_is_reported_without_read_crash(self) -> None:
        self.store.record_event("test.event", payload={"ok": True})
        with closing(sqlite3.connect(self.store.db_path)) as conn:
            conn.execute("DROP TRIGGER core_events_no_update")
            conn.execute("UPDATE core_events SET payload_json = '{bad json'")
            conn.commit()
        valid, message = self.store.verify_event_chain()
        self.assertFalse(valid)
        self.assertIn("payload invalid", message)
        event = self.store.list_events()[0]
        self.assertIn("_integrity_error", event.payload)

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

    def test_concurrent_same_task_assignment_is_compare_and_set(self) -> None:
        task = self.store.create_task(
            objective="Claim once", repository=self.root
        )
        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        lock = threading.Lock()

        def contender(adapter: str) -> None:
            store = CoreStore(self.store.db_path, clock=self.clock)
            store.initialize()
            barrier.wait()
            try:
                store.assign_task(
                    task.task_id,
                    adapter_id=adapter,
                    branch="main",
                    worktree=str(self.root),
                    expected_version=task.version,
                )
                result = "assigned"
            except StoreConflict:
                result = "conflict"
            with lock:
                outcomes.append(result)

        threads = [
            threading.Thread(target=contender, args=("claude",)),
            threading.Thread(target=contender, args=("codex",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(sorted(outcomes), ["assigned", "conflict"])
        self.assertEqual(
            len(self.store.list_events(event_type="task.assigned")), 1
        )
        self.assertEqual(self.store.get_task(task.task_id).version, 1)

    def test_stale_transition_version_cannot_overwrite_new_state(self) -> None:
        task = self.store.create_task(objective="Versioned", repository=self.root)
        paused = self.store.transition_task(
            task.task_id,
            TaskStatus.PAUSED,
            expected_status=task.status,
            expected_version=task.version,
        )
        with self.assertRaises(StoreConflict):
            self.store.transition_task(
                task.task_id,
                TaskStatus.CANCELLED,
                expected_status=task.status,
                expected_version=task.version,
            )
        self.assertEqual(self.store.get_task(task.task_id), paused)

    def test_worker_adapters_reject_nested_secrets_without_echoing_values(self) -> None:
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
            expected_version=task.version,
        )
        claude = ClaudeAdapter()
        codex = CodexAdapter()
        packet = claude.prepare_packet(task, lease_owner=None)
        self.assertFalse(packet.write_allowed)
        self.assertTrue(packet.requires_action_time_lease_validation)
        self.assertFalse(claude.descriptor().remote_writes)
        self.assertFalse(codex.descriptor().remote_writes)
        result = codex.normalize_result(
            {"summary": "checked", "tests_run": ["unit"]}
        )
        self.assertEqual(result.tests_run, ("unit",))
        secret_value = "do-not-echo-this"
        with self.assertRaises(AdapterError) as caught:
            claude.prepare_packet(
                task,
                lease_owner="claude:t1",
                bounded_context={
                    "safe": [{"clientSecret": secret_value}],
                    "nested": {"api_token": secret_value},
                },
            )
        self.assertNotIn(secret_value, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
