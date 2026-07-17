from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "inboxctl.py"
SPEC = importlib.util.spec_from_file_location("nero_inbox_test", CLI)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class InboxTests(unittest.TestCase):
    def test_verifier_suite_green(self):
        r = subprocess.run([sys.executable, str(ROOT / "verify" / "verify_nero_inbox.py")],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-800:])

    def test_orphan_lock_heals(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "s.json"
            store = M.Store(state)
            lock = store.lock_path
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text("999999 0", encoding="ascii")
            old = time.time() - 400
            os.utime(lock, (old, old))
            with store.lock():
                pass  # stale lock broken by exactly one winner
            self.assertFalse(lock.exists())

    def test_release_is_ownership_checked(self):
        with tempfile.TemporaryDirectory() as td:
            store = M.Store(Path(td) / "s.json")
            with store.lock():
                # simulate a foreign process replacing our lock mid-hold
                store.lock_path.write_text("foreign-token", encoding="ascii")
            self.assertTrue(store.lock_path.exists())  # not ours: not deleted
            store.lock_path.unlink()

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.json"
            p.write_text("[1,2,3]", encoding="utf-8")
            with self.assertRaises(ValueError):
                M.Store(p).load()

    def test_printable_strips_ansi(self):
        self.assertNotIn("\x1b", M.printable("a\x1b[31mred\x1b[0m b", 100))


if __name__ == "__main__":
    unittest.main()
