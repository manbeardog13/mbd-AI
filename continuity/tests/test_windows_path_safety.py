from __future__ import annotations

import ctypes
import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "continuity" / "continuityctl.py"
SPEC = importlib.util.spec_from_file_location("continuity_path_safety_test", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

DIRECTORY = getattr(stat, "FILE_ATTRIBUTE_DIRECTORY", 0x10)
REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
SYMLINK = getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C)
MOUNT_POINT = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)


def metadata(attributes=DIRECTORY, tag=0):
    return SimpleNamespace(st_file_attributes=attributes, st_reparse_tag=tag)


class WindowsPathSafetyTests(unittest.TestCase):
    def test_github_runner_style_short_alias_canonicalizes_within_authority(self):
        raw = r"C:\Users\RUNNER~1\AppData\Local\Temp\continuity_test_x\continuity.db"
        root = r"C:\Users\RUNNER~1\AppData\Local\Temp\continuity_test_x"

        def expand(path):
            return path.replace(r"C:\Users\RUNNER~1", r"C:\Users\runneradmin")

        resolved = M._canonical_windows_path(raw, root, realpath_fn=expand)
        self.assertEqual(
            resolved,
            r"C:\Users\runneradmin\AppData\Local\Temp\continuity_test_x\continuity.db",
        )
        self.assertTrue(M._path_is_within(resolved, expand(root), windows=True))

    @unittest.skipUnless(os.name == "nt", "requires Windows short-name APIs")
    def test_real_83_alias_is_not_misclassified_as_reparse(self):
        get_short = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
        get_short.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_short.restype = ctypes.c_uint32
        with tempfile.TemporaryDirectory(prefix="continuity runner fixture ") as td:
            buffer = ctypes.create_unicode_buffer(32768)
            written = get_short(td, buffer, len(buffer))
            if not written or os.path.normcase(buffer.value) == os.path.normcase(td):
                self.skipTest("volume did not assign an 8.3 alias")
            candidate = str(Path(buffer.value) / "continuity.db")
            resolved = M.validate_db_path(candidate)
            attributes, tag = M._windows_reparse_metadata(Path(buffer.value))
            self.assertFalse(attributes & REPARSE)
            self.assertEqual(tag, 0)
            self.assertEqual(os.path.realpath(resolved), os.path.realpath(candidate))

    def test_ordinary_windows_directory_attributes_are_allowed(self):
        attributes, tag = M._windows_reparse_metadata(
            Path("ordinary"), lstat_fn=lambda _path: metadata()
        )
        self.assertEqual((attributes, tag), (DIRECTORY, 0))
        M._reject_windows_reparse_points(
            [Path("ordinary")], metadata_fn=lambda _path: (attributes, tag)
        )

    def test_symlink_reparse_tag_is_rejected(self):
        with self.assertRaisesRegex(M.ContinuityError, "attributes=0x00000410 tag=0xA000000C"):
            M._reject_windows_reparse_points(
                [Path("link")], metadata_fn=lambda _path: (DIRECTORY | REPARSE, SYMLINK)
            )

    def test_junction_redirect_outside_authority_is_rejected(self):
        with self.assertRaisesRegex(M.ContinuityError, "A0000003"):
            M._reject_windows_reparse_points(
                [Path("junction")],
                metadata_fn=lambda _path: (DIRECTORY | REPARSE, MOUNT_POINT),
            )

    def test_nested_redirect_is_rejected(self):
        chain = [Path("root"), Path("root") / "safe", Path("root") / "safe" / "link"]

        def inspect(path):
            if path.name == "link":
                return DIRECTORY | REPARSE, SYMLINK
            return DIRECTORY, 0

        with self.assertRaises(M.ContinuityError):
            M._reject_windows_reparse_points(chain, metadata_fn=inspect)

    def test_unknown_reparse_tag_fails_closed(self):
        with self.assertRaisesRegex(M.ContinuityError, "DEADBEEF"):
            M._reject_windows_reparse_points(
                [Path("unknown")],
                metadata_fn=lambda _path: (DIRECTORY | REPARSE, 0xDEADBEEF),
            )

    def test_reparse_inserted_during_alias_resolution_fails_closed(self):
        calls = 0

        def reject(_existing):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise M.ContinuityError("UNAVAILABLE", "reparse inserted")

        with self.assertRaisesRegex(M.ContinuityError, "inserted"):
            M._validate_windows_path(
                r"C:\root\child\continuity.db",
                [Path("child")],
                reject_fn=reject,
                canonical_fn=lambda candidate, _root: candidate,
            )
        self.assertEqual(calls, 2)

    def test_missing_existing_authority_fails_closed(self):
        with self.assertRaisesRegex(M.ContinuityError, "no existing path authority"):
            M._validate_windows_path(r"Z:\missing\continuity.db", [])

    def test_sibling_prefix_is_not_contained(self):
        self.assertFalse(
            M._path_is_within(r"C:\authority-evil\db.sqlite", r"C:\authority", windows=True)
        )

    def test_windows_containment_is_case_insensitive(self):
        self.assertTrue(
            M._path_is_within(r"C:\AUTHORITY\child\db.sqlite", r"c:\authority", windows=True)
        )

    def test_dotdot_traversal_remains_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(M.ContinuityError, "traversal"):
                M.validate_db_path(str(Path(td) / ".." / "escape.db"))

    def test_nonexistent_child_beneath_normal_root_is_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            candidate = Path(td) / "future" / "continuity.db"
            resolved = M.validate_db_path(str(candidate))
            self.assertTrue(
                M._path_is_within(
                    os.path.realpath(resolved), os.path.realpath(td), windows=os.name == "nt"
                )
            )

    def test_posix_containment_remains_case_sensitive_and_component_aware(self):
        self.assertTrue(M._path_is_within("/authority/child/db", "/authority", windows=False))
        self.assertFalse(M._path_is_within("/authority-evil/db", "/authority", windows=False))
        self.assertFalse(M._path_is_within("/AUTHORITY/child/db", "/authority", windows=False))

    def test_windows_attribute_failure_is_fail_closed(self):
        with self.assertRaisesRegex(M.ContinuityError, "attributes unavailable"):
            M._windows_reparse_metadata(
                Path("missing-attributes"), lstat_fn=lambda _path: SimpleNamespace()
            )

    @unittest.skipUnless(os.name == "nt", "requires Windows symlink support")
    def test_real_symlink_redirect_outside_authority_is_rejected_when_supported(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "root"
            outside = Path(parent) / "outside"
            root.mkdir()
            outside.mkdir()
            link = root / "escape"
            try:
                os.symlink(outside, link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaises(M.ContinuityError):
                M.validate_db_path(str(link / "continuity.db"))


if __name__ == "__main__":
    unittest.main()
