#!/usr/bin/env python3
"""Deterministic repository policy checks for Nero.

The tool is deliberately local and standard-library only. It never pushes,
pulls, commits, changes GitHub settings, or contacts a model. Network-changing
Git operations remain explicit human-approved commands.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "governance" / "repository-policy.json"
ZERO_SHA = "0" * 40


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str


def load_policy(path: Path = POLICY_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        policy = json.load(handle)
    if policy.get("schema_version") != 1:
        raise ValueError("unsupported repository policy schema")
    return policy


def git(args: Sequence[str], cwd: Path = ROOT, check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result


def current_branch(cwd: Path = ROOT) -> str | None:
    result = git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd)
    return result.stdout.strip() if result.returncode == 0 else None


def branch_allowed(branch: str, policy: dict) -> bool:
    if branch == policy["canonical_branch"]:
        return True
    return any(re.fullmatch(pattern, branch) for pattern in policy["allowed_branch_patterns"])


def remote_url_allowed(url: str, policy: dict) -> bool:
    return any(re.fullmatch(pattern, url) for pattern in policy["allowed_remote_url_patterns"])


def parse_push_lines(lines: Iterable[str]) -> list[tuple[str, str, str, str]]:
    updates: list[tuple[str, str, str, str]] = []
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f"malformed pre-push line {number}")
        updates.append((fields[0], fields[1], fields[2], fields[3]))
    return updates


def _is_ancestor(older: str, newer: str, cwd: Path = ROOT) -> bool:
    return git(["merge-base", "--is-ancestor", older, newer], cwd).returncode == 0


def _worktree_dirty(cwd: Path = ROOT) -> bool:
    return bool(git(["status", "--porcelain", "--untracked-files=all"], cwd, check=True).stdout)


def pre_push_findings(
    updates: Sequence[tuple[str, str, str, str]],
    remote_name: str,
    remote_url: str,
    policy: dict,
    cwd: Path = ROOT,
) -> list[Finding]:
    findings: list[Finding] = []
    expected_remote = policy["canonical_remote"]
    base_ref = f"{expected_remote}/{policy['canonical_branch']}"
    push_policy = policy["push"]

    if remote_name != expected_remote:
        findings.append(Finding("block", "remote-name", f"push remote must be {expected_remote}"))
    if not remote_url_allowed(remote_url, policy):
        findings.append(Finding("block", "remote-url", "push URL is not the canonical repository"))
    if push_policy["require_clean_worktree"] and _worktree_dirty(cwd):
        findings.append(Finding("block", "dirty-worktree", "commit or intentionally remove all worktree changes before push"))
    if git(["rev-parse", "--verify", "--quiet", base_ref], cwd).returncode:
        findings.append(Finding("block", "missing-base", f"missing {base_ref}; fetch explicitly before push"))

    active_branch = current_branch(cwd)
    for local_ref, local_sha, remote_ref, remote_sha in updates:
        if local_sha == ZERO_SHA:
            findings.append(Finding("block", "branch-delete", "branch deletion by push is forbidden"))
            continue
        if not remote_ref.startswith("refs/heads/"):
            findings.append(Finding("block", "tag-or-other-ref", "only branch refs may be pushed"))
            continue
        remote_branch = remote_ref.removeprefix("refs/heads/")
        if remote_branch in policy["protected_branches"]:
            findings.append(Finding("block", "protected-branch", f"direct push to {remote_branch} is forbidden"))
        if not branch_allowed(remote_branch, policy):
            findings.append(Finding("block", "branch-name", f"branch name is outside policy: {remote_branch}"))
        if not local_ref.startswith("refs/heads/"):
            findings.append(Finding("block", "detached-source", "push must originate from a named local branch"))
            continue
        local_branch = local_ref.removeprefix("refs/heads/")
        if push_policy["require_same_source_and_destination_branch"] and local_branch != remote_branch:
            findings.append(Finding("block", "refspec-rename", "source and destination branch names must match"))
        if active_branch != local_branch:
            findings.append(Finding("block", "non-head-push", "only the checked-out branch may be pushed"))
        if remote_sha != ZERO_SHA and not _is_ancestor(remote_sha, local_sha, cwd):
            findings.append(Finding("block", "non-fast-forward", "non-fast-forward and force pushes are forbidden"))
        if (
            push_policy["require_canonical_base_ancestor"]
            and git(["rev-parse", "--verify", "--quiet", base_ref], cwd).returncode == 0
            and not _is_ancestor(base_ref, local_sha, cwd)
        ):
            findings.append(Finding("block", "stale-base", f"{base_ref} is not an ancestor of the proposed push"))

    return findings


def audit_findings(policy: dict, cwd: Path = ROOT) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    remote = policy["canonical_remote"]
    canonical = policy["canonical_branch"]
    branch = current_branch(cwd)

    if branch is None:
        findings.append(Finding("block", "detached-head", "HEAD is detached"))
    elif not branch_allowed(branch, policy):
        findings.append(Finding("warn", "legacy-branch-name", f"current branch is outside the future naming policy: {branch}"))

    url_result = git(["remote", "get-url", remote], cwd)
    url = url_result.stdout.strip() if url_result.returncode == 0 else ""
    if not url:
        findings.append(Finding("block", "missing-remote", f"missing remote {remote}"))
    elif not remote_url_allowed(url, policy):
        findings.append(Finding("block", "remote-url", f"unexpected {remote} URL"))

    remote_head_result = git(["symbolic-ref", "--quiet", f"refs/remotes/{remote}/HEAD"], cwd)
    remote_head = remote_head_result.stdout.strip().removeprefix(f"refs/remotes/{remote}/") if remote_head_result.returncode == 0 else None
    if remote_head != canonical:
        findings.append(Finding("block", "remote-default", f"remote default resolves to {remote_head or 'unknown'}, expected {canonical}"))

    upstream_result = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd)
    upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else None
    if branch == canonical and upstream != f"{remote}/{canonical}":
        findings.append(Finding("block", "main-upstream", f"{canonical} must track {remote}/{canonical}"))
    elif branch and branch != canonical and upstream is None:
        findings.append(Finding("info", "no-upstream", "task branch has not been published"))

    dirty = _worktree_dirty(cwd)
    if dirty:
        findings.append(Finding("warn", "dirty-worktree", "worktree contains tracked or untracked changes"))

    base_ref = f"{remote}/{canonical}"
    ahead = behind = None
    if branch and git(["rev-parse", "--verify", "--quiet", base_ref], cwd).returncode == 0:
        counts = git(["rev-list", "--left-right", "--count", f"{base_ref}...HEAD"], cwd, check=True).stdout.split()
        behind, ahead = (int(counts[0]), int(counts[1]))
        if behind:
            findings.append(Finding("block", "base-divergence", f"HEAD is missing {behind} commit(s) from {base_ref}"))

    hooks_path = git(["config", "--get", "core.hooksPath"], cwd).stdout.strip()
    if hooks_path != ".githooks":
        findings.append(Finding("warn", "hooks-inactive", "tracked hooks are not active; set core.hooksPath=.githooks after review"))

    worktrees = git(["worktree", "list", "--porcelain"], cwd, check=True).stdout
    if "\nprunable" in worktrees:
        findings.append(Finding("warn", "prunable-worktree", "stale worktree metadata exists; review before pruning"))

    snapshot = {
        "branch": branch,
        "canonical_branch": canonical,
        "remote": remote,
        "remote_url": url,
        "remote_default": remote_head,
        "upstream": upstream,
        "dirty": dirty,
        "behind_canonical": behind,
        "ahead_of_canonical": ahead,
        "hooks_path": hooks_path or None,
    }
    return findings, snapshot


def _print_findings(findings: Sequence[Finding]) -> None:
    if not findings:
        print("PASS: repository policy checks found no issues")
        return
    for finding in findings:
        print(f"{finding.level.upper():5} {finding.code}: {finding.message}")


def cmd_audit(args: argparse.Namespace) -> int:
    policy = load_policy(Path(args.policy))
    findings, snapshot = audit_findings(policy, Path(args.cwd).resolve())
    if args.json:
        print(json.dumps({"snapshot": snapshot, "findings": [asdict(item) for item in findings]}, indent=2))
    else:
        _print_findings(findings)
    return 1 if any(item.level == "block" for item in findings) else 0


def cmd_pre_push(args: argparse.Namespace) -> int:
    policy = load_policy(Path(args.policy))
    try:
        updates = parse_push_lines(sys.stdin)
    except ValueError as exc:
        print(f"BLOCK pre-push-input: {exc}", file=sys.stderr)
        return 1
    findings = pre_push_findings(updates, args.remote_name, args.remote_url, policy, Path(args.cwd).resolve())
    _print_findings(findings)
    if findings:
        print("Push remains a separate Toni-approved action; this hook only enforces mechanical safety.", file=sys.stderr)
    return 1 if any(item.level == "block" for item in findings) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=str(ROOT), help="repository root")
    parser.add_argument("--policy", default=str(POLICY_PATH), help="policy JSON path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit", help="read-only local repository audit")
    audit_parser.add_argument("--json", action="store_true")
    audit_parser.set_defaults(func=cmd_audit)
    push_parser = subparsers.add_parser("pre-push", help="validate Git pre-push updates from stdin")
    push_parser.add_argument("remote_name")
    push_parser.add_argument("remote_url")
    push_parser.set_defaults(func=cmd_pre_push)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCK repoctl-error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
