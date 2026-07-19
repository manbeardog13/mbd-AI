#!/usr/bin/env python3
"""Emit and verify the Windows path facts used by continuity CI."""
from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import shutil
import tempfile
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "continuity" / "continuityctl.py"
SPEC = importlib.util.spec_from_file_location("continuity_windows_path_probe", SCRIPT)
assert SPEC and SPEC.loader
CONTINUITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTINUITY)

INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF


def _converted_path(function, path: str) -> str | None:
    needed = function(path, None, 0)
    if not needed:
        return None
    buffer = ctypes.create_unicode_buffer(needed)
    written = function(path, buffer, needed)
    return buffer.value if written else None


def _existing_components(path: Path) -> list[Path]:
    components = []
    probe = path
    while True:
        if probe.exists() or probe.is_symlink():
            components.append(probe)
        if probe.parent == probe:
            break
        probe = probe.parent
    return list(reversed(components))


def main() -> int:
    if os.name != "nt":
        print(json.dumps({"ok": False, "error": "Windows-only verifier"}))
        return 2

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_attributes = kernel32.GetFileAttributesW
    get_attributes.argtypes = [wintypes.LPCWSTR]
    get_attributes.restype = wintypes.DWORD
    get_short = kernel32.GetShortPathNameW
    get_short.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_short.restype = wintypes.DWORD
    get_long = kernel32.GetLongPathNameW
    get_long.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_long.restype = wintypes.DWORD

    test_root = Path(tempfile.mkdtemp(prefix="continuity_test_probe_"))
    try:
        raw_db = str(test_root / "continuity.db")
        components = []
        divergences = []
        for component in _existing_components(Path(raw_db)):
            attributes = int(get_attributes(str(component)))
            if attributes == INVALID_FILE_ATTRIBUTES:
                raise OSError(ctypes.get_last_error(), f"attributes unavailable: {component}")
            lstat_attributes, tag = CONTINUITY._windows_reparse_metadata(component)
            if attributes != lstat_attributes:
                raise AssertionError(f"attribute API mismatch for {component}")
            normalized = os.path.normpath(str(component))
            resolved = os.path.realpath(str(component))
            if os.path.normcase(normalized) != os.path.normcase(resolved):
                divergences.append(
                    {"lexical": normalized, "resolved": resolved}
                )
            components.append(
                {
                    "path": str(component),
                    "attributes": f"0x{attributes:08X}",
                    "reparse": bool(attributes & CONTINUITY._FILE_ATTRIBUTE_REPARSE_POINT),
                    "reparse_tag": f"0x{tag:08X}" if tag else None,
                }
            )

        short_root = _converted_path(get_short, str(test_root))
        long_root = _converted_path(get_long, short_root or str(test_root))
        resolved_root = os.path.realpath(str(test_root))
        resolved_db = os.path.realpath(raw_db)
        validated_db = CONTINUITY.validate_db_path(raw_db)
        contained = CONTINUITY._path_is_within(
            resolved_db, resolved_root, windows=True
        )
        same_location = bool(
            short_root
            and long_root
            and os.path.normcase(os.path.realpath(short_root))
            == os.path.normcase(os.path.realpath(long_root))
        )
        actual_reparse = [row for row in components if row["reparse"]]
        validated_matches_resolved = (
            os.path.normcase(validated_db) == os.path.normcase(resolved_db)
        )
        result = {
            "ok": (
                contained
                and not actual_reparse
                and same_location
                and validated_matches_resolved
            ),
            "environment": {
                name: os.environ.get(name)
                for name in (
                    "TEMP",
                    "TMP",
                    "USERPROFILE",
                    "RUNNER_TEMP",
                    "GITHUB_WORKSPACE",
                )
            },
            "runner_workspace": os.environ.get("GITHUB_WORKSPACE"),
            "repository": str(ROOT),
            "test_created": True,
            "raw_database_path": raw_db,
            "normalized_database_path": os.path.abspath(raw_db),
            "short_test_root": short_root,
            "long_test_root": long_root,
            "resolved_test_root": resolved_root,
            "resolved_database_path": resolved_db,
            "validated_database_path": validated_db,
            "validated_matches_resolved": validated_matches_resolved,
            "contained_in_test_root": contained,
            "same_physical_location_via_short_and_long_names": same_location,
            "realpath_spelling_divergences": divergences,
            "components": components,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
