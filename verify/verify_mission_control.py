#!/usr/bin/env python3
"""Offline verification for Nero Core and Mission Control Milestone 2."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    marker = "OK" if condition else "XX"
    print(f"  {marker} {name}{': ' + detail if detail else ''}")
    if not condition:
        FAILURES.append(name)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if not isinstance(node.func, ast.Attribute):
        return ""
    parts: list[str] = [node.func.attr]
    value = node.func.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _verification_runner_contract() -> None:
    path = ROOT / "app" / "core" / "verification.py"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        check("production verification module parses", False, str(exc))
        return

    imported_roots: set[str] = set()
    dangerous_calls: list[str] = []
    class_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_names.add(node.name)
        elif isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            if name in {
                "Popen",
                "run",
                "call",
                "check_call",
                "check_output",
                "os.system",
                "os.popen",
            } or name.startswith(("subprocess.", "os.spawn", "docker.")):
                dangerous_calls.append(name)

    forbidden_imports = imported_roots.intersection(
        {"subprocess", "docker", "anthropic", "openai", "ollama"}
    )
    check("verification.py source defines DisabledRunner", "DisabledRunner" in class_names)
    check("verification.py source contains no FakeRunner", "FakeRunner" not in class_names)
    check(
        "verification.py contains none of the prohibited import patterns",
        not forbidden_imports,
        ", ".join(sorted(forbidden_imports)),
    )
    check(
        "verification.py contains none of the prohibited process or Docker call patterns",
        not dangerous_calls,
        ", ".join(sorted(set(dangerous_calls))),
    )
    check(
        "verification.py source contains no literal Docker auto-start or image-pull command",
        all(
            token not in source.lower()
            for token in ("docker start", "docker pull", "start-service com.docker")
        ),
    )


def static_contract() -> None:
    required = (
        "app/core/contracts.py",
        "app/core/store.py",
        "app/core/git_service.py",
        "app/core/lease_registry.py",
        "app/core/scheduler.py",
        "app/core/adapters.py",
        "app/core/verification.py",
        "app/core/service.py",
        "mission_control/api.py",
        "mission_control/static/index.html",
        "run_mission_control.py",
        "docs/DESIGN-mission-control-m1.md",
        "docs/DESIGN-mission-control-m2.md",
        "docs/adr/0018-core-owned-verification.md",
    )
    for relative in required:
        check(f"required file {relative}", (ROOT / relative).is_file())

    policy = json.loads((ROOT / ".codex" / "nero-host.json").read_text(encoding="utf-8"))
    hooks = json.loads((ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    claude = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    disabled_keys = (
        "local_model_inference",
        "voice_enabled",
        "auto_speak",
        "desktop_voice_warmup",
        "background_processes",
        "project_server_startup",
        "memory_preload",
        "local_fallback",
    )
    check(
        "Host Presence local switches remain disabled",
        all(policy.get(key) is False for key in disabled_keys),
    )
    check("Codex startup hooks remain empty", hooks == {} or hooks == {"hooks": {}})
    check("Claude SessionStart remains absent", "SessionStart" not in claude.get("hooks", {}))

    api_source = (ROOT / "mission_control" / "api.py").read_text(encoding="utf-8")
    git_source = (ROOT / "app" / "core" / "git_service.py").read_text(encoding="utf-8")
    combined = api_source + "\n" + git_source
    for operation in ("push", "commit", "merge", "pull", "rebase", "reset", "checkout"):
        check(
            f"no {operation} API route or GitService method",
            f"def {operation}(" not in combined and f"/git/{operation}" not in combined,
        )

    _verification_runner_contract()


def run_suite() -> None:
    modules = (
        "tests.test_nero_core",
        "tests.test_repository_leases",
        "tests.test_mission_control_git",
        "tests.test_mission_control_service",
        "tests.test_mission_control_api",
        "tests.test_mission_control_m2_api",
        "tests.test_mission_control_static",
        "tests.test_mission_control_verification",
        "tests.test_mission_control_migrations",
    )
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", *modules],
        cwd=ROOT,
        text=True,
        check=False,
    )
    check(
        "Core, Git, orchestration, migration, verification, API, and interface suites",
        result.returncode == 0,
    )


def main() -> int:
    print("Nero Mission Control M2 — offline verification")
    static_contract()
    run_suite()
    print()
    if FAILURES:
        print(f"  {len(FAILURES)} check(s) FAILED: {', '.join(FAILURES)}")
        return 1
    print(
        "  Focused M2 checks passed. The shipped DisabledRunner did not execute "
        "repository verification. Tests intentionally targeted only disposable "
        "local repositories and remotes; no GitHub remote was configured."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
