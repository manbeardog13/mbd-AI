"""Deterministic Git intelligence with tracked-remote-bound fetch receipts.

The only Git metadata mutation supported here is an explicit fetch of the
validated tracked merge ref into the object database. Core binds the exact OID
from a strict remote advertisement and suppresses ``FETCH_HEAD`` writes. A
repository-controlled fetch refspec is never used. There are no commit, merge,
rebase, pull, reset, checkout, or push methods.
"""
from __future__ import annotations

import json
from hashlib import sha256
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
    remote_fingerprint: str | None
    upstream: str | None
    merge_ref: str | None
    upstream_oid: str | None
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
                remote_fingerprint=_optional_text(raw.get("remote_fingerprint")),
                upstream=_optional_text(raw.get("upstream")),
                merge_ref=_optional_text(raw.get("merge_ref")),
                upstream_oid=_optional_text(raw.get("upstream_oid")),
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
    isolated_git_environment = {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_SHALLOW_FILE",
        "GIT_NAMESPACE",
        "GIT_CEILING_DIRECTORIES",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_PREFIX",
        "GIT_SUPER_PREFIX",
        "GIT_INTERNAL_SUPER_PREFIX",
        "GIT_QUARANTINE_PATH",
        "GIT_REPLACE_REF_BASE",
        "GIT_GRAFT_FILE",
        "GIT_ATTR_SOURCE",
        "GIT_CONFIG",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_PARAMETERS",
        "GIT_CONFIG_COUNT",
        "GIT_EXEC_PATH",
        "GIT_EXTERNAL_DIFF",
        "GIT_DIFF_OPTS",
        "GIT_ALLOW_PROTOCOL",
        "GIT_SSH",
        "GIT_SSH_VARIANT",
    }
    for name in isolated_git_environment:
        environment.pop(name, None)
    for name in tuple(environment):
        if name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment.pop(name, None)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GCM_INTERACTIVE"] = "Never"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_SSH_COMMAND"] = "ssh -oBatchMode=yes"
    environment["GIT_NO_LAZY_FETCH"] = "1"
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
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
_REMOTE_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
_MERGE_REF_PATTERN = re.compile(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,239}")
_OBJECT_ID_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def _safe_remote_name(value: str) -> bool:
    """Reject option-like or ambiguous repository-controlled remote names."""

    text = str(value)
    return bool(
        _REMOTE_NAME_PATTERN.fullmatch(text)
        and ".." not in text
        and "//" not in text
        and not text.endswith(("/", ".lock"))
    )


def _safe_merge_ref(value: str | None) -> bool:
    text = str(value or "")
    return bool(
        _MERGE_REF_PATTERN.fullmatch(text)
        and ".." not in text
        and "//" not in text
        and not text.endswith(("/", ".", ".lock"))
    )


