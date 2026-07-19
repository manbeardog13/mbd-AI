from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "inboxctl.py"
SPEC = importlib.util.spec_from_file_location("nero_inbox_test", CLI)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class InboxTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows 8.3 aliases only")
    def test_authority_accepts_equivalent_short_and_long_windows_paths(self):
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            get_short_path = ctypes.WinDLL(
                "kernel32", use_last_error=True
            ).GetShortPathNameW
            get_short_path.argtypes = [
                wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD,
            ]
            get_short_path.restype = wintypes.DWORD
            buffer = ctypes.create_unicode_buffer(32768)
            written = get_short_path(str(root), buffer, len(buffer))
            if written == 0 or Path(buffer.value) == root:
                self.skipTest("8.3 aliases are unavailable on this volume")

            M._reject_link_components(Path(buffer.value) / "new" / "state.json", root)

    @unittest.skipUnless(os.name == "nt", "Windows case semantics only")
    def test_authority_accepts_windows_case_differences(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            M._reject_link_components(
                Path(str(root).swapcase()) / "new" / "state.json",
                root,
            )

    def test_authority_rejects_sibling_prefix_and_dotdot_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root = parent / "authority"
            sibling = parent / "authority-escape"
            root.mkdir()
            sibling.mkdir()
            with self.assertRaisesRegex(ValueError, "escapes"):
                M._reject_link_components(sibling / "state.json", root)
            with self.assertRaisesRegex(ValueError, "escapes"):
                M._reject_link_components(root / ".." / sibling.name / "state.json", root)

    def test_authority_allows_nonexistent_descendant(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            M._reject_link_components(root / "new" / "state.json", root)

    def test_authority_rejects_symlink_escape_where_supported(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td)
            root, outside = parent / "root", parent / "outside"
            root.mkdir()
            outside.mkdir()
            link = root / "redirect"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "link|escapes"):
                M._reject_link_components(link / "state.json", root)

    def test_posix_containment_remains_component_aware_and_case_sensitive(self):
        root = PurePosixPath("/srv/nero")
        self.assertEqual(
            M._relative_authority_parts(
                PurePosixPath("/srv/nero/inbox/state.json"), root, windows=False
            ),
            ("inbox", "state.json"),
        )
        for candidate in (
            PurePosixPath("/srv/nero-escape/state.json"),
            PurePosixPath("/srv/NERO/state.json"),
        ):
            with self.assertRaisesRegex(ValueError, "escapes"):
                M._relative_authority_parts(candidate, root, windows=False)

    def test_verifier_suite_green(self):
        r = subprocess.run([sys.executable, str(ROOT / "verify" / "verify_nero_inbox.py")],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-800:])

    def test_persistent_lock_file_is_reused(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "s.json"
            store = M.Store(state)
            lock = store.lock_path
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text("999999 0", encoding="ascii")
            with store.lock():
                self.assertTrue(lock.exists())
            self.assertTrue(lock.exists())
            with store.lock():
                pass  # kernel ownership, not pathname age, governs reuse

    def test_release_makes_lock_immediately_reacquirable(self):
        with tempfile.TemporaryDirectory() as td:
            store = M.Store(Path(td) / "s.json")
            with store.lock():
                self.assertTrue(store.lock_path.exists())
            started = time.monotonic()
            with store.lock():
                pass
            self.assertLess(time.monotonic() - started, 1.0)

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.json"
            p.write_text("[1,2,3]", encoding="utf-8")
            with self.assertRaises(ValueError):
                M.Store(p).load()

    def test_printable_strips_ansi(self):
        self.assertNotIn("\x1b", M.printable("a\x1b[31mred\x1b[0m b", 100))

    def test_legacy_familiar_write_surface_is_removed(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "must-not-exist.txt"
            result = subprocess.run(
                [sys.executable, str(CLI), "familiar", "--familiar-file",
                 str(target)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertFalse(target.exists())
            self.assertFalse(json.loads(result.stderr)["ok"])

    def test_feed_non_string_fields_fail_as_structured_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state, policies = root / "inbox.json", root / "policies.md"
            policies.write_text("---\nversion: 1.0.0\n---\n", encoding="utf-8")
            envelope = json.dumps({
                "v": 1, "provider": "adr", "event": "proposed",
                "id": "ADR-1", "title": "typed feed", "source_ref": 7,
            })
            env = os.environ.copy()
            env["NERO_INBOX_TEST_ROOT"] = str(root)
            result = subprocess.run(
                [sys.executable, str(CLI), "--state", str(state),
                 "--policies", str(policies), "feed"], input=envelope,
                capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            error = json.loads(result.stderr)
            self.assertFalse(error["ok"])
            self.assertIn("source_ref must be a string", error["error"])
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(state.exists())

    def test_failed_migration_backup_is_removed(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "inbox.json"
            with mock.patch.object(M.os, "fsync", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    M._write_backup(state, b"legacy bytes", 1)
            self.assertFalse(Path(f"{state}.v1.bak").exists())

    def test_state_reader_rejects_non_regular_file(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "inbox.json"
            state.mkdir()
            with self.assertRaisesRegex(ValueError, "regular non-link file"):
                M.Store(state).load()


if __name__ == "__main__":
    unittest.main()
