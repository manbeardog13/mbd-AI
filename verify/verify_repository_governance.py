#!/usr/bin/env python3
"""Validate the repository-governance package without network or mutation."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/dependency-review.yml",
    ".github/workflows/codeql.yml",
    ".github/rulesets/main.json",
    ".githooks/pre-push",
    "governance/repository-policy.json",
    "governance/github/repository-settings.json",
    "scripts/repoctl.py",
    "docs/repository/GIT_POLICY.md",
    "docs/repository/MIGRATION_PLAN.md",
    "docs/orchestration/ROADMAP.md",
]


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        check((ROOT / relative).is_file(), f"missing {relative}", errors)

    policy = json.loads((ROOT / "governance/repository-policy.json").read_text(encoding="utf-8"))
    settings = json.loads((ROOT / "governance/github/repository-settings.json").read_text(encoding="utf-8"))
    ruleset = json.loads((ROOT / ".github/rulesets/main.json").read_text(encoding="utf-8"))
    check(policy["canonical_branch"] == "main", "canonical branch must be main", errors)
    check(policy["pull"]["strategy"] == "ff-only", "pull strategy must be ff-only", errors)
    check(not policy["push"]["allow_force_push"], "force push must be disabled", errors)
    check(settings["activation_requires_toni_approval"] is True, "remote activation must require Toni", errors)
    check(settings["repository_settings"]["allow_squash_merge"] is True, "squash merge must be enabled", errors)
    check(settings["repository_settings"]["allow_merge_commit"] is False, "merge commits must be disabled", errors)
    check(ruleset["enforcement"] == "disabled", "ruleset template must be disabled before approval", errors)
    check(ruleset.get("bypass_actors") == [], "ruleset must have no bypass actors", errors)

    rule_types = {rule["type"] for rule in ruleset["rules"]}
    for required_type in ("deletion", "non_fast_forward", "required_linear_history", "pull_request", "required_status_checks"):
        check(required_type in rule_types, f"ruleset missing {required_type}", errors)
    pull_rule = next(rule for rule in ruleset["rules"] if rule["type"] == "pull_request")
    check(pull_rule["parameters"]["allowed_merge_methods"] == ["squash"], "ruleset must be squash-only", errors)
    status_rule = next(rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks")
    contexts = {item["context"] for item in status_rule["parameters"]["required_status_checks"]}
    expected_contexts = {"repository-policy", "python-tests-3.13", "python-tests-3.14", "dependency-review"}
    check(contexts == expected_contexts, "required status checks drifted", errors)

    workflow_files = list((ROOT / ".github/workflows").glob("*.yml"))
    uses_pattern = re.compile(r"^\s*uses:\s*[^\s]+@([^\s#]+)", re.MULTILINE)
    for workflow in workflow_files:
        text = workflow.read_text(encoding="utf-8")
        check("pull_request_target:" not in text, f"unsafe trigger in {workflow.name}", errors)
        check("permissions:" in text, f"explicit permissions missing in {workflow.name}", errors)
        for ref in uses_pattern.findall(text):
            check(bool(re.fullmatch(r"[0-9a-f]{40}", ref)), f"action is not SHA-pinned in {workflow.name}: {ref}", errors)

    owners = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")
    for protected in ("/.github/", "/governance/", "/.githooks/", "/docs/CONSTITUTION.md"):
        check(protected in owners, f"CODEOWNERS missing {protected}", errors)

    hook = (ROOT / ".githooks/pre-push").read_text(encoding="utf-8")
    check("scripts/repoctl.py pre-push" in hook, "pre-push hook is not wired to repoctl", errors)

    if errors:
        print(json.dumps({"all_pass": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"all_pass": True, "checks": 13, "workflows": len(workflow_files)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
