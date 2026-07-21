"""Regression tests for continuity verifier gates and linked-worktree paths."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PATH = ROOT / "verify" / "verify_nero_continuity.py"
SPEC = importlib.util.spec_from_file_location("verify_nero_continuity", VERIFIER_PATH)
VERIFIER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VERIFIER)


def _worktree_output(primary: Path, linked: Path) -> bytes:
    return b"\0".join(
        (
            b"worktree " + os.fsencode(str(primary)),
            b"HEAD " + b"1" * 40,
            b"branch refs/heads/main",
            b"",
            b"worktree " + os.fsencode(str(linked)),
            b"HEAD " + b"2" * 40,
            b"branch refs/heads/topic",
            b"",
        )
    )


class WorktreeResolutionTests(unittest.TestCase):
    def test_main_checkout_resolves_without_git_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "primary repo"
            (repo / ".git").mkdir(parents=True)
            with mock.patch.object(
                VERIFIER.subprocess,
                "run",
                side_effect=AssertionError("Git should not be called"),
            ):
                self.assertEqual(VERIFIER._main_worktree_root(repo), repo.resolve())

    def test_linked_checkout_uses_primary_worktree_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "primary repo Ž"
            linked = Path(tmp) / "linked repo"
            linked.mkdir()
            (linked / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=_worktree_output(primary, linked), stderr=b""
            )
            with mock.patch.object(VERIFIER.subprocess, "run", return_value=completed):
                self.assertEqual(
                    VERIFIER._main_worktree_root(linked), primary.resolve()
                )

    def test_failed_or_malformed_discovery_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            linked = Path(tmp) / "linked"
            linked.mkdir()
            (linked / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
            cases = (
                subprocess.CompletedProcess(
                    args=[], returncode=1, stdout=b"", stderr=b"failed"
                ),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout=b"HEAD bad\0", stderr=b""
                ),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout=b"worktree \0", stderr=b""
                ),
            )
            for completed in cases:
                with self.subTest(returncode=completed.returncode):
                    with mock.patch.object(
                        VERIFIER.subprocess, "run", return_value=completed
                    ):
                        with self.assertRaises(RuntimeError):
                            VERIFIER._main_worktree_root(linked)

    def test_process_failures_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            linked = Path(tmp) / "linked"
            linked.mkdir()
            (linked / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
            failures = (
                FileNotFoundError("git missing"),
                subprocess.TimeoutExpired(cmd="git", timeout=15),
            )
            for failure in failures:
                with self.subTest(failure=type(failure).__name__):
                    with mock.patch.object(
                        VERIFIER.subprocess, "run", side_effect=failure
                    ):
                        with self.assertRaises(RuntimeError):
                            VERIFIER._main_worktree_root(linked)

    def test_protected_memory_path_ignores_linked_worktree_decoy(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "primary repo"
            linked = Path(tmp) / "linked repo"
            home = Path(tmp) / "home"
            (primary / "data").mkdir(parents=True)
            (linked / "data").mkdir(parents=True)
            (linked / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
            (primary / "data" / "memory.db").write_bytes(b"canonical")
            (linked / "data" / "memory.db").write_bytes(b"decoy")
            completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=_worktree_output(primary, linked), stderr=b""
            )
            with mock.patch.object(VERIFIER.subprocess, "run", return_value=completed):
                root, paths = VERIFIER._protected_paths(linked, home=home)
            self.assertEqual(root, primary.resolve())
            self.assertEqual(
                paths["data/memory.db"], primary.resolve() / "data" / "memory.db"
            )


class ProtectedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "data/memory.db": "memory",
            "global_claude_md": "claude",
            "codex_agents_md": "codex",
            "codex_config_toml": "config-a",
        }

    def test_equal_required_hashes_pass(self):
        result = VERIFIER._compare_protected(self.before, dict(self.before))
        self.assertTrue(result["ok"])
        self.assertEqual(result["changed"], [])
        self.assertEqual(result["absent"], [])

    def test_byte_mutation_fails(self):
        after = dict(self.before, **{"data/memory.db": "changed"})
        result = VERIFIER._compare_protected(self.before, after)
        self.assertFalse(result["ok"])
        self.assertEqual(result["changed"], ["data/memory.db"])

    def test_missing_created_and_present_deleted_fail(self):
        for before_value, after_value in ((None, "created"), ("present", None)):
            with self.subTest(before=before_value, after=after_value):
                before = dict(self.before, **{"data/memory.db": before_value})
                after = dict(self.before, **{"data/memory.db": after_value})
                result = VERIFIER._compare_protected(before, after)
                self.assertFalse(result["ok"])
                self.assertIn("data/memory.db", result["absent"])

    def test_missing_required_file_never_passes_vacuously(self):
        before = dict(self.before, **{"data/memory.db": None})
        after = dict(before)
        result = VERIFIER._compare_protected(before, after)
        self.assertFalse(result["ok"])
        self.assertEqual(result["absent_unchanged"], ["data/memory.db"])

    def test_codex_config_drift_is_gated(self):
        after = dict(self.before, codex_config_toml="config-b")
        result = VERIFIER._compare_protected(self.before, after)
        self.assertFalse(result["ok"])
        self.assertEqual(result["changed"], ["codex_config_toml"])


class ColdCliGateTests(unittest.TestCase):
    def _perf(self, read: float, write: float) -> dict[str, float]:
        return {"read_cold_p95": read, "write_cold_p95": write}

    def test_exact_budget_passes_and_over_budget_fails(self):
        codes = [0] * VERIFIER.COLD_SAMPLE_COUNT
        semantics = [True] * VERIFIER.COLD_SAMPLE_COUNT
        at_budget = VERIFIER._cold_cli_gates(
            self._perf(250.0, 250.0), codes, codes, semantics, semantics
        )
        self.assertTrue(at_budget["cold_cli_read_p95_within_250ms"])
        self.assertTrue(at_budget["cold_cli_write_p95_within_250ms"])

        over_budget = VERIFIER._cold_cli_gates(
            self._perf(250.01, 250.01), codes, codes, semantics, semantics
        )
        self.assertFalse(over_budget["cold_cli_read_p95_within_250ms"])
        self.assertFalse(over_budget["cold_cli_write_p95_within_250ms"])

    def test_fast_failed_sample_cannot_pass_latency_gate(self):
        read_codes = [0] * VERIFIER.COLD_SAMPLE_COUNT
        read_codes[-1] = 7
        write_codes = [0] * VERIFIER.COLD_SAMPLE_COUNT
        semantics = [True] * VERIFIER.COLD_SAMPLE_COUNT
        result = VERIFIER._cold_cli_gates(
            self._perf(1.0, 1.0),
            read_codes,
            write_codes,
            semantics,
            semantics,
        )
        self.assertFalse(result["cold_cli_read_samples_succeeded"])
        self.assertFalse(result["cold_cli_read_p95_within_250ms"])
        self.assertTrue(result["cold_cli_write_samples_succeeded"])
        self.assertTrue(result["cold_cli_write_p95_within_250ms"])

    def test_zero_exit_with_wrong_semantics_cannot_pass(self):
        codes = [0] * VERIFIER.COLD_SAMPLE_COUNT
        read_semantics = [True] * VERIFIER.COLD_SAMPLE_COUNT
        read_semantics[-1] = False
        write_semantics = [True] * VERIFIER.COLD_SAMPLE_COUNT
        result = VERIFIER._cold_cli_gates(
            self._perf(1.0, 1.0),
            codes,
            codes,
            read_semantics,
            write_semantics,
        )
        self.assertFalse(result["cold_cli_read_samples_succeeded"])
        self.assertFalse(result["cold_cli_read_p95_within_250ms"])
        self.assertTrue(result["cold_cli_write_samples_succeeded"])

    def test_non_object_json_is_a_semantic_failure(self):
        for output in (None, [], "OK", 1):
            with self.subTest(output=output):
                self.assertFalse(VERIFIER._cold_read_sample_ok(0, output, "topic"))
                self.assertFalse(VERIFIER._cold_write_sample_ok(0, output))


if __name__ == "__main__":
    unittest.main()