def _safe_object_id(value: str | None) -> bool:
    return bool(_OBJECT_ID_PATTERN.fullmatch(str(value or "")))


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
        requested_path = Path(requested)
        root_path = Path(root.strip()).resolve()
        if requested_path != root_path and root_path not in requested_path.parents:
            raise GitInspectionError(
                "Git returned a worktree outside the requested repository path"
            )
        common = self._required(
            root, "rev-parse", "--path-format=absolute", "--git-common-dir"
        )
        common = os.path.normcase(str(Path(common.strip()).resolve()))
        worktree = str(Path(root.strip()).resolve())
        errors: list[str] = []
        topology_trusted = True
        shallow = self._git(worktree, "rev-parse", "--is-shallow-repository")
        if shallow.returncode != 0 or shallow.stdout.strip() != "false":
            topology_trusted = False
            errors.append(
                "Git topology is shallow or could not be measured as complete"
            )
        grafts_path = Path(common) / "info" / "grafts"
        try:
            if grafts_path.is_file() and grafts_path.stat().st_size:
                topology_trusted = False
                errors.append("legacy Git graft topology is not trusted")
        except OSError:
            topology_trusted = False
            errors.append("legacy Git graft topology could not be inspected")

        branch_result = self._git(
            worktree, "symbolic-ref", "--quiet", "--short", "HEAD"
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
        detached = branch is None
        head_oid = self._optional(worktree, "rev-parse", "--verify", "HEAD")
        head = head_oid[:12] if head_oid else None
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

        remotes_result = self._git(worktree, "remote")
        if remotes_result.returncode != 0:
            errors.append(f"remote discovery failed: {self._message(remotes_result)}")
        discovered_remotes = self._lines(
            remotes_result.stdout if remotes_result.returncode == 0 else ""
        )
        unsafe_remotes = [
            remote for remote in discovered_remotes if not _safe_remote_name(remote)
        ]
        if unsafe_remotes:
            errors.append("unsafe Git remote name was ignored")
        remotes = [remote for remote in discovered_remotes if _safe_remote_name(remote)]
        configured_remote = (
            self._optional(worktree, "config", "--get", f"branch.{branch}.remote")
            if branch
            else None
        )
        merge_ref = (
            self._optional(worktree, "config", "--get", f"branch.{branch}.merge")
            if branch
            else None
        )
        if (
            upstream is None
            and configured_remote not in {None, "."}
            and _safe_remote_name(configured_remote)
            and _safe_merge_ref(merge_ref)
        ):
            upstream = (
                f"{configured_remote}/"
                + str(merge_ref).removeprefix("refs/heads/")
            )
        local_upstream = configured_remote == "."
        if upstream and not local_upstream and not _safe_merge_ref(merge_ref):
            errors.append("configured upstream merge ref is unavailable or unsafe")
        tracked_remote = self._tracking_remote(
            worktree,
            branch=branch,
            upstream=upstream,
            remotes=remotes,
            configured_remote=configured_remote,
        )
        if local_upstream:
            chosen_remote = None
        elif configured_remote is not None:
            chosen_remote = tracked_remote
            if chosen_remote is None:
                errors.append("configured branch remote is unavailable or unsafe")
        else:
            chosen_remote = (
                tracked_remote
                or (
                    preferred_remote
                    if preferred_remote in remotes
                    and _safe_remote_name(preferred_remote)
                    else None
                )
                or (remotes[0] if remotes else None)
            )
        raw_remote_url = None
        if chosen_remote:
            remote_url_result = self._git(
                worktree, "remote", "get-url", "--", chosen_remote
            )
            if remote_url_result.returncode == 0:
                raw_remote_url = remote_url_result.stdout.strip() or None
            else:
                errors.append(
                    f"remote URL lookup failed: {self._message(remote_url_result)}"
                )
        remote_url = redact_remote_url(raw_remote_url)
        remote_fingerprint = (
            sha256(raw_remote_url.encode("utf-8")).hexdigest()
            if raw_remote_url is not None
            else None
        )
        upstream_oid: str | None = None

        receipt = (
            fetch_receipt
            if isinstance(fetch_receipt, FetchReceipt)
            else FetchReceipt.parse(fetch_receipt)
        )
        receipt_oid_available = bool(
            receipt
            and (
                (not receipt.succeeded and receipt.upstream_oid is None)
                or (upstream is None and receipt.upstream_oid is None)
                or (
                    upstream is not None
                    and _safe_object_id(receipt.upstream_oid)
                    and self._git(
                        worktree,
                        "cat-file",
                        "-e",
                        f"{receipt.upstream_oid}^{{commit}}",
                    ).returncode
                    == 0
                )
            )
        )
        receipt_matches = bool(
            receipt
            and receipt.version == 2
            and receipt.repository_key == common
            and receipt.tracking_remote == chosen_remote
            and receipt.remote_url == remote_url
            and receipt.remote_fingerprint == remote_fingerprint
            and receipt.upstream == upstream
            and receipt.merge_ref == merge_ref
            and receipt_oid_available
        )
        upstream_oid = receipt.upstream_oid if receipt_matches and receipt else None
        if receipt and not receipt_matches:
            errors.append(
                "stored fetch receipt does not match the current repository, "
                "tracked remote, exact remote fingerprint, merge source, upstream, "
                "or fetched OID"
            )

        attempted_at = receipt.attempted_at if receipt_matches and receipt else None
        fetched_at = receipt.fetched_at if receipt_matches and receipt else None
        authentication = (
            receipt.authentication if receipt_matches and receipt else "not_checked"
        )
        fresh = bool(
            receipt_matches
            and receipt
            and receipt.succeeded
            and self._is_fresh(receipt.fetched_at)
        )
        remote_available: bool | None = True if fresh else None
        current_receipt = receipt if receipt_matches else None

        if fetch_remote:
            attempted_at = self.clock()
            if (
                not chosen_remote
                or raw_remote_url is None
                or upstream is None
                or not _safe_merge_ref(merge_ref)
            ):
                fresh = False
                fetched_at = None
                remote_available = None
                authentication = (
                    "not_configured"
                    if not chosen_remote
                    else "configuration_unreadable"
                )
                errors.append(
                    "branch tracks a local upstream, not a fetchable remote"
                    if local_upstream
                    else (
                        "no Git remote is configured"
                        if not chosen_remote
                        else "current branch has no safely measurable tracked merge ref"
                    )
                )
            else:
                advertised = self._git(
                    worktree,
                    "ls-remote",
                    "--upload-pack=git-upload-pack",
                    "--refs",
                    "--exit-code",
                    "--",
                    chosen_remote,
                    merge_ref,
                    timeout=45.0,
                )
                advertised_oid = (
                    self._advertised_ref_oid(advertised.stdout, merge_ref)
                    if advertised.returncode == 0
                    else None
                )
                advertisement_invalid = bool(
                    advertised.returncode == 0 and advertised_oid is None
                )
                if advertisement_invalid:
                    fetch = CommandResult(
                        128,
                        "",
                        "tracked merge ref advertisement was malformed",
                    )
                    authentication = "remote_response_invalid"
                elif advertised.returncode == 0:
                    fetch = self._git(
                        worktree,
                        "-c",
                        "fetch.writeCommitGraph=false",
                        "fetch",
                        "--upload-pack=git-upload-pack",
                        "--no-write-fetch-head",
                        "--no-tags",
                        "--no-prune",
                        "--no-recurse-submodules",
                        "--no-auto-maintenance",
                        "--no-auto-gc",
                        "--refmap=",
                        "--",
                        chosen_remote,
                        merge_ref,
                        timeout=45.0,
                    )
                else:
                    fetch = advertised
                if fetch.returncode == 0 and advertised_oid is not None:
                    fetched_at = attempted_at
                    fresh = True
                    remote_available = True
                    authentication = "fetch_succeeded"
                    upstream_oid = advertised_oid
                    if (
                        self._git(
                            worktree,
                            "cat-file",
                            "-e",
                            f"{upstream_oid}^{{commit}}",
                        ).returncode
                        != 0
                    ):
                        fresh = False
                        fetched_at = None
                        upstream_oid = None
                        errors.append(
                            "advertised upstream commit was not fetched exactly"
                        )
                else:
                    fetched_at = None
                    fresh = False
                    remote_available = (
                        None
                        if advertisement_invalid
                        else False
                    )
                    if not advertisement_invalid:
                        authentication = self._classify_fetch_failure(fetch)
                    errors.append(f"fetch failed: {self._message(fetch)}")
            current_receipt = FetchReceipt(
                version=2,
                repository_key=common,
                tracking_remote=chosen_remote,
                remote_url=remote_url,
                remote_fingerprint=remote_fingerprint,
                upstream=upstream,
                merge_ref=merge_ref,
                upstream_oid=upstream_oid,
                attempted_at=attempted_at,
                succeeded=fresh,
                fetched_at=fetched_at,
                authentication=authentication,
            )

        status = self._git(
            worktree,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--ignore-submodules=none",
            "--no-renames",
        )
        status_output_ok = (
            status.returncode == 0 and self._status_output_valid(status.stdout)
        )
        if status.returncode != 0:
            errors.append(f"status failed: {self._message(status)}")
        elif not status_output_ok:
            errors.append("Git returned malformed status output")
        entries = self._status_entries(status.stdout if status_output_ok else "")
        index_flags = self._git(worktree, "ls-files", "-v", "-z")
        hidden_index_flags: list[str] = []
        if index_flags.returncode != 0:
            errors.append(f"index flag inspection failed: {self._message(index_flags)}")
        else:
            for record in index_flags.stdout.split("\0"):
                if not record:
                    continue
                if len(record) < 3 or record[1] != " ":
                    errors.append("Git returned malformed index flag output")
                    hidden_index_flags = ["unreadable"]
                    break
                if record[0].islower() or record[0] == "S":
                    hidden_index_flags.append(record[2:])
            if hidden_index_flags:
                errors.append(
                    "assume-unchanged or skip-worktree index flags are not trusted"
                )
        untracked = sum(1 for code, _ in entries if code == "??")
        staged = sum(
            1 for code, _ in entries if code != "??" and code[0] not in (" ", "?")
        )
        modified = sum(1 for code, _ in entries if code != "??")
        conflict_codes = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
        conflicts = tuple(path for code, path in entries if code in conflict_codes)

        ahead: int | None = None
        behind: int | None = None
        if fresh and not topology_trusted:
            fresh = False
        if upstream and fresh and upstream_oid:
            counts = self._git(
                worktree,
                "rev-list",
                "--left-right",
                "--count",
                f"{upstream_oid}...HEAD",
            )
            if counts.returncode == 0:
                parts = counts.stdout.strip().split()
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    behind, ahead = int(parts[0]), int(parts[1])
                else:
                    errors.append("Git returned malformed ahead/behind counts")
                    fresh = False
            else:
                errors.append(f"ahead/behind failed: {self._message(counts)}")
                fresh = False
        elif upstream and fresh:
            errors.append("upstream OID is unavailable")
            fresh = False

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
        worktree_result = self._git(worktree, "worktree", "list", "--porcelain")
        worktrees = tuple(
            self._parse_worktrees(
                worktree_result.stdout if worktree_result.returncode == 0 else ""
            )
        )
        measured_worktree = next(
            (
                item
                for item in worktrees
                if item.get("worktree")
                and os.path.normcase(str(Path(str(item["worktree"])).resolve()))
                == os.path.normcase(str(Path(worktree).resolve()))
            ),
            None,
        )
        ending_branch_result = self._git(
            worktree, "symbolic-ref", "--quiet", "--short", "HEAD"
        )
        ending_branch = (
            ending_branch_result.stdout.strip()
            if ending_branch_result.returncode == 0
            else None
        )
        ending_head = self._optional(worktree, "rev-parse", "--verify", "HEAD")
        ending_configured_remote = (
            self._optional(worktree, "config", "--get", f"branch.{branch}.remote")
            if branch
            else None
        )
        ending_merge_ref = (
            self._optional(worktree, "config", "--get", f"branch.{branch}.merge")
            if branch
            else None
        )
        ending_remote_url = None
        if chosen_remote:
            ending_url_result = self._git(
                worktree, "remote", "get-url", "--", chosen_remote
            )
            if ending_url_result.returncode == 0:
                ending_remote_url = ending_url_result.stdout.strip() or None
        stable_identity = bool(
            measured_worktree
            and measured_worktree.get("HEAD") == head_oid
            and measured_worktree.get("branch") == branch
            and ending_branch == branch
            and ending_head == head_oid
            and ending_configured_remote == configured_remote
            and ending_merge_ref == merge_ref
            and ending_remote_url == raw_remote_url
        )
        inspection_ok = bool(
            status_output_ok
            and topology_trusted
            and index_flags.returncode == 0
            and not hidden_index_flags
            and worktree_result.returncode == 0
            and stable_identity
        )
        if worktree_result.returncode != 0:
            errors.append(f"worktree inspection failed: {self._message(worktree_result)}")
        elif not measured_worktree or not measured_worktree.get("HEAD"):
            errors.append("current worktree HEAD could not be measured")
        elif not stable_identity:
            errors.append(
                "worktree branch, HEAD, or tracked remote changed during Git inspection"
            )
            fresh = False
            ahead = None
            behind = None
            relationship = self.relationship_text(
                branch=ending_branch,
                upstream=upstream,
                ahead=None,
                behind=None,
                detached=ending_branch is None,
                head=ending_head[:12] if ending_head else None,
                fresh=False,
            )

        return GitState(
            repository=worktree,
            common_directory=common,
            worktree=worktree,
            branch=branch,
            detached_head=detached,
            upstream=upstream,
            tracked_merge_ref=merge_ref if _safe_merge_ref(merge_ref) else None,
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
            branch_inventory_scope="cached_local_refs_not_remote_verified",
            worktrees=worktrees,
            active_write_lease=active_write_lease,
            pending_commit=bool(entries),
            pending_push=(ahead > 0) if ahead is not None else None,
            inspection_ok=inspection_ok,
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
        configured_remote: str | None = None,
    ) -> str | None:
        del worktree
        if branch and configured_remote and configured_remote != ".":
            if configured_remote in remotes and _safe_remote_name(configured_remote):
                return configured_remote
        if upstream:
            matches = [
                remote for remote in remotes if upstream.startswith(f"{remote}/")
            ]
            if matches:
                return max(matches, key=len)
        return None

    def _git(self, cwd: str, *args: str, timeout: float = 15.0) -> CommandResult:
        return self.runner(
            (
                "git",
                "-C",
                cwd,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-c",
                "core.ignoreStat=false",
                "-c",
                "core.trustctime=true",
                "-c",
                "core.checkStat=default",
                "-c",
                "core.hooksPath=NUL",
                "-c",
                "core.sshCommand=ssh -oBatchMode=yes",
                "-c",
                "ssh.variant=ssh",
                "-c",
                "core.commitGraph=false",
                "-c",
                "protocol.allow=never",
                "-c",
                "protocol.file.allow=always",
                "-c",
                "protocol.https.allow=always",
                "-c",
                "protocol.ssh.allow=always",
                *args,
            ),
            cwd,
            timeout,
        )

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
    def _status_output_valid(raw: str) -> bool:
        return all(
            len(record) >= 4 and record[2] == " "
            for record in raw.split("\0")
            if record
        )

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
    def _advertised_ref_oid(raw: str, expected_ref: str) -> str | None:
        matches: list[str] = []
        for line in raw.splitlines():
            oid, separator, ref = line.strip().partition("\t")
            if not separator:
                parts = line.split(maxsplit=1)
                if len(parts) != 2:
                    continue
                oid, ref = parts
            if ref == expected_ref and _safe_object_id(oid):
                matches.append(oid)
        return matches[0] if len(matches) == 1 else None

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
