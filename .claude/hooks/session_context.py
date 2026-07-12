#!/usr/bin/env python3
"""SessionStart hook — rebuild context from the repository, not from chat.

Injects a short reminder (per docs/ARCHITECT_MEMORY.md's startup procedure) so
every new session begins by reading the repo's memory instead of relying on
conversational history. Cross-platform (python), mirroring the Stop hook.
"""
from __future__ import annotations

import json
import sys

CONTEXT = (
    "Rebuild context from the REPOSITORY — documentation is the project's memory; "
    "conversations are only discussions about it. Before making architectural "
    "decisions or writing code, read in order: docs/ARCHITECT_MEMORY.md (start "
    "here: vision, principles, architectural rules, standards, the map) -> "
    "docs/PROJECT_BRIEF.md (current snapshot) -> PROGRESS.md (shipped/next) -> "
    "docs/CONSTITUTION.md (the law) -> docs/adr/ (why) -> the relevant "
    "docs/DESIGN-* -> the subsystem's code, its tests, and its latest commits. "
    "If the docs and any chat history disagree, the repository wins until the docs "
    "are intentionally updated."
)


def main() -> int:
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()  # drain the session payload; we don't need it
    except Exception:
        pass
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": CONTEXT,
        }
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
