"""Deterministic Git intelligence with tracked-remote-bound fetch receipts.

The only Git metadata mutation supported here is an explicit
``git fetch --prune <tracked-remote>``. There are no commit, merge, rebase,
pull, reset, checkout, or push methods.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from .contracts import GitState


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class FetchReceipt:
    version: int
    repository_key: str
    tracking_remote: str | None
    remote_url: str | None
    upstream: str | None
    attempted_at: str
    succeeded: bool
    fetched_at: str | None
    authentication: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def parse(cls, value: Mapping[str, Any] | str | None) -> FetchReceipt | None:
        if value is None:
            return None
        try:
            raw = json.loads(value) if isinstance(value, str) else dict(value)
            return cls(
                version=int(raw["version"]),
                repository_key=str(raw["repository_key"]),
                tracking_remote=_optional_text(raw.get("tracking_remote")),
                remote_url=_optional_text(raw.get("remote_url")),
                upstream=_optional_text(raw.get("upstream")),
                attempted_at=str(raw["attempted_at"]),
                succeeded=bool(raw["succeeded"]),
                fetched_at=_optional_text(raw.get("fetched_at")),
                authentication=str(raw["authentication"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None


Runner = Callable[[Sequence[str], str, float], CommandResult]


class GitInspectionError(RuntimeError):
    """Raised when a path is not an inspectable Git worktree."""


def _default_runner(args: Sequence[str], cwd: str, timeout: float) -> CommandResult:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GCM_INTERACTIVE"] = "Never"
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
            env=environment,
        )
        return CommandResult(result.returncode, result.stdout, result.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(128, "", str(exc))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def redact_remote_url(value: str | None) -> str | None:
    """Remove credentials, query strings, and fragments from a Git remote URL."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if "://" in text:
        try:
            parts = urlsplit(text)
            host = parts.hostname or ""
            if parts.port is not None:
                host = f"{host}:{parts.port}"
            return urlunsplit((parts.scheme, host, parts.path, "", ""))
        except (ValueError, TypeError):
            return "[redacted remote URL]"
    scp = re.fullmatch(r"[^@/\s]+@([^:\s]+):(.+)", text)
    if scp:
        return f"{scp.group(1)}:{scp.group(2)}"
    return text.split("?", 1)[0].split("#", 1)[0]


_URL_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"<>]+")
_SCP_PATTERN = re.compile(r"(?<![\w.-])[^@/\s]+@[^:\s]+:[^\s'\"<>]+")


def redact_git_text(value: str) -> str:
    """Best-effort redaction for remote URLs echoed by Git diagnostics."""

    def safe_url(match: re.Match[str]) -> str:
        return redact_remote_url(match.group(0)) or "[redacted remote URL]"

    text = _URL_PATTERN.sub(safe_url, value)
    return _SCP_PATTERN.sub(safe_url, text)


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
        preferred_remote: str = "origin",
        fetch_receipt: FetchReceipt | Mapping[str, Any] | str | None = None,
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

        branch_result = self._git(
            worktree, "symbolic-ref", "--quiet", "--short", "HEAD"
        )
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

        remotes = self._lines(self._git(worktree, "remote").stdout)
        tracked_remote = self._tracking_remote(
            worktree, branch=branch, upstream=upstream, remotes=remotes
        )
        chosen_remote = (
            tracked_remote
            or (preferred_remote if preferred_remote in remotes else None)
            or (remotes[0] if remotes else None)
        )
        raw_remote_url = None
        if chosen_remote:
            remote_url_result = self._git(
                worktree, "remote", "get-url", chosen_remote
            )
            if remote_url_result.returncode == 0:
                raw_remote_url = remote_url_result.stdout.strip() or None
        remote_url = redact_remote_url(raw_remote_url)

        receipt = (
            fetch_receipt
            if isinstance(fetch_receipt, FetchReceipt)
            else FetchReceipt.parse(fetch_receipt)
        )
        receipt_matches = bool(
            receipt
            and receipt.version == 1
            and receipt.repository_key == common
            and receipt.tracking_remote == chosen_remote
            and receipt.remote_url == remote_url
            and receipt.upstream == upstream
        )
        if receipt and not receipt_matches:
            errors.append(
                "stored fetch receipt does not match the current repository, "
                "tracked remote, remote URL, or upstream"
            )

        attempted_at = receipt.attempted_at if receipt_matches and receipt else None
        fetched_at = receipt.fetched_at if receipt_matches and receipt else None
        authentication = (
            receipt.authentication if receipt_matches and receipt else "not_checked"
        )
        remote_available: bool | None = (
            receipt.succeeded if receipt_matches and receipt else None
        )
        fresh = bool(
            receipt_matches
            and receipt
            and receipt.succeeded
            and self._is_fresh(receipt.fetched_at)
        )
        current_receipt = receipt if receipt_matches else None

        if fetch_remote:
            attempted_at = self.clock()
            if not chosen_remote:
                fresh = False
                fetched_at = None
                remote_available = False
                authentication = "not_configured"
                errors.append("no Git remote is configured")
            else:
                fetch = self._git(
                    worktree, "fetch", "--prune", chosen_remote, timeout=45.0
                )
                if fetch.returncode == 0:
                    fetched_at = attempted_at
                    fresh = True
                    remote_available = True
                    authentication = "fetch_authenticated"
                else:
                    fetched_at = None
                    fresh = False
                    remote_available = False
                    authentication = self._classify_fetch_failure(fetch)
                    errors.append(f"fetch failed: {self._message(fetch)}")
            current_receipt = FetchReceipt(
                version=1,
                repository_key=common,
                tracking_remote=chosen_remote,
                remote_url=remote_url,
                upstream=upstream,
                attempted_at=attempted_at,
                succeeded=fresh,
                fetched_at=fetched_at,
                authentication=authentication,
            )

        status = self._git(
            worktree, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
        if status.returncode != 0:
            errors.append(f"status failed: {self._message(status)}")
        entries = self._status_entries(status.stdout if status.returncode == 0 else "")
        untracked = sum(1 for code, _ in entries if code == "??")
        staged = sum(
            1 for code, _ in entries if code != "??" and code[0] not in (" ", "?")
        )
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
            local_only = tuple(
                sorted(item for item in local_branches if item not in remote_short)
            )
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
        worktrees = tuple(
            self._parse_worktrees(
                self._git(worktree, "worktree", "list", "--porcelain").stdout
            )
        )

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
            last_fetch_attempt_at=attempted_at,
            fetch_receipt=current_receipt.as_dict() if current_receipt else None,
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
            return (
                f"Detached HEAD at {head or 'unknown commit'}; "
                "no local branch is checked out."
            )
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
            f"and {behind} {GitService._commits(behind)} behind upstream branch "
            f"{upstream}."
        )

    def _tracking_remote(
        self,
        worktree: str,
        *,
        branch: str | None,
        upstream: str | None,
        remotes: list[str],
    ) -> str | None:
        if branch:
            configured = self._optional(
                worktree, "config", "--get", f"branch.{branch}.remote"
            )
            if configured and configured != "." and configured in remotes:
                return configured
        if upstream:
            matches = [
                remote for remote in remotes if upstream.startswith(f"{remote}/")
            ]
            if matches:
                return max(matches, key=len)
        return None

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
        raw = (
            result.stderr
            or result.stdout
            or f"git exited {result.returncode}"
        ).strip()
        return redact_git_text(raw)

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
