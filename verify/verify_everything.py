#!/usr/bin/env python3
"""Run every verify_*.py in this folder and print one summary.

    python verify/verify_everything.py

This is Nero's top-level self-check. Each subsystem ships a `verify_<name>.py`
here; this runner discovers and runs them all, then reports.

Per-check exit codes (the contract every verify_*.py follows):
    0  = pass
    2  = skip (not applicable on this machine — e.g. no GPU in the cloud box)
    other = fail

This runner exits non-zero if any check FAILED (skips don't fail the run).
Run it inside the project's virtualenv so app imports resolve:
    Windows:  .venv\\Scripts\\python verify\\verify_everything.py
    Unix:     .venv/bin/python verify/verify_everything.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELF = Path(__file__).name


def main() -> int:
    scripts = sorted(p for p in HERE.glob("verify_*.py") if p.name != SELF)
    if not scripts:
        print("No verify_*.py scripts found.")
        return 0

    results: list[tuple[str, str]] = []
    for script in scripts:
        print("\n" + "=" * 60)
        print(f"  {script.name}")
        print("-" * 60)
        code = subprocess.run([sys.executable, str(script)]).returncode
        status = {0: "PASS", 2: "SKIP"}.get(code, "FAIL")
        results.append((script.name, status))

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    mark = {"PASS": "OK  ", "SKIP": "  . ", "FAIL": "XX  "}
    for name, status in results:
        print(f"  {mark[status]}{status:<5} {name}")
    print("=" * 60)

    failed = [name for name, status in results if status == "FAIL"]
    skipped = [name for name, status in results if status == "SKIP"]
    if failed:
        print(f"  {len(failed)} FAILED: {', '.join(failed)}")
        return 1
    if skipped:
        print(f"  All good. ({len(skipped)} skipped as not-applicable here.)")
    else:
        print("  All checks passed. Nero is healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
