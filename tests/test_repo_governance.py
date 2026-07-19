from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repoctl", ROOT / "scripts" / "repoctl.py")
assert SPEC and SPEC.loader
repoctl = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = repoctl
SPEC.loader.exec_module(repoctl)


class RepositoryGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads((ROOT / "governance" / "repository-policy.json").read_text(encoding="utf-8"))

    def test_future_branch_names_are_host_scoped_and_lowercase(self) -> None:
        for branch in ("codex/repository-governance", "claude/fix-continuity", "human/release-1.0"):
            self.assertTrue(repoctl.branch_allowed(branch, self.policy), branch)
        for branch in ("feature/foo", "codex/UPPER", "main-copy", "review/foo"):
            self.assertFalse(repoctl.branch_allowed(branch, self.policy), branch)

    def test_only_canonical_remote_urls_are_allowed(self) -> None:
        self.assertTrue(repoctl.remote_url_allowed("https://github.com/manbeardog13/mbd-AI.git", self.policy))
        self.assertTrue(repoctl.remote_url_allowed("git@github.com:manbeardog13/mbd-AI.git", self.policy))
        self.assertFalse(repoctl.remote_url_allowed("https://github.com/attacker/mbd-AI.git", self.policy))

    def test_pre_push_input_is_strict(self) -> None:
        line = f"refs/heads/codex/test {'1' * 40} refs/heads/codex/test {'0' * 40}\n"
        self.assertEqual(len(repoctl.parse_push_lines([line])), 1)
        with self.assertRaises(ValueError):
            repoctl.parse_push_lines(["too few fields"])

    def test_policy_blocks_dangerous_push_classes(self) -> None:
        push = self.policy["push"]
        self.assertFalse(push["allow_branch_deletion"])
        self.assertFalse(push["allow_force_push"])
        self.assertFalse(push["allow_protected_branch_push"])
        self.assertFalse(push["allow_tag_push"])
        self.assertTrue(push["require_canonical_base_ancestor"])

    def test_pull_policy_is_fast_forward_only_on_main(self) -> None:
        pull = self.policy["pull"]
        self.assertEqual(pull["allowed_branch"], "main")
        self.assertEqual(pull["strategy"], "ff-only")
        self.assertEqual(pull["require_tracking_branch"], "origin/main")


if __name__ == "__main__":
    unittest.main()
