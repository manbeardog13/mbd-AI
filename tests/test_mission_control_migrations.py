"""Hostile, offline migration checks for Mission Control M2."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.store import CoreStore, SafeModeError, SCHEMA_VERSION, StoreError


M1_SCHEMA = """
CREATE TABLE core_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE core_tasks (
    task_id TEXT PRIMARY KEY,
    objective TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    dependencies_json TEXT NOT NULL,
    acceptance_json TEXT NOT NULL,
    write_required INTEGER NOT NULL,
    repository TEXT NOT NULL,
    branch TEXT,
    worktree TEXT,
    assigned_adapter TEXT,
    context_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,
    blocker TEXT
);
CREATE TABLE core_approvals (
    approval_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    summary TEXT NOT NULL,
    risk TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    decision_note TEXT
);
CREATE TABLE core_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    task_id TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE
);
"""


def create_m1_database(
    path: Path,
    *,
    legacy_complete: bool = False,
    corrupt_event: bool = False,
) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(M1_SCHEMA)
        conn.execute(
            "INSERT INTO core_meta(key, value) VALUES ('schema_version', '1')"
        )
        if legacy_complete:
            conn.execute(
                """
                INSERT INTO core_tasks(
                    task_id, objective, status, priority, dependencies_json,
                    acceptance_json, write_required, repository, branch,
                    worktree, assigned_adapter, context_version, created_at,
                    updated_at, version, result_json, blocker
                ) VALUES (
                    'legacy-complete', 'Historical M1 task', 'complete', 50,
                    '[]', '[]', 0, ?, 'main', ?, 'codex', 'm1', ?, ?, 7,
                    '{"summary":"worker claimed verification","tests_run":["manual"]}',
                    NULL
                )
                """,
                (
                    str(path.parent),
                    str(path.parent),
                    "2026-07-15T08:00:00+00:00",
                    "2026-07-15T08:01:00+00:00",
                ),
            )
        if corrupt_event:
            conn.execute(
                """
                INSERT INTO core_events(
                    event_id, event_type, actor, task_id, payload_json,
                    created_at, previous_hash, event_hash
                ) VALUES ('bad-event', 'legacy.event', 'legacy', NULL, '{}',
                          '2026-07-15T08:00:00+00:00', 'GENESIS', 'tampered')
                """
            )
        conn.commit()


class MissionControlMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "mission-control.db"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_m1_upgrade_is_transactional_idempotent_and_preserves_legacy_truth(self) -> None:
        create_m1_database(self.db, legacy_complete=True)
        store = CoreStore(self.db)
        store.initialize()

        with closing(sqlite3.connect(self.db)) as conn:
            conn.row_factory = sqlite3.Row
            version = conn.execute(
                "SELECT value FROM core_meta WHERE key='schema_version'"
            ).fetchone()["value"]
            task_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(core_tasks)").fetchall()
            }
            migrated = conn.execute(
                "SELECT COUNT(*) FROM core_events WHERE event_type='schema.migrated'"
            ).fetchone()[0]
            legacy = conn.execute(
                "SELECT status, version, verified_run_id FROM core_tasks "
                "WHERE task_id='legacy-complete'"
            ).fetchone()
            run_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='core_verification_runs'"
            ).fetchone()

        self.assertEqual(int(version), SCHEMA_VERSION)
        self.assertTrue(
            {
                "verification_profile_id",
                "verification_profile_version",
                "verification_profile_digest",
                "verified_run_id",
            }.issubset(task_columns)
        )
        self.assertIsNotNone(run_table)
        self.assertEqual(migrated, 1)
        self.assertEqual(legacy["status"], "complete")
        self.assertEqual(legacy["version"], 7)
        self.assertIsNone(legacy["verified_run_id"])

        store.initialize()
        self.assertEqual(
            len(store.list_events(event_type="schema.migrated")),
            1,
        )
        self.assertTrue(store.verify_event_chain()[0])

    def test_two_initializers_create_one_migration_event(self) -> None:
        create_m1_database(self.db)
        barrier = threading.Barrier(2)
        errors: list[BaseException] = []
        lock = threading.Lock()

        def initialize() -> None:
            barrier.wait()
            try:
                CoreStore(self.db).initialize()
            except BaseException as exc:  # capture thread failures for the assertion
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=initialize) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        store = CoreStore(self.db)
        self.assertEqual(len(store.list_events(event_type="schema.migrated")), 1)
        self.assertTrue(store.verify_event_chain()[0])

    def test_corrupt_m1_chain_is_not_migrated(self) -> None:
        create_m1_database(self.db, corrupt_event=True)
        with self.assertRaisesRegex(SafeModeError, "read-only safe mode"):
            CoreStore(self.db).initialize()

        with closing(sqlite3.connect(self.db)) as conn:
            version = conn.execute(
                "SELECT value FROM core_meta WHERE key='schema_version'"
            ).fetchone()[0]
            run_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='core_verification_runs'"
            ).fetchone()
            task_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(core_tasks)")
            }
        self.assertEqual(version, "1")
        self.assertIsNone(run_table)
        self.assertNotIn("verified_run_id", task_columns)

    def test_future_schema_version_is_never_downgraded(self) -> None:
        store = CoreStore(self.db)
        store.initialize()
        with closing(sqlite3.connect(self.db)) as conn:
            before_events = conn.execute("SELECT COUNT(*) FROM core_events").fetchone()[0]
            conn.execute(
                "UPDATE core_meta SET value='999' WHERE key='schema_version'"
            )
            conn.commit()

        future = CoreStore(self.db)
        with self.assertRaisesRegex(SafeModeError, "newer than supported"):
            future.initialize()

        with closing(sqlite3.connect(self.db)) as conn:
            version = conn.execute(
                "SELECT value FROM core_meta WHERE key='schema_version'"
            ).fetchone()[0]
            after_events = conn.execute("SELECT COUNT(*) FROM core_events").fetchone()[0]
        self.assertEqual(version, "999")
        self.assertEqual(after_events, before_events)

    def test_schema_version_metadata_is_reserved_from_public_writes(self) -> None:
        store = CoreStore(self.db)
        store.initialize()
        with self.assertRaisesRegex(StoreError, "reserved"):
            store.set_meta(
                "schema_version",
                "1",
                event_type="hostile.schema.rollback",
                actor="hostile-fixture",
                payload={"attempted_version": 1},
            )
        self.assertEqual(store.get_meta("schema_version"), str(SCHEMA_VERSION))
        self.assertEqual(
            store.list_events(event_type="hostile.schema.rollback"), []
        )

    def test_direct_metadata_downgrade_with_m2_artifacts_fails_closed(self) -> None:
        store = CoreStore(self.db)
        store.initialize()
        with closing(sqlite3.connect(self.db)) as conn:
            before_events = conn.execute("SELECT COUNT(*) FROM core_events").fetchone()[0]
            conn.execute(
                "UPDATE core_meta SET value='1' WHERE key='schema_version'"
            )
            conn.commit()

        downgraded = CoreStore(self.db)
        with self.assertRaisesRegex(SafeModeError, "conflicts with M2 artifacts"):
            downgraded.initialize()
        valid, message = downgraded.verify_event_chain()
        self.assertFalse(valid)
        self.assertIn("conflicts with M2 artifacts", message)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT value FROM core_meta WHERE key='schema_version'"
                ).fetchone()[0],
                "1",
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM core_events").fetchone()[0],
                before_events,
            )

    def test_partial_m2_artifact_in_v1_database_is_not_migrated(self) -> None:
        create_m1_database(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                "ALTER TABLE core_tasks ADD COLUMN verification_profile_id TEXT"
            )
            conn.commit()

        with self.assertRaisesRegex(SafeModeError, "conflicts with M2 artifacts"):
            CoreStore(self.db).initialize()
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT value FROM core_meta WHERE key='schema_version'"
                ).fetchone()[0],
                "1",
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM core_events "
                    "WHERE event_type='schema.migrated'"
                ).fetchone()[0],
                0,
            )

    def test_fresh_database_starts_at_m2_without_fake_migration_history(self) -> None:
        store = CoreStore(self.db)
        store.initialize()
        self.assertEqual(store.get_meta("schema_version"), str(SCHEMA_VERSION))
        self.assertEqual(store.list_events(event_type="schema.migrated"), [])
        self.assertTrue(store.verify_event_chain()[0])

    def test_current_schema_rejects_same_name_but_wrong_unique_index(self) -> None:
        CoreStore(self.db).initialize()
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP INDEX idx_core_verification_one_running_repository")
            conn.execute(
                "CREATE INDEX idx_core_verification_one_running_repository "
                "ON core_verification_runs(task_id)"
            )
            conn.commit()

        with self.assertRaisesRegex(SafeModeError, "schema|integrity artifact"):
            CoreStore(self.db).initialize()

    def test_current_schema_rejects_same_name_but_permissive_trigger(self) -> None:
        CoreStore(self.db).initialize()
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TRIGGER core_verification_runs_terminal_no_update")
            conn.execute(
                """
                CREATE TRIGGER core_verification_runs_terminal_no_update
                BEFORE UPDATE ON core_verification_runs
                BEGIN
                    SELECT 1;
                END
                """
            )
            conn.commit()

        with self.assertRaisesRegex(SafeModeError, "schema|integrity artifact"):
            CoreStore(self.db).initialize()

    def test_current_schema_rejects_missing_verification_run_column(self) -> None:
        CoreStore(self.db).initialize()
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                "ALTER TABLE core_verification_runs "
                "RENAME COLUMN error_code TO error_detail"
            )
            conn.commit()

        with self.assertRaisesRegex(SafeModeError, "schema"):
            CoreStore(self.db).initialize()


if __name__ == "__main__":
    unittest.main()
