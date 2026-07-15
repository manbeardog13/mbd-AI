"""Deterministic read-only Git intelligence for Mission Control.

The only metadata mutation supported here is an explicit ``git fetch --prune``.
There are no commit, merge, rebase, pull, reset, checkout, or push methods.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Sequence

from .contracts import GitState


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[Sequence[str], str, float], CommandResult]


class GitInspectionError(RuntimeError):
    """Raised when a path is not an inspectable Git worktree."""


def _default_runner(args: Sequence[str], cwd: str, timeout: float) -> CommandResult:
    try:
        result = subprocess.run(
            list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return CommandResult(result.returncode, result.stdout, result.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(128, "", str(exc))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class GitService:
    def __init__(
        self,
        *,
        runner: Runner = _default_runner,
        clock: Callable[[], str] = _now_iso,
        freshness_seconds: int = 300,
    ) -> None:
        self.runner = runner
        self.clock = clock
        self.freshness_seconds = max(1, int(freshness_seconds))

    def inspect(
        self,
        repository: str | Path,
        *,
        fetch_remote: bool = False,
        remote_name: str = "origin",
        last_fetch_at: str | None = None,
        active_write_lease: dict | None = None,
    ) -> GitState:
        requested = str(Path(repository).resolve())
        inside = self._git(requested, "rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            raise GitInspectionError(
                f"not a Git worktree: {requested}: {self._message(inside)}"
            )

        root = self._required(requested, "rev-parse", "--show-toplevel")
        common = self._required(
            root, "rev-parse", "--path-format=absolute", "--git-common-dir"
        )
        common = os.path.normcase(str(Path(common.strip()).resolve()))
        worktree = str(Path(root.strip()).resolve())
        errors: list[str] = []

        remotes = self._lines(self._git(worktree, "remote").stdout)
        chosen_remote = remote_name if remote_name in remotes else (remotes[0] if remotes else None)
        remote_url = None
        if chosen_remote:
            remote_url_result = self._git(worktree, "remote", "get-url", chosen_remote)
            if remote_url_result.returncode == 0:
                remote_url = remote_url_result.stdout.strip() or None

        fetched_at = last_fetch_at
        remote_available: bool | None = None
        authentication = "not_checked"
        fresh = self._is_fresh(last_fetch_at)
        if fetch_remote:
            if not chosen_remote:
                fresh = False
                remote_available = False
                authentication = "not_configured"
                errors.append("no Git remote is configured")
            else:
                fetch = self._git(
                    worktree, "fetch", "--prune", chosen_remote, timeout=45.0
                )
                if fetch.returncode == 0:
                    fetched_at = self.clock()
                    fresh = True
                    remote_available = True
                    authentication = "fetch_authenticated"
                else:
                    fresh = False
                    remote_available = False
                    authentication = self._classify_fetch_failure(fetch)
                    errors.append(f"fetch failed: {self._message(fetch)}")

        branch_result = self._git(worktree, "symbolic-ref", "--quiet", "--short", "HEAD")
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
        detached = branch is None
        head = self._optional(worktree, "rev-parse", "--short=12", "HEAD")
        upstream = None
        if branch:
            upstream_result = self._git(
                worktree,
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{upstream}",
            )
            if upstream_result.returncode == 0:
                upstream = upstream_result.stdout.strip() or None

        status = self._git(
            worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
        if status.returncode != 0:
            errors.append(f"status failed: {self._message(status)}")
        entries = self._status_entries(status.stdout if status.returncode == 0 else "")
        untracked = sum(1 for code, _ in entries if code == "??")
        staged = sum(1 for code, _ in entries if code != "??" and code[0] not in (" ", "?"))
        modified = sum(1 for code, _ in entries if code != "??")
        conflict_codes = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
        conflicts = tuple(path for code, path in entries if code in conflict_codes)

        ahead: int | None = None
        behind: int | None = None
        if upstream and fresh:
            counts = self._git(
                worktree,
                "rev-list",
                "--left-right",
                "--count",
                f"{upstream}...HEAD",
            )
            if counts.returncode == 0:
                parts = counts.stdout.strip().split()
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    behind, ahead = int(parts[0]), int(parts[1])
                else:
                    errors.append("Git returned malformed ahead/behind counts")
            else:
                errors.append(f"ahead/behind failed: {self._message(counts)}")

        relationship = self.relationship_text(
            branch=branch,
            upstream=upstream,
            ahead=ahead,
            behind=behind,
            detached=detached,
            head=head,
            fresh=fresh,
        )
        local_branches = self._lines(
            self._git(
                worktree, "for-each-ref", "--format=%(refname:short)", "refs/heads"
            ).stdout
        )
        remote_refs = [
            item
            for item in self._lines(
                self._git(
                    worktree,
                    "for-each-ref",
                    "--format=%(refname:short)",
                    "refs/remotes",
                ).stdout
            )
            if not item.endswith("/HEAD")
        ]
        if chosen_remote:
            remote_short = {
                item[len(chosen_remote) + 1 :]
                for item in remote_refs
                if item.startswith(f"{chosen_remote}/")
            }
            local_only = tuple(sorted(item for item in local_branches if item not in remote_short))
            remote_only = tuple(
                sorted(
                    item
                    for item in remote_refs
                    if item.startswith(f"{chosen_remote}/")
                    and item[len(chosen_remote) + 1 :] not in set(local_branches)
                )
            )
        else:
            local_only = tuple(sorted(local_branches))
            remote_only = tuple(sorted(remote_refs))

        last_commit = self._optional(
            worktree, "log", "-1", "--format=%h %s (%cI)"
        )
        worktrees = tuple(self._parse_worktrees(self._git(worktree, "worktree", "list", "--porcelain").stdout))

        return GitState(
            repository=worktree,
            common_directory=common,
            worktree=worktree,
            branch=branch,
            detached_head=detached,
            upstream=upstream,
            remote_name=chosen_remote,
            remote_url=remote_url,
            remote_available=remote_available,
            authentication=authentication,
            push_permission="untested",
            last_fetch_at=fetched_at,
            remote_state_fresh=fresh,
            ahead=ahead,
            behind=behind,
            relationship=relationship,
            clean=not entries,
            modified_count=modified,
            untracked_count=untracked,
            staged_count=staged,
            conflict_count=len(conflicts),
            conflict_files=conflicts,
            last_commit=last_commit,
            local_only_branches=local_only,
            remote_only_branches=remote_only,
            worktrees=worktrees,
            active_write_lease=active_write_lease,
            pending_commit=bool(entries),
            pending_push=(ahead > 0) if ahead is not None else None,
            errors=tuple(errors),
        )

    @staticmethod
    def relationship_text(
        *,
        branch: str | None,
        upstream: str | None,
        ahead: int | None,
        behind: int | None,
        detached: bool,
        head: str | None,
        fresh: bool,
    ) -> str:
        if detached:
            return f"Detached HEAD at {head or 'unknown commit'}; no local branch is checked out."
        if not branch:
            return "No local branch could be identified."
        if not upstream:
            return f"Local branch {branch} has no configured upstream branch."
        if not fresh or ahead is None or behind is None:
            return (
                f"Local branch {branch} tracks upstream branch {upstream}, but "
                "ahead/behind is unavailable until a successful fresh fetch."
            )
        return (
            f"Local branch {branch} is {ahead} {GitService._commits(ahead)} ahead "
            f"and {behind} {GitService._commits(behind)} behind upstream branch {upstream}."
        )

    def _git(self, cwd: str, *args: str, timeout: float = 15.0) -> CommandResult:
        return self.runner(("git", "-C", cwd, *args), cwd, timeout)

    def _required(self, cwd: str, *args: str) -> str:
        result = self._git(cwd, *args)
        if result.returncode != 0 or not result.stdout.strip():
            raise GitInspectionError(self._message(result))
        return result.stdout.strip()

    def _optional(self, cwd: str, *args: str) -> str | None:
        result = self._git(cwd, *args)
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def _is_fresh(self, timestamp: str | None) -> bool:
        if not timestamp:
            return False
        try:
            value = datetime.fromisoformat(timestamp)
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            now = datetime.fromisoformat(self.clock())
            if now.tzinfo is None:
                now = now.replace(tzinfo=UTC)
            age = (now.astimezone(UTC) - value.astimezone(UTC)).total_seconds()
            return 0 <= age <= self.freshness_seconds
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _status_entries(raw: str) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for record in raw.split("\0"):
            if len(record) < 4:
                continue
            code = record[:2]
            path = record[3:]
            if path:
                entries.append((code, path))
        return entries

    @staticmethod
    def _parse_worktrees(raw: str) -> list[dict[str, str | None]]:
        result: list[dict[str, str | None]] = []
        current: dict[str, str | None] = {}
        for line in [*raw.splitlines(), ""]:
            if not line:
                if current:
                    branch = current.get("branch")
                    if branch and branch.startswith("refs/heads/"):
                        current["branch"] = branch.removeprefix("refs/heads/")
                    result.append(current)
                    current = {}
                continue
            key, _, value = line.partition(" ")
            current[key] = value or None
        return result

    @staticmethod
    def _lines(raw: str) -> list[str]:
        return [line.strip() for line in raw.splitlines() if line.strip()]

    @staticmethod
    def _message(result: CommandResult) -> str:
        return (result.stderr or result.stdout or f"git exited {result.returncode}").strip()

    @staticmethod
    def _classify_fetch_failure(result: CommandResult) -> str:
        text = f"{result.stdout}\n{result.stderr}".lower()
        auth_markers = (
            "authentication failed",
            "could not read username",
            "permission denied",
            "repository not found",
            "access denied",
            "invalid username or password",
        )
        if any(marker in text for marker in auth_markers):
            return "authentication_failed"
        return "remote_unavailable"

    @staticmethod
    def _commits(value: int) -> str:
        return "commit" if value == 1 else "commits"
