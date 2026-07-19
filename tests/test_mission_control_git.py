"""Real-repository failure matrix for deterministic Mission Control Git state."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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
        self.assertEqual(state.authentication, "fetch_succeeded")
        self.assertTrue(state.remote_state_fresh)
        self.assertTrue(state.inspection_ok)
        self.assertEqual(state.fetch_receipt["version"], 2)
        self.assertEqual(len(state.fetch_receipt["remote_fingerprint"]), 64)
        self.assertEqual(len(state.fetch_receipt["upstream_oid"]), 40)

    def test_dirty_and_untracked_counts(self) -> None:
        (self.fixture.local / "state.txt").write_text("dirty\n", encoding="utf-8")
        (self.fixture.local / "new.txt").write_text("new\n", encoding="utf-8")
        state = self.inspect()
        self.assertFalse(state.clean)
        self.assertEqual(state.modified_count, 1)
        self.assertEqual(state.untracked_count, 1)
        self.assertTrue(state.pending_commit)

    def test_assume_unchanged_cannot_hide_a_modified_tracked_file(self) -> None:
        self.fixture._git(
            self.fixture.local,
            "update-index",
            "--assume-unchanged",
            "state.txt",
        )
        (self.fixture.local / "state.txt").write_text(
            "hidden tracked mutation\n",
            encoding="utf-8",
        )
        porcelain = self.fixture._git(
            self.fixture.local,
            "status",
            "--porcelain=v1",
        ).stdout
        self.assertEqual(porcelain, "")

        state = self.inspect()

        self.assertFalse(state.inspection_ok)
        self.assertTrue(
            any("assume-unchanged" in error for error in state.errors)
        )

    def test_submodule_ignore_all_cannot_hide_a_dirty_submodule(self) -> None:
        submodule_source = self.root / "submodule-source"
        self.fixture._run(
            self.root,
            "init",
            "--initial-branch=main",
            str(submodule_source),
        )
        self.fixture._config(submodule_source)
        (submodule_source / "payload.txt").write_text("base\n", encoding="utf-8")
        self.fixture._git(submodule_source, "add", "payload.txt")
        self.fixture._git(submodule_source, "commit", "-m", "submodule base")
        self.fixture._run(
            self.fixture.local,
            "-C",
            str(self.fixture.local),
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(submodule_source),
            "deps/sub",
        )
        self.fixture._git(self.fixture.local, "add", ".gitmodules", "deps/sub")
        self.fixture._git(self.fixture.local, "commit", "-m", "add submodule")
        self.fixture._git(
            self.fixture.local,
            "config",
            "submodule.deps/sub.ignore",
            "all",
        )
        (self.fixture.local / "deps" / "sub" / "payload.txt").write_text(
            "dirty\n",
            encoding="utf-8",
        )
        porcelain = self.fixture._git(
            self.fixture.local,
            "status",
            "--porcelain=v1",
        ).stdout
        self.assertEqual(porcelain, "")

        state = self.inspect()

        self.assertTrue(state.inspection_ok)
        self.assertFalse(state.clean)
        self.assertEqual(state.modified_count, 1)

    def test_branch_and_head_change_during_inspection_fails_closed(self) -> None:
        real_runner = self.service.runner
        switched = False

        def switching_runner(args, cwd, timeout):
            nonlocal switched
            result = real_runner(args, cwd, timeout)
            if not switched and "worktree" in args and "list" in args:
                switched = True
                self.fixture._git(
                    self.fixture.local,
                    "checkout",
                    "-b",
                    "inspection-race",
                )
                (self.fixture.local / "race.txt").write_text(
                    "late commit\n",
                    encoding="utf-8",
                )
                self.fixture._git(self.fixture.local, "add", "race.txt")
                self.fixture._git(
                    self.fixture.local,
                    "commit",
                    "-m",
                    "late inspection race",
                )
            return result

        state = GitService(runner=switching_runner, clock=lambda: NOW).inspect(
            self.fixture.local,
            fetch_remote=True,
        )

        self.assertTrue(switched)
        self.assertFalse(state.inspection_ok)
        self.assertFalse(state.remote_state_fresh)
        self.assertIsNone(state.ahead)
        self.assertIsNone(state.behind)
        self.assertTrue(
            any(
                "branch, HEAD, or tracked remote changed" in error
                for error in state.errors
            )
        )

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

    def test_cached_branch_inventory_and_common_worktree_key(self) -> None:
        self.fixture._git(self.fixture.local, "branch", "local-only")
        self.fixture._git(self.fixture.other, "checkout", "-b", "remote-only")
        self.fixture._git(self.fixture.other, "push", "-u", "origin", "remote-only")
        state = self.inspect()
        self.assertIn("local-only", state.local_only_branches)
        self.assertNotIn("origin/remote-only", state.remote_only_branches)
        self.assertEqual(
            state.branch_inventory_scope,
            "cached_local_refs_not_remote_verified",
        )

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

    def test_receipt_rejects_raw_remote_changes_hidden_by_redaction(self) -> None:
        cases = (
            (
                "userinfo",
                "https://alice:first@example.invalid/org/repo.git",
                "https://bob:second@example.invalid/org/repo.git",
            ),
            (
                "query",
                "https://example.invalid/org/repo.git?token=first",
                "https://example.invalid/org/repo.git?token=second",
            ),
            (
                "scp username",
                "alice@example.invalid:org/repo.git",
                "bob@example.invalid:org/repo.git",
            ),
        )
        upstream_oid = self.fixture._git(
            self.fixture.local, "rev-parse", "refs/remotes/origin/main"
        ).stdout.strip()
        for label, original, changed in cases:
            with self.subTest(remote_change=label):
                self.fixture._git(
                    self.fixture.local, "remote", "set-url", "origin", original
                )
                measured = self.service.inspect(self.fixture.local)
                receipt = {
                    "version": 2,
                    "repository_key": measured.common_directory,
                    "tracking_remote": "origin",
                    "remote_url": measured.remote_url,
                    "remote_fingerprint": hashlib.sha256(
                        original.encode("utf-8")
                    ).hexdigest(),
                    "upstream": measured.upstream,
                    "upstream_oid": upstream_oid,
                    "attempted_at": NOW,
                    "succeeded": True,
                    "fetched_at": NOW,
                    "authentication": "fetch_succeeded",
                }
                self.fixture._git(
                    self.fixture.local, "remote", "set-url", "origin", changed
                )
                state = self.service.inspect(
                    self.fixture.local, fetch_receipt=receipt
                )

                self.assertEqual(state.remote_url, receipt["remote_url"])
                self.assertFalse(state.remote_state_fresh)
                self.assertIsNone(state.fetch_receipt)
                self.assertEqual(state.authentication, "not_checked")
                self.assertTrue(
                    any("exact remote fingerprint" in error for error in state.errors)
                )

    def test_manual_tracking_ref_change_does_not_change_fetched_oid_counts(self) -> None:
        fresh = self.inspect()
        fetched_oid = fresh.fetch_receipt["upstream_oid"]
        self.fixture.commit(self.fixture.local, "local\n", "local-only change")
        local_oid = self.fixture._git(
            self.fixture.local, "rev-parse", "HEAD"
        ).stdout.strip()
        self.assertNotEqual(local_oid, fetched_oid)
        self.fixture._git(
            self.fixture.local,
            "update-ref",
            "refs/remotes/origin/main",
            local_oid,
        )

        state = self.service.inspect(
            self.fixture.local, fetch_receipt=fresh.fetch_receipt
        )
        self.assertTrue(state.remote_state_fresh)
        self.assertEqual(state.fetch_receipt["upstream_oid"], fetched_oid)
        self.assertEqual((state.ahead, state.behind), (1, 0))

    def test_preexisting_replace_ref_cannot_distort_topology_counts(self) -> None:
        remote_oid = self.fixture._git(
            self.fixture.local, "rev-parse", "refs/remotes/origin/main"
        ).stdout.strip()
        self.fixture.commit(self.fixture.local, "local\n", "local topology tip")
        local_oid = self.fixture._git(
            self.fixture.local, "rev-parse", "HEAD"
        ).stdout.strip()
        self.fixture._git(
            self.fixture.local, "replace", local_oid, remote_oid
        )
        distorted = self.fixture._git(
            self.fixture.local,
            "rev-list",
            "--left-right",
            "--count",
            f"{remote_oid}...HEAD",
        ).stdout.strip()
        self.assertNotEqual(distorted, "0\t1")

        state = self.service.inspect(self.fixture.local, fetch_remote=True)
        self.assertEqual(state.fetch_receipt["upstream_oid"], remote_oid)
        self.assertEqual((state.ahead, state.behind), (1, 0))
        self.assertTrue(state.remote_state_fresh)

    def test_inherited_git_dir_and_work_tree_cannot_redirect_inspection(self) -> None:
        decoy = self.root / "decoy"
        self.fixture._run(
            self.root, "init", "--initial-branch=decoy", str(decoy)
        )
        self.fixture._config(decoy)
        (decoy / "decoy.txt").write_text("decoy\n", encoding="utf-8")
        self.fixture._git(decoy, "add", "decoy.txt")
        self.fixture._git(decoy, "commit", "-m", "decoy repository")

        with patch.dict(
            os.environ,
            {
                "GIT_DIR": str(decoy / ".git"),
                "GIT_WORK_TREE": str(decoy),
            },
            clear=False,
        ):
            state = self.service.inspect(self.fixture.local)

        self.assertEqual(Path(state.repository), self.fixture.local.resolve())
        self.assertEqual(Path(state.worktree), self.fixture.local.resolve())
        self.assertEqual(state.branch, "main")
        self.assertNotIn("decoy repository", state.last_commit or "")

    def test_shared_fetch_head_overwrite_cannot_rebind_advertised_oid(self) -> None:
        self.fixture.commit(self.fixture.local, "local\n", "local topology tip")
        local_oid = self.fixture._git(
            self.fixture.local, "rev-parse", "HEAD"
        ).stdout.strip()
        remote_oid = self.fixture._git(
            self.fixture.seed, "rev-parse", "refs/heads/main"
        ).stdout.strip()
        extra = self.root / "shared-fetch-head-worktree"
        self.fixture._git(
            self.fixture.local, "worktree", "add", "-b", "extra", str(extra)
        )
        self.fixture._git(extra, "branch", "--set-upstream-to=origin/main", "extra")
        common = Path(self.service.inspect(extra).common_directory)
        self.assertEqual(
            common,
            Path(self.service.inspect(self.fixture.local).common_directory),
        )
        fetch_head = common / "FETCH_HEAD"
        injected = f"{local_oid}\t\tbranch 'forged' of shared-worktree\n"
        real_runner = self.service.runner

        def overwriting_runner(args, cwd, timeout):
            result = real_runner(args, cwd, timeout)
            if "ls-remote" in args:
                fetch_head.write_text(injected, encoding="utf-8")
            return result

        state = GitService(
            runner=overwriting_runner,
            clock=lambda: NOW,
            freshness_seconds=300,
        ).inspect(extra, fetch_remote=True)

        self.assertEqual(fetch_head.read_text(encoding="utf-8"), injected)
        self.assertEqual(state.fetch_receipt["upstream_oid"], remote_oid)
        self.assertNotEqual(state.fetch_receipt["upstream_oid"], local_oid)
        self.assertEqual((state.ahead, state.behind), (1, 0))
        self.assertTrue(state.remote_state_fresh)

    def test_dual_fetch_binds_exact_merge_ref_despite_custom_refspec(self) -> None:
        self.fixture._git(self.fixture.other, "checkout", "-b", "alternate")
        self.fixture.commit(self.fixture.other, "alternate\n", "alternate tip")
        self.fixture._git(self.fixture.other, "push", "-u", "origin", "alternate")
        alternate_oid = self.fixture._git(
            self.fixture.other, "rev-parse", "HEAD"
        ).stdout.strip()
        main_oid = self.fixture._git(
            self.fixture.local, "rev-parse", "HEAD"
        ).stdout.strip()
        self.fixture._git(
            self.fixture.local, "config", "--unset-all", "remote.origin.fetch"
        )
        self.fixture._git(
            self.fixture.local,
            "config",
            "--add",
            "remote.origin.fetch",
            "+refs/heads/alternate:refs/remotes/origin/main",
        )

        state = self.service.inspect(self.fixture.local, fetch_remote=True)
        tracking_oid = self.fixture._git(
            self.fixture.local, "rev-parse", "refs/remotes/origin/main"
        ).stdout.strip()
        self.assertEqual(tracking_oid, main_oid)
        self.assertNotEqual(tracking_oid, alternate_oid)
        self.assertEqual(state.fetch_receipt["upstream_oid"], main_oid)
        self.assertEqual((state.ahead, state.behind), (0, 0))
        self.assertTrue(state.remote_state_fresh)

    def test_merge_source_change_invalidates_same_display_upstream_receipt(
        self,
    ) -> None:
        self.fixture._git(self.fixture.other, "checkout", "-b", "source-one")
        self.fixture.commit(self.fixture.other, "source one\n", "source one")
        self.fixture._git(self.fixture.other, "push", "origin", "source-one")
        self.fixture._git(self.fixture.other, "checkout", "main")
        self.fixture._git(self.fixture.other, "checkout", "-b", "source-two")
        self.fixture.commit(self.fixture.other, "source two\n", "source two")
        self.fixture._git(self.fixture.other, "push", "origin", "source-two")

        self.fixture._git(
            self.fixture.local,
            "config",
            "--unset-all",
            "remote.origin.fetch",
        )
        self.fixture._git(
            self.fixture.local,
            "config",
            "--add",
            "remote.origin.fetch",
            "+refs/heads/source-one:refs/remotes/origin/main",
        )
        self.fixture._git(
            self.fixture.local,
            "config",
            "branch.main.merge",
            "refs/heads/source-one",
        )
        first = self.service.inspect(self.fixture.local, fetch_remote=True)
        self.assertEqual(first.upstream, "origin/main")
        self.assertEqual(first.tracked_merge_ref, "refs/heads/source-one")
        self.assertEqual(first.fetch_receipt["merge_ref"], "refs/heads/source-one")
        self.assertTrue(first.remote_state_fresh)

        self.fixture._git(
            self.fixture.local,
            "config",
            "--unset-all",
            "remote.origin.fetch",
        )
        self.fixture._git(
            self.fixture.local,
            "config",
            "--add",
            "remote.origin.fetch",
            "+refs/heads/source-two:refs/remotes/origin/main",
        )
        self.fixture._git(
            self.fixture.local,
            "config",
            "branch.main.merge",
            "refs/heads/source-two",
        )
        changed = self.service.inspect(
            self.fixture.local,
            fetch_remote=False,
            fetch_receipt=first.fetch_receipt,
        )

        self.assertEqual(changed.upstream, "origin/main")
        self.assertEqual(changed.tracked_merge_ref, "refs/heads/source-two")
        self.assertFalse(changed.remote_state_fresh)
        self.assertIsNone(changed.fetch_receipt)
        self.assertIsNone(changed.ahead)
        self.assertIsNone(changed.behind)
        self.assertTrue(
            any("merge source" in error for error in changed.errors)
        )

    def test_malicious_fetch_refspec_cannot_rewrite_non_remote_namespaces(self) -> None:
        self.fixture.commit(self.fixture.local, "local\n", "protected local tip")
        local_tip = self.fixture._git(
            self.fixture.local, "rev-parse", "HEAD"
        ).stdout.strip()
        self.fixture._git(self.fixture.local, "branch", "protected", local_tip)
        self.fixture._git(self.fixture.local, "tag", "protected", local_tip)

        (self.fixture.seed / "remote-blob.txt").write_text(
            "remote replacement payload\n", encoding="utf-8"
        )
        remote_blob = self.fixture._git(
            self.fixture.seed, "hash-object", "-w", "remote-blob.txt"
        ).stdout.strip()
        self.fixture._git(
            self.fixture.seed, "update-ref", "refs/evil/blob", remote_blob
        )
        self.fixture._git(
            self.fixture.seed, "tag", "source-tag", "refs/heads/main"
        )
        remote_main = self.fixture._git(
            self.fixture.seed, "rev-parse", "refs/heads/main"
        ).stdout.strip()
        self.fixture._git(
            self.fixture.seed,
            "push",
            "origin",
            "refs/evil/blob:refs/evil/blob",
            "refs/tags/source-tag:refs/tags/source-tag",
        )

        (self.fixture.local / "original-object.txt").write_text(
            "unreferenced original\n", encoding="utf-8"
        )
        (self.fixture.local / "replacement-object.txt").write_text(
            "local replacement\n", encoding="utf-8"
        )
        original_blob = self.fixture._git(
            self.fixture.local, "hash-object", "-w", "original-object.txt"
        ).stdout.strip()
        replacement_blob = self.fixture._git(
            self.fixture.local, "hash-object", "-w", "replacement-object.txt"
        ).stdout.strip()
        replace_ref = f"refs/replace/{original_blob}"
        self.fixture._git(
            self.fixture.local, "update-ref", replace_ref, replacement_blob
        )

        self.fixture._git(
            self.fixture.local, "config", "--unset-all", "remote.origin.fetch"
        )
        malicious_refspecs = (
            "+refs/heads/main:refs/heads/protected",
            "+refs/tags/source-tag:refs/tags/protected",
            f"+refs/evil/blob:{replace_ref}",
        )
        for refspec in malicious_refspecs:
            self.fixture._git(
                self.fixture.local,
                "config",
                "--add",
                "remote.origin.fetch",
                refspec,
            )

        protected_refs = (
            "refs/heads/protected",
            "refs/tags/protected",
            replace_ref,
        )
        before = {
            ref: self.fixture._git(
                self.fixture.local, "rev-parse", "--verify", ref
            ).stdout.strip()
            for ref in protected_refs
        }

        state = self.service.inspect(self.fixture.local, fetch_remote=True)
        after = {
            ref: self.fixture._git(
                self.fixture.local, "rev-parse", "--verify", ref
            ).stdout.strip()
            for ref in protected_refs
        }
        self.assertEqual(after, before)
        self.assertTrue(state.remote_state_fresh)
        self.assertEqual(state.authentication, "fetch_succeeded")
        self.assertEqual(state.fetch_receipt["upstream_oid"], remote_main)

    def test_failed_and_malformed_status_are_not_trusted(self) -> None:
        real_runner = self.service.runner
        cases = (
            ("failed", CommandResult(128, "", "status unavailable")),
            ("malformed", CommandResult(0, "??broken\0", "")),
        )
        for label, replacement in cases:
            with self.subTest(status_result=label):
                def runner(args, cwd, timeout, replacement=replacement):
                    if "status" in args:
                        return replacement
                    return real_runner(args, cwd, timeout)

                state = GitService(runner=runner, clock=lambda: NOW).inspect(
                    self.fixture.local
                )
                self.assertFalse(state.inspection_ok)
                self.assertTrue(state.errors)

    def test_failed_and_malformed_rev_list_withhold_relationship(self) -> None:
        real_runner = self.service.runner
        cases = (
            ("failed", CommandResult(128, "", "rev-list unavailable")),
            ("malformed", CommandResult(0, "one two three\n", "")),
        )
        for label, replacement in cases:
            with self.subTest(rev_list_result=label):
                def runner(args, cwd, timeout, replacement=replacement):
                    if "rev-list" in args:
                        return replacement
                    return real_runner(args, cwd, timeout)

                state = GitService(runner=runner, clock=lambda: NOW).inspect(
                    self.fixture.local,
                    fetch_remote=True,
                )
                self.assertFalse(state.remote_state_fresh)
                self.assertIsNone(state.ahead)
                self.assertIsNone(state.behind)
                self.assertIsNone(state.pending_push)
                self.assertTrue(state.errors)

    def test_local_upstream_is_never_treated_as_a_fetch_remote(self) -> None:
        self.fixture._git(
            self.fixture.local, "config", "branch.main.remote", "."
        )
        self.fixture._git(
            self.fixture.local,
            "config",
            "branch.main.merge",
            "refs/heads/main",
        )
        calls = []
        real_runner = self.service.runner

        def runner(args, cwd, timeout):
            calls.append(tuple(args))
            return real_runner(args, cwd, timeout)

        state = GitService(runner=runner, clock=lambda: NOW).inspect(
            self.fixture.local,
            fetch_remote=True,
        )
        self.assertIsNone(state.remote_name)
        self.assertFalse(state.remote_state_fresh)
        self.assertEqual(state.authentication, "not_configured")
        self.assertFalse(any("fetch" in call for call in calls))
        self.assertTrue(any("local upstream" in error for error in state.errors))

    def test_leading_dash_remote_is_ignored_without_invocation(self) -> None:
        self.fixture._git(self.fixture.local, "remote", "remove", "origin")
        self.fixture._git(
            self.fixture.local,
            "config",
            "remote.-danger.url",
            str(self.fixture.remote),
        )
        self.fixture._git(
            self.fixture.local,
            "config",
            "remote.-danger.fetch",
            "+refs/heads/*:refs/remotes/-danger/*",
        )
        self.fixture._git(
            self.fixture.local, "config", "branch.main.remote", "-danger"
        )
        self.fixture._git(
            self.fixture.local,
            "config",
            "branch.main.merge",
            "refs/heads/main",
        )
        calls = []
        real_runner = self.service.runner

        def runner(args, cwd, timeout):
            calls.append(tuple(args))
            return real_runner(args, cwd, timeout)

        state = GitService(runner=runner, clock=lambda: NOW).inspect(
            self.fixture.local,
            fetch_remote=True,
        )
        self.assertIsNone(state.remote_name)
        self.assertFalse(state.remote_state_fresh)
        self.assertFalse(any("fetch" in call for call in calls))
        self.assertTrue(any("unsafe Git remote name" in error for error in state.errors))

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
        self.assertEqual(later.authentication, "fetch_succeeded")
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
