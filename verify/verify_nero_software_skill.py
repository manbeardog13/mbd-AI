#!/usr/bin/env python3
"""Verify canonical Nero engineering skill and user-host deployments."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


SKILL_NAME = "nero-software-engineering"
REQUIRED_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    "references/audit-playbook.md",
    "references/host-resource-routing.md",
    "references/language-routing.md",
    "references/specialist-routing.md",
    "references/translation-and-adaptation.md",
    "scripts/detect_stack.py",
}


def digest(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def inventory(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise FileNotFoundError(f"missing skill directory: {root}")
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        result[path.relative_to(root).as_posix()] = digest(path)
    return result


def compare(canonical: dict[str, str], deployed: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for missing in sorted(set(canonical) - set(deployed)):
        errors.append(f"missing deployed file: {missing}")
    for extra in sorted(set(deployed) - set(canonical)):
        errors.append(f"unexpected deployed file: {extra}")
    for name in sorted(set(canonical) & set(deployed)):
        if canonical[name] != deployed[name]:
            errors.append(f"content drift: {name}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(__file__).resolve().parents[1]
    canonical_root = repo / "skills" / SKILL_NAME
    home = Path.home()
    deployments = {
        "codex": home / ".codex" / "skills" / SKILL_NAME,
        "claude": home / ".claude" / "skills" / SKILL_NAME,
    }

    errors: list[str] = []
    try:
        canonical = inventory(canonical_root)
    except (OSError, FileNotFoundError) as exc:
        canonical = {}
        errors.append(str(exc))

    missing_required = sorted(REQUIRED_FILES - set(canonical))
    errors.extend(f"missing canonical file: {name}" for name in missing_required)

    skill_text = ""
    if (canonical_root / "SKILL.md").is_file():
        skill_text = (canonical_root / "SKILL.md").read_text(encoding="utf-8")
        if "[TODO" in skill_text:
            errors.append("SKILL.md still contains TODO placeholders")
        for phrase in (
            "Universal software engineering",
            "references/host-resource-routing.md",
            "references/translation-and-adaptation.md",
            "Never start Ollama",
        ):
            if phrase not in skill_text:
                errors.append(f"SKILL.md missing contract phrase: {phrase}")

    deployment_results: dict[str, object] = {}
    for host, root in deployments.items():
        try:
            deployed = inventory(root)
            host_errors = compare(canonical, deployed)
        except (OSError, FileNotFoundError) as exc:
            host_errors = [str(exc)]
        errors.extend(f"{host}: {message}" for message in host_errors)
        deployment_results[host] = {
            "path": str(root),
            "ok": not host_errors,
            "errors": host_errors,
        }

    result = {
        "ok": not errors,
        "canonical": str(canonical_root),
        "canonical_files": len(canonical),
        "deployments": deployment_results,
        "errors": errors,
    }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("PASS" if result["ok"] else "FAIL")
        print(f"canonical: {canonical_root} ({len(canonical)} files)")
        for host, details in deployment_results.items():
            print(f"{host}: {'PASS' if details['ok'] else 'FAIL'} - {details['path']}")
        for error in errors:
            print(f"- {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

