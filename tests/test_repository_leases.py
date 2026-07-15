"""Cross-process-style tests for the canonical repository lease registry."""
from __future__ import annotations

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

from app.core.lease_registry import LeaseRegistryError, RepositoryLeaseRegistry


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value


class RepositoryLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.common = Path(self.temp.name) / ".git"
        self.common.mkdir()
        self.clock = MutableClock()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def registry(self) -> RepositoryLeaseRegistry:
        return RepositoryLeaseRegistry(clock=self.clock)

    def test_separate_registry_objects_allow_exactly_one_concurrent_writer(self) -> None:
        barrier = threading.Barrier(8)
        acquisitions = []
        lock = threading.Lock()

        def contender(index: int) -> None:
            barrier.wait()
            result = self.registry().acquire(
                self.common,
                owner=f"worker-{index}",
                task_id=f"task-{index}",
                ttl_seconds=30,
            )
            with lock:
                acquisitions.append(result)

        threads = [threading.Thread(target=contender, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        grants = [item.grant for item in acquisitions if item.grant]
        self.assertEqual(len(grants), 1)
        path = self.registry().database_path(self.common)
        with closing(sqlite3.connect(path)) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM lease_history WHERE event_type='lease.acquired'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM lease_history WHERE event_type='lease.denied'"
                ).fetchone()[0],
                7,
            )

    def test_heartbeat_expiry_and_reacquisition_use_fencing(self) -> None:
        registry = self.registry()
        first = registry.acquire(
            self.common, owner="codex:t1", task_id="t1", ttl_seconds=10
        ).grant
        self.assertIsNotNone(first)
        self.clock.value += timedelta(seconds=4)
        renewed = registry.heartbeat(
            self.common,
            first.lease.lease_id,
            first.lease.fencing_token,
            first.token,
            ttl_seconds=10,
        )
        self.assertGreater(renewed.expires_at, first.lease.expires_at)
        self.clock.value += timedelta(seconds=11)
        self.assertIsNone(registry.observe(self.common).active)
        with self.assertRaises(LeaseRegistryError):
            registry.heartbeat(
                self.common,
                first.lease.lease_id,
                first.lease.fencing_token,
                first.token,
            )
        second = registry.acquire(
            self.common, owner="claude:t2", task_id="t2"
        ).grant
        self.assertGreater(
            second.lease.fencing_token, first.lease.fencing_token
        )
        released, active = registry.release(
            self.common,
            first.lease.lease_id,
            first.lease.fencing_token,
            first.token,
        )
        self.assertFalse(released)
        self.assertEqual(active.lease_id, second.lease.lease_id)

    def test_wrong_token_or_fence_cannot_mutate_lease(self) -> None:
        registry = self.registry()
        grant = registry.acquire(
            self.common, owner="codex:t1", task_id="t1"
        ).grant
        with self.assertRaises(LeaseRegistryError):
            registry.validate(
                self.common,
                grant.lease.lease_id,
                grant.lease.fencing_token,
                "wrong",
            )
        released, active = registry.release(
            self.common,
            grant.lease.lease_id,
            grant.lease.fencing_token + 1,
            grant.token,
        )
        self.assertFalse(released)
        self.assertEqual(active.owner, "codex:t1")

    def test_registry_path_depends_only_on_common_directory(self) -> None:
        first = self.registry().database_path(self.common)
        second = self.registry().database_path(self.common / ".." / ".git")
        self.assertEqual(first.resolve(), second.resolve())


if __name__ == "__main__":
    unittest.main()
