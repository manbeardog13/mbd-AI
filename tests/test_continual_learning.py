from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "nero-continual-learning" / "scripts" / "learning_ledger.py"
SPEC = importlib.util.spec_from_file_location("nero_learning_test", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
Ledger = MODULE.Ledger


class ContinualLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "learning.json"
        self.ledger = Ledger(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_status_is_cold_and_does_not_create_ledger(self):
        status = self.ledger.status()
        self.assertFalse(status["exists"])
        self.assertFalse(self.path.exists())

    def test_episode_privacy_and_contextual_routing(self):
        raw_context = "private customer incident 719"
        self.ledger.record(
            task_kind="audit",
            resource="codex-hosted",
            tags="security,python",
            context_label=raw_context,
            success=True,
            quality=0.95,
            latency_ms=120,
            note="sanitized acceptance checks passed",
        )
        self.ledger.record(
            task_kind="audit",
            resource="slow-tool",
            tags="security",
            context_label="other case",
            success=False,
            quality=0.9,
            latency_ms=5000,
            note="failed",
        )
        serialized = self.path.read_text(encoding="utf-8")
        self.assertNotIn(raw_context, serialized)
        state = json.loads(serialized)
        self.assertEqual(len(state["episodes"][0]["context_key"]), 64)
        ranking = self.ledger.recommend(
            task_kind="audit",
            candidates=["slow-tool", "codex-hosted", "unseen"],
            tags="security",
            target_latency_ms=500,
        )["ranking"]
        self.assertEqual(ranking[0]["resource"], "codex-hosted")
        self.assertEqual({row["resource"] for row in ranking}, {"slow-tool", "codex-hosted", "unseen"})

    def _promoted_lesson(self):
        lesson = self.ledger.propose(
            statement="When an auth parser changes, run malformed-token tests; invalidate the lesson if rejection coverage falls.",
            task_kind="audit",
            tags="auth,security",
        )
        for index, label in enumerate(("api-v1", "api-v2", "api-v1-regression")):
            result = self.ledger.evaluate(
                lesson_id=lesson["id"],
                passed=True,
                score=0.9,
                tags=f"auth,context-{index % 2}",
                context_label=label,
                note="test passed",
            )
        self.assertTrue(result["stats"]["eligible_for_promotion"])
        promoted = self.ledger.promote(lesson_id=lesson["id"], approved=True)
        return promoted["lesson"]

    def test_promotion_retrieval_and_quarantine(self):
        with self.assertRaises(PermissionError):
            candidate = self.ledger.propose(
                statement="Bounded rule with a falsifier.", task_kind="test", tags="x"
            )
            self.ledger.promote(lesson_id=candidate["id"], approved=False)
        lesson = self._promoted_lesson()
        retrieved = self.ledger.lessons(task_kind="audit", tags="security,auth")
        self.assertEqual(retrieved[0]["id"], lesson["id"])
        for label in ("failure-a", "failure-b"):
            result = self.ledger.evaluate(
                lesson_id=lesson["id"],
                passed=False,
                score=0.8,
                tags="auth",
                context_label=label,
                note="regression",
            )
        self.assertEqual(result["lesson"]["status"], "quarantined")
        self.assertEqual(self.ledger.lessons(task_kind="audit", tags="auth"), [])
        self.assertTrue(any(row["kind"] == "root-cause" for row in self.ledger.backlog()))
        self.assertTrue(self.ledger.audit()["ok"])

    def test_duplicate_candidate_is_deduplicated(self):
        kwargs = dict(statement="Test a bounded statement before reuse.", task_kind="review", tags="code")
        first = self.ledger.propose(**kwargs)
        second = self.ledger.propose(**kwargs)
        self.assertFalse(first["deduplicated"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["id"], second["id"])

    def test_retirement_requires_approval(self):
        lesson = self.ledger.propose(
            statement="Retire this bounded test lesson when obsolete.",
            task_kind="maintenance",
            tags="stale",
        )
        with self.assertRaises(PermissionError):
            self.ledger.retire(lesson_id=lesson["id"], approved=False, note="obsolete")
        retired = self.ledger.retire(
            lesson_id=lesson["id"], approved=True, note="Superseded by a verified rule."
        )
        self.assertEqual(retired["status"], "retired")


if __name__ == "__main__":
    unittest.main()
