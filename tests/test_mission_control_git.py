"""Real-repository failure matrix for deterministic Mission Control Git state."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.git_service import CommandResult, GitService


NOW = "2026-07-15T12:00:00+00:00"


class GitFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.remote = root / "remote.git"
        self.seed = root / "seed"
        self.local = root / "local"
        self.other = root / "other"
        self._run(root, "init", "--bare", "--initial-branch=main", str(self.remote))
        self._run(root, "init", "--initial-branch=main", str(self.seed))
        self._config(self.seed)
        (self.seed / "state.txt").write_text("base\n", encoding="utf-8")
        self._git(self.seed, "add", "state.txt")
        self._git(self.seed, "commit", "-m", "base")
        self._git(self.seed, "remote", "add", "origin", str(self.remote))
        self._git(self.seed, "push", "-u", "origin", "main")
        self._run(root, "clone", str(self.remote), str(self.local))
        self._run(root, "clone", str(self.remote), str(self.other))
        self._config(self.local)
        self._config(self.other)

    def _config(self, repo: Path) -> None:
        self._git(repo, "config", "user.name", "Nero Test")
        self._git(repo, "config", "user.email", "nero-test@example.invalid")

    def commit(self, repo: Path, content: str, message: str) -> None:
        (repo / "state.txt").write_text(content, encoding="utf-8")
        self._git(repo, "add", "state.txt")
        self._git(repo, "commit", "-m", message)

    def push_other(self, content: str = "remote\n") -> None:
        self.commit(self.other, content, "remote change")
        self._git(self.other, "push", "origin", "main")

    def _git(self, repo: Path, *args: str, check: bool = True):
        return self._run(repo, "-C", str(repo), *args, check=check)

    @staticmethod
    def _run(cwd: Path, *args: str, check: bool = True):
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=check,
        )


class MissionControlGitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = GitFixture(self.root)
        self.service = GitService(clock=lambda: NOW, freshness_seconds=300)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def inspect(self, *, fetch: bool = True):
        state = self.service.inspect(self.fixture.local, fetch_remote=fetch)
        if fetch:
            self.receipt = state.fetch_receipt
            return state
        return self.service.inspect(
            self.fixture.local, fetch_receipt=getattr(self, "receipt", None)
        )

    def test_clean_relationship_names_both_branches(self) -> None:
        state = self.inspect()
        self.assertTrue(state.clean)
        self.assertEqual((state.ahead, state.behind), (0, 0))
        self.assertEqual(
            state.relationship,
            "Local branch main is 0 commits ahead and 0 commits behind upstream branch origin/main.",
        )
        self.assertEqual(state.authentication, "fetch_authenticated")
        self.assertTrue(state.remote_state_fresh)

    def test_dirty_and_untracked_counts(self) -> None:
        (self.fixture.local / "state.txt").write_text("dirty\n", encoding="utf-8")
        (self.fixture.local / "new.txt").write_text("new\n", encoding="utf-8")
        state = self.inspect()
        self.assertFalse(state.clean)
        self.assertEqual(state.modified_count, 1)
        self.assertEqual(state.untracked_count, 1)
        self.assertTrue(state.pending_commit)

    def test_ahead(self) -> None:
        self.fixture.commit(self.fixture.local, "local\n", "local change")
        state = self.inspect()
        self.assertEqual((state.ahead, state.behind), (1, 0))
        self.assertTrue(state.pending_push)
        self.assertIn("main is 1 commit ahead", state.relationship)

    def test_behind(self) -> None:
        self.fixture.push_other()
        state = self.inspect()
        self.assertEqual((state.ahead, state.behind), (0, 1))
        self.assertIn("1 commit behind upstream branch origin/main", state.relationship)

    def test_diverged(self) -> None:
        self.fixture.commit(self.fixture.local, "local\n", "local change")
        self.fixture.push_other("remote\n")
        state = self.inspect()
        self.assertEqual((state.ahead, state.behind), (1, 1))
        self.assertTrue(state.diverged)

    def test_conflict(self) -> None:
        self.fixture.commit(self.fixture.local, "local\n", "local change")
        self.fixture.push_other("remote\n")
        self.fixture._git(self.fixture.local, "fetch", "origin")
        merge = self.fixture._git(
            self.fixture.local, "merge", "origin/main", check=False
        )
        self.assertNotEqual(merge.returncode, 0)
        state = self.inspect(fetch=False)
        self.assertEqual(state.conflict_count, 1)
        self.assertEqual(state.conflict_files, ("state.txt",))

    def test_detached_head(self) -> None:
        self.fixture._git(self.fixture.local, "checkout", "--detach", "HEAD")
        state = self.inspect()
        self.assertTrue(state.detached_head)
        self.assertIsNone(state.branch)
        self.assertIn("Detached HEAD", state.relationship)

    def test_unavailable_remote(self) -> None:
        missing = self.root / "missing.git"
        self.fixture._git(
            self.fixture.local, "remote", "set-url", "origin", str(missing)
        )
        state = self.inspect()
        self.assertFalse(state.remote_available)
        self.assertEqual(state.authentication, "remote_unavailable")
        self.assertFalse(state.remote_state_fresh)
        self.assertTrue(any("fetch failed" in error for error in state.errors))

    def test_failed_authentication_is_distinct(self) -> None:
        real_runner = self.service.runner

        def auth_runner(args, cwd, timeout):
            if "fetch" in args:
                return CommandResult(128, "", "fatal: Authentication failed")
            return real_runner(args, cwd, timeout)

        state = GitService(runner=auth_runner, clock=lambda: NOW).inspect(
            self.fixture.local, fetch_remote=True
        )
        self.assertEqual(state.authentication, "authentication_failed")
        self.assertFalse(state.remote_available)

    def test_local_only_remote_only_and_common_worktree_key(self) -> None:
        self.fixture._git(self.fixture.local, "branch", "local-only")
        self.fixture._git(self.fixture.other, "checkout", "-b", "remote-only")
        self.fixture._git(self.fixture.other, "push", "-u", "origin", "remote-only")
        state = self.inspect()
        self.assertIn("local-only", state.local_only_branches)
        self.assertIn("origin/remote-only", state.remote_only_branches)

        extra = self.root / "extra-worktree"
        self.fixture._git(
            self.fixture.local, "worktree", "add", "-b", "extra", str(extra)
        )
        extra_state = self.service.inspect(
            extra, fetch_receipt=state.fetch_receipt
        )
        self.assertEqual(state.common_directory, extra_state.common_directory)
        self.assertGreaterEqual(len(extra_state.worktrees), 2)

    def test_no_fetch_means_no_remote_claim(self) -> None:
        state = self.service.inspect(self.fixture.local, fetch_remote=False)
        self.assertIsNone(state.ahead)
        self.assertIsNone(state.behind)
        self.assertFalse(state.remote_state_fresh)
        self.assertIn("until a successful fresh fetch", state.relationship)

    def test_fetch_uses_current_branch_tracking_remote_not_origin(self) -> None:
        upstream = self.root / "upstream.git"
        self.fixture._run(
            self.root, "init", "--bare", "--initial-branch=main", str(upstream)
        )
        self.fixture._git(self.fixture.seed, "remote", "add", "upstream", str(upstream))
        self.fixture._git(self.fixture.seed, "push", "upstream", "main")
        self.fixture._git(self.fixture.local, "remote", "add", "upstream", str(upstream))
        self.fixture._git(self.fixture.local, "fetch", "upstream")
        self.fixture._git(
            self.fixture.local,
            "branch",
            "--set-upstream-to=upstream/main",
            "main",
        )
        state = self.service.inspect(self.fixture.local, fetch_remote=True)
        self.assertEqual(state.remote_name, "upstream")
        self.assertEqual(state.upstream, "upstream/main")
        self.assertTrue(state.remote_state_fresh)
        self.assertEqual(state.fetch_receipt["tracking_remote"], "upstream")

    def test_receipt_is_rejected_when_remote_url_changes(self) -> None:
        fresh = self.inspect()
        replacement = self.root / "replacement.git"
        self.fixture._run(
            self.root, "init", "--bare", "--initial-branch=main", str(replacement)
        )
        self.fixture._git(
            self.fixture.local, "remote", "set-url", "origin", str(replacement)
        )
        state = self.service.inspect(
            self.fixture.local, fetch_receipt=fresh.fetch_receipt
        )
        self.assertFalse(state.remote_state_fresh)
        self.assertIsNone(state.ahead)
        self.assertTrue(any("does not match" in error for error in state.errors))

    def test_failed_fetch_receipt_invalidates_previous_success(self) -> None:
        fresh = self.inspect()
        self.fixture._git(
            self.fixture.local,
            "remote",
            "set-url",
            "origin",
            str(self.root / "missing.git"),
        )
        failed = self.service.inspect(
            self.fixture.local,
            fetch_remote=True,
            fetch_receipt=fresh.fetch_receipt,
        )
        self.assertFalse(failed.remote_state_fresh)
        self.assertFalse(failed.fetch_receipt["succeeded"])
        later = self.service.inspect(
            self.fixture.local, fetch_receipt=failed.fetch_receipt
        )
        self.assertFalse(later.remote_state_fresh)
        self.assertIsNone(later.ahead)
        self.assertEqual(later.authentication, "remote_unavailable")

    def test_authentication_result_survives_non_refresh_inspection(self) -> None:
        fresh = self.inspect()
        later = self.service.inspect(
            self.fixture.local, fetch_receipt=fresh.fetch_receipt
        )
        self.assertEqual(later.authentication, "fetch_authenticated")
        self.assertTrue(later.remote_state_fresh)

    def test_remote_url_credentials_are_redacted_from_state_and_errors(self) -> None:
        secret_url = (
            "https://alice:secret@example.invalid/repo.git?token=second#fragment"
        )
        self.fixture._git(
            self.fixture.local, "remote", "set-url", "origin", secret_url
        )
        real_runner = self.service.runner

        def failing_runner(args, cwd, timeout):
            if "fetch" in args:
                return CommandResult(
                    128, "", f"fatal: Authentication failed for '{secret_url}'"
                )
            return real_runner(args, cwd, timeout)

        state = GitService(runner=failing_runner, clock=lambda: NOW).inspect(
            self.fixture.local, fetch_remote=True
        )
        serialized = str(state.as_dict())
        self.assertEqual(state.remote_url, "https://example.invalid/repo.git")
        self.assertNotIn("alice", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("second", serialized)


if __name__ == "__main__":
    unittest.main()
