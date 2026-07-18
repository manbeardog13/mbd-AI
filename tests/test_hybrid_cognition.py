from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "nero-hybrid-cognition" / "scripts" / "hybrid_brain.py"
SPEC = importlib.util.spec_from_file_location("nero_hybrid_test", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
Brain = MODULE.Brain


class HybridCognitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "hybrid.json"
        self.learning = Path(self.temp.name) / "learning.json"
        self.brain = Brain(self.state)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, topology="parallel-analysis", **kwargs):
        return self.brain.create(
            objective="Find the smallest verified change",
            acceptance="Both required lanes submit evidence and the gate passes",
            topology=topology,
            task_kind="software-engineering",
            task_tags="engineering,python",
            references="src,tests",
            builder=kwargs.get("builder", "codex"),
            codex_scope=kwargs.get("codex_scope"),
            claude_scope=kwargs.get("claude_scope"),
        )

    def submit(self, task_id, host, **kwargs):
        return self.brain.submit(
            task_id=task_id,
            host=host,
            summary=kwargs.get("summary", f"{host} evidence-backed result"),
            evidence=kwargs.get("evidence", "test-output,source-path"),
            checks=kwargs.get("checks", "targeted tests pass"),
            risks=kwargs.get("risks", "bounded residual risk"),
            files=kwargs.get("files", ""),
            verdict=kwargs.get("verdict"),
        )

    def test_status_is_cold(self):
        self.assertFalse(self.brain.status()["exists"])
        self.assertFalse(self.state.exists())

    def test_parallel_analysis_gate_and_learning_feedback(self):
        task = self.create()
        for host in ("codex", "claude"):
            self.brain.claim(task_id=task["id"], host=host, lease_minutes=10)
        with self.assertRaises(ValueError):
            self.submit(task["id"], "codex", files="src/file.py")
        self.submit(task["id"], "codex")
        self.submit(task["id"], "claude")
        self.assertTrue(self.brain.ready(task_id=task["id"])["ready"])
        approved = self.brain.approve(
            task_id=task["id"],
            approved=True,
            quality=0.93,
            decision_note="Acceptance checks passed against shared evidence.",
            learning_ledger=str(self.learning),
        )
        self.assertEqual(approved["task"]["status"], "completed")
        self.assertTrue(approved["learning"]["ok"])
        learning = json.loads(self.learning.read_text(encoding="utf-8"))
        self.assertEqual(len(learning["episodes"]), 3)
        self.assertNotIn(task["objective"], self.learning.read_text(encoding="utf-8"))
        self.assertTrue(self.brain.audit()["ok"])

    def test_build_review_requires_current_passing_review(self):
        task = self.create("build-review", builder="codex")
        with self.assertRaises(ValueError):
            self.brain.claim(task_id=task["id"], host="claude", lease_minutes=10)
        self.brain.claim(task_id=task["id"], host="codex", lease_minutes=10)
        self.submit(task["id"], "codex", files="src/a.py")
        self.brain.claim(task_id=task["id"], host="claude", lease_minutes=10)
        self.submit(task["id"], "claude", verdict="changes-requested")
        self.assertFalse(self.brain.ready(task_id=task["id"])["ready"])
        self.brain.claim(task_id=task["id"], host="codex", lease_minutes=10)
        self.submit(task["id"], "codex", summary="revision two", files="src/a.py")
        self.brain.claim(task_id=task["id"], host="claude", lease_minutes=10)
        self.submit(task["id"], "claude", verdict="pass")
        self.assertTrue(self.brain.ready(task_id=task["id"])["ready"])

    def test_disjoint_build_rejects_overlap_and_scope_escape(self):
        with self.assertRaises(ValueError):
            self.create("disjoint-build", codex_scope="src", claude_scope="src/docs")
        task = self.create(
            "disjoint-build", codex_scope="src/backend", claude_scope="src/frontend"
        )
        self.brain.claim(task_id=task["id"], host="codex", lease_minutes=10)
        with self.assertRaises(ValueError):
            self.submit(task["id"], "codex", files="src/frontend/app.ts")
        self.submit(task["id"], "codex", files="src/backend/api.py")
        self.brain.claim(task_id=task["id"], host="claude", lease_minutes=10)
        self.submit(task["id"], "claude", files="src/frontend/app.ts")
        self.assertTrue(self.brain.ready(task_id=task["id"])["ready"])


if __name__ == "__main__":
    unittest.main()
