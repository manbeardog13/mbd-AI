#!/usr/bin/env python3
"""Read-only verification for Nero School."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCHOOL = ROOT / "School"
TOOL = SCHOOL / "tooling" / "schoolctl.py"
BEGIN = "<!-- NERO_SCHOOL_SHARED_WORK_V1:BEGIN -->"
END = "<!-- NERO_SCHOOL_SHARED_WORK_V1:END -->"


def load_schoolctl():
    spec = importlib.util.spec_from_file_location("verify_schoolctl", TOOL)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load schoolctl")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def block(text: str) -> str:
    assert text.count(BEGIN) == 1 and text.count(END) == 1
    return text[text.index(BEGIN): text.index(END) + len(END)]


def main() -> int:
    checks = []
    schoolctl = load_schoolctl()
    try:
        result = schoolctl.command_verify(None)
        assert result["ok"], result["errors"]
        assert result["tasks"] == 14
        assert result["virtues"] >= 20
        checks.append({"check": "structure and hash chains", "ok": True})
    except Exception as exc:
        checks.append({"check": "structure and hash chains", "ok": False, "error": str(exc)})

    try:
        canonical = block((SCHOOL / "SHARED_WORK_RULES.md").read_text(encoding="utf-8"))
        codex = block((Path.home() / ".codex" / "AGENTS.md").read_text(encoding="utf-8"))
        claude = block((Path.home() / ".claude" / "CLAUDE.md").read_text(encoding="utf-8"))
        assert canonical == codex == claude
        checks.append({"check": "global shared-work rule deployment", "ok": True})
    except Exception as exc:
        checks.append({"check": "global shared-work rule deployment", "ok": False, "error": str(exc)})

    try:
        for task_json in SCHOOL.glob("[0-9][0-9]_*/*/task.json"):
            task = task_json.parent
            state = schoolctl.agreement_state(task)
            assert state["status"] == "PENDING"
            entries = schoolctl.entry_lines(task / "Task_agreement.txt")
            assert len(entries) == 1 and entries[0]["actor"] == "codex"
            assert not schoolctl.entry_lines(task / "AUDIT.txt")
        checks.append({"check": "honest Claude-pending agreements", "ok": True})
    except Exception as exc:
        checks.append({"check": "honest Claude-pending agreements", "ok": False, "error": str(exc)})

    try:
        executables = [TOOL, SCHOOL / "tooling" / "bootstrap_school.py", SCHOOL / "DEBATE CC" / "watch_debate.ps1"]
        forbidden = re.compile(r"\b(ollama|qwen|requests\.|urllib\.|httpx\.|socket\.)", re.I)
        for path in executables:
            assert not forbidden.search(path.read_text(encoding="utf-8")), f"forbidden runtime route in {path}"
        batch = (SCHOOL / "NERO_EXPERIENCE.bat").read_text(encoding="utf-8").lower()
        assert "dashboard --watch" in batch
        watcher = (SCHOOL / "DEBATE CC" / "START_DEBATE_WATCHER.bat").read_text(encoding="utf-8").lower()
        assert "watch_debate.ps1" in watcher
        checks.append({"check": "cold dashboard and opt-in watcher", "ok": True})
    except Exception as exc:
        checks.append({"check": "cold dashboard and opt-in watcher", "ok": False, "error": str(exc)})

    result = {"ok": all(row["ok"] for row in checks), "checks": checks}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
