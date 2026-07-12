#!/usr/bin/env python3
"""Self-test for the fs.read capability — jailed, bounded, read-only.

Fully offline (temp dir). Proves: reads a file in the jail, refuses directories
and binaries, truncates large files, and — through the registry — a path escaping
the jail is gated (HIGH, denied without confirm) so it never leaks. Exit 0 = pass.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capabilities import Context, Registry  # noqa: E402
from app.capabilities.builtin import register_builtins  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


def main() -> int:
    d = Path(tempfile.mkdtemp())
    (d / "hello.txt").write_text("hi Toni", encoding="utf-8")
    (d / "sub").mkdir()
    (d / "blob.bin").write_bytes(b"\x00\x01binary\x00")
    (d / "big.txt").write_text("x" * 300_000, encoding="utf-8")

    reg = Registry()
    register_builtins(reg)
    check("fs.read is registered as a built-in", reg.get("fs.read") is not None)

    ctx = Context(allowed_dirs=[str(d)])
    r = reg.dispatch("fs.read", {"path": "hello.txt"}, ctx)
    check("reads a file in the jail", r.ok and "hi Toni" in r.output)

    check("missing file fails cleanly",
          not reg.dispatch("fs.read", {"path": "nope.txt"}, ctx).ok)
    check("directory is rejected",
          not reg.dispatch("fs.read", {"path": "sub"}, ctx).ok)
    check("binary file is refused",
          not reg.dispatch("fs.read", {"path": "blob.bin"}, ctx).ok)

    big = reg.dispatch("fs.read", {"path": "big.txt"}, ctx)
    check("large file is truncated", big.ok and big.data.get("truncated"))

    denied = reg.dispatch("fs.read", {"path": "/etc/passwd"},
                          Context(allowed_dirs=[str(d)], confirm=None))
    check("out-of-jail read is gated (HIGH, denied without confirm)",
          (not denied.ok) and denied.data.get("denied") and denied.data.get("risk") == "high")

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  fs.read verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
