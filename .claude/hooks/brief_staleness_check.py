#!/usr/bin/env python3
"""Stop hook — standing rule: keep docs/PROJECT_BRIEF.md current.

Cross-platform (Windows / macOS / Linux) replacement for the old bash hook:
Windows has no working /bin/bash, so `bash <script>.sh` hit the WSL stub and
failed with "cannot execute binary file". This is pure Python + git, invoked the
same way on every OS.

When Claude stops with nothing left to do, if the project's source has changed
since PROJECT_BRIEF.md was last updated, remind Claude (exit 2 -> stderr) to
refresh the brief, commit+push it, and say so in chat. On turns that changed
nothing, exit 0 silently.
"""
from __future__ import annotations

import json
import subprocess
import sys

# Meaningful source whose change should prompt a brief refresh. Deliberately
# excludes PROJECT_BRIEF.md itself (so the hook never nags about its own fix).
SOURCE_PATHS = [
    "app", "verify", "tests", "bootstrap.py", "run.py", "config.example.yaml",
    "docs/VISION.md", "docs/DIRECTIVE.md",
]
BRIEF = "docs/PROJECT_BRIEF.md"


def _git(args: list[str]) -> str:
    """Run git, returning stripped stdout ('' on any failure)."""
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=15
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _commit_epoch(root: str, paths: list[str]) -> int:
    ts = _git(["-C", root, "log", "-1", "--format=%ct", "--", *paths])
    try:
        return int(ts)
    except (TypeError, ValueError):
        return 0


def main() -> int:
    raw = ""
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    # Recursion guard: don't re-fire on the stop caused by our own feedback.
    if data.get("stop_hook_active"):
        return 0

    root = _git(["rev-parse", "--show-toplevel"])
    if not root:
        return 0  # not a git repo -> nothing to check

    brief_t = _commit_epoch(root, [BRIEF])
    if brief_t == 0:
        return 0  # brief not tracked -> nothing to nag about

    if _commit_epoch(root, SOURCE_PATHS) > brief_t:
        sys.stderr.write(
            "Standing rule (keep the brief current): the project's source has "
            "changed since docs/PROJECT_BRIEF.md was last updated. Update "
            "docs/PROJECT_BRIEF.md to reflect the current state, commit and push "
            "it (merge to main), then tell Toni in chat that you've updated the "
            "brief.\n"
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
