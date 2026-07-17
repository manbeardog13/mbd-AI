#!/usr/bin/env python3
"""Deterministically verify the deployed Claude-lane Nero capsule.

The managed block in the user-global CLAUDE.md must be byte-identical to the
block in the repo canonical source (docs/host/NERO_CLAUDE_GLOBAL_CAPSULE.md).
Parallel to verify_nero_global_presence.py, which covers the Codex lane.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "docs" / "host" / "NERO_CLAUDE_GLOBAL_CAPSULE.md"
DEPLOYED = Path.home() / ".claude" / "CLAUDE.md"


def block(text: str, begin: str, end: str, source: str) -> str:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise AssertionError(f"{source}: capsule markers must occur exactly once")
    start = text.index(begin)
    finish = text.index(end, start) + len(end)
    return text[start:finish]


def main() -> int:
    checks = []
    ok = True
    try:
        canonical = CANONICAL.read_text(encoding="utf-8")
        found = re.search(r"<!-- (NERO_CLAUDE_GLOBAL_CAPSULE_V\d+):BEGIN -->", canonical)
        if not found:
            raise AssertionError("canonical capsule marker not found")
        name = found.group(1)
        begin, end = f"<!-- {name}:BEGIN -->", f"<!-- {name}:END -->"
        deployed = DEPLOYED.read_text(encoding="utf-8")
        if block(canonical, begin, end, "canonical") != block(deployed, begin, end, "deployed"):
            raise AssertionError(f"deployed {name} block differs from canonical source")
        checks.append({"check": f"{name} deployed byte-identical to canonical", "ok": True})
    except Exception as exc:  # deterministic verifier: report, never guess
        ok = False
        checks.append({"check": "claude capsule deployment", "ok": False, "error": str(exc)})
    print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
