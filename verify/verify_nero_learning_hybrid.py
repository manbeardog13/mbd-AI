#!/usr/bin/env python3
"""Deterministically verify Nero's learning and dual-host skill deployment."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "skills"
DEPLOYMENTS = {
    "codex": Path.home() / ".codex" / "skills",
    "claude": Path.home() / ".claude" / "skills",
}
SKILLS = ("nero-continual-learning", "nero-hybrid-cognition")
def _capsule_markers() -> tuple[str, str]:
    """Derive the capsule marker version from the repo canonical source."""
    import re as _re
    canonical = (ROOT / "docs" / "NERO_CLAUDE_GLOBAL_CAPSULE.md").read_text(encoding="utf-8")
    found = _re.search(r"<!-- (NERO_CLAUDE_GLOBAL_CAPSULE_V\d+):BEGIN -->", canonical)
    if not found:
        raise AssertionError("canonical Claude capsule marker not found")
    name = found.group(1)
    return f"<!-- {name}:BEGIN -->", f"<!-- {name}:END -->"


BEGIN, END = _capsule_markers()


def managed_block(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise AssertionError("Claude capsule markers must occur exactly once")
    start = text.index(BEGIN)
    finish = text.index(END, start) + len(END)
    return text[start:finish]


def tree(path: Path) -> dict[str, bytes]:
    return {
        item.relative_to(path).as_posix(): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc"
    }


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_capsule() -> None:
    canonical_text = (ROOT / "docs" / "NERO_CLAUDE_GLOBAL_CAPSULE.md").read_text(
        encoding="utf-8"
    )
    deployed_path = Path.home() / ".claude" / "CLAUDE.md"
    deployed_text = deployed_path.read_text(encoding="utf-8")
    assert managed_block(canonical_text) == managed_block(deployed_text)
    assert deployed_text.index("# Ruflo Integration") < deployed_text.index(BEGIN)
    forbidden = ("ollama serve", "qwen ", "nero_voice", "wake-nero", "localhost:8080")
    block = managed_block(deployed_text).lower()
    assert not any(term in block for term in forbidden)

    project = (ROOT / "CLAUDE.md").read_text(encoding="utf-8").lower()
    for required in (
        "hosted intelligence",
        "cold",
        "$nero-hybrid-cognition",
        "$nero-continual-learning",
        "explicit approval",
    ):
        assert required in project, f"project CLAUDE.md missing {required}"

    settings = ROOT / ".claude" / "settings.json"
    if settings.exists():
        payload = json.loads(settings.read_text(encoding="utf-8"))
        for event in payload.get("hooks", {}).values():
            for matcher in event:
                for hook in matcher.get("hooks", []):
                    command = str(hook.get("command", "")).lower()
                    assert not any(
                        term in command
                        for term in ("ollama", "qwen", "nero_voice", "wake-nero", "start-nero")
                    ), f"Claude hook starts a forbidden Nero runtime: {command}"


def verify_skills() -> None:
    for skill in SKILLS:
        source = CANONICAL / skill
        source_tree = tree(source)
        assert source_tree, f"canonical skill is empty: {skill}"
        for host, root in DEPLOYMENTS.items():
            assert tree(root / skill) == source_tree, f"{host} deployment drift: {skill}"

    continual = (CANONICAL / "nero-continual-learning" / "SKILL.md").read_text(
        encoding="utf-8"
    ).lower()
    hybrid = (CANONICAL / "nero-hybrid-cognition" / "SKILL.md").read_text(
        encoding="utf-8"
    ).lower()
    for required in ("explicitly approves", "quarantine", "never start ollama", "cold"):
        assert required in continual, f"continual skill missing {required}"
    for required in (
        "parallel-analysis",
        "build-review",
        "disjoint-build",
        "cannot start",
        "explicit approval",
    ):
        assert required in hybrid, f"hybrid skill missing {required}"


def verify_smoke() -> None:
    learning_module = load_module(
        CANONICAL / "nero-continual-learning" / "scripts" / "learning_ledger.py",
        "verify_nero_learning",
    )
    hybrid_module = load_module(
        CANONICAL / "nero-hybrid-cognition" / "scripts" / "hybrid_brain.py",
        "verify_nero_hybrid",
    )
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        ledger_path = directory / "learning.json"
        state_path = directory / "hybrid.json"
        ledger = learning_module.Ledger(ledger_path)
        brain = hybrid_module.Brain(state_path)
        assert not ledger.status()["exists"] and not ledger_path.exists()
        assert not brain.status()["exists"] and not state_path.exists()

        task = brain.create(
            objective="Compare independent bounded findings",
            acceptance="Both lanes submit checks",
            topology="parallel-analysis",
            task_kind="verification",
            task_tags="verification,python",
            references="tests",
            builder="codex",
            codex_scope=None,
            claude_scope=None,
        )
        for host in ("codex", "claude"):
            brain.claim(task_id=task["id"], host=host, lease_minutes=5)
            brain.submit(
                task_id=task["id"],
                host=host,
                summary=f"{host} result",
                evidence="test-output",
                checks="smoke pass",
                risks="none observed",
                files="",
                verdict=None,
            )
        assert brain.ready(task_id=task["id"])["ready"]
        approved = brain.approve(
            task_id=task["id"],
            approved=True,
            quality=0.9,
            decision_note="Evidence gate passed.",
            learning_ledger=str(ledger_path),
        )
        assert approved["learning"]["ok"]
        assert len(ledger.load()["episodes"]) == 3
        assert ledger.audit()["ok"] and brain.audit()["ok"]


def main() -> int:
    checks = []
    for name, function in (
        ("Claude capsule", verify_capsule),
        ("skill deployments", verify_skills),
        ("learning + hybrid smoke", verify_smoke),
    ):
        try:
            function()
            checks.append({"check": name, "ok": True})
        except Exception as exc:
            checks.append({"check": name, "ok": False, "error": str(exc)})
    result = {"ok": all(row["ok"] for row in checks), "checks": checks}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
