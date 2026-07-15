from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import schoolctl


class SchoolControlTests(unittest.TestCase):
    def test_level_curve_is_bounded(self):
        self.assertEqual(schoolctl.level_for_xp(0), 1)
        self.assertEqual(schoolctl.level_for_xp(2500), 50)
        self.assertEqual(schoolctl.level_for_xp(10000), 100)
        self.assertEqual(schoolctl.level_for_xp(50000), 100)

    def test_hash_chain_detects_entry_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.txt"
            path.write_text("HEADER\n", encoding="utf-8")
            schoolctl.append_entry(path, {"actor": "codex", "value": 1})
            schoolctl.append_entry(path, {"actor": "claude", "value": 2})
            self.assertEqual(len(schoolctl.verify_chain(path)), 2)
            content = path.read_text(encoding="utf-8").replace('"value": 1', '"value": 9')
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                schoolctl.verify_chain(path)

    def test_generic_json_grader(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task = root / "task"
            run = task / "runs" / "attempt_001"
            work = run / "work"
            work.mkdir(parents=True)
            spec = {
                "id": "TEST-1",
                "checks": [
                    {"id": "a", "type": "json_equals", "path": "answer", "expected": "yes", "weight": 2},
                    {"id": "b", "type": "json_max", "path": "attempts", "expected": 3, "weight": 1},
                ],
            }
            (task / "task.json").write_text(json.dumps(spec), encoding="utf-8")
            (run / "run.json").write_text(json.dumps({"run_id": "TEST-1:attempt-1"}), encoding="utf-8")
            (work / "submission.json").write_text(json.dumps({"answer": "YES", "attempts": 2}), encoding="utf-8")
            result = schoolctl.run_checks(task, run)
            self.assertEqual(result["objective_score"], 10.0)
            self.assertTrue(all(row["passed"] for row in result["checks"]))

    def test_initial_tasks_are_pending_real_claude_review(self):
        tasks = list(schoolctl.SCHOOL.glob("[0-9][0-9]_*/*/task.json"))
        self.assertEqual(len(tasks), 14)
        for task_json in tasks:
            state = schoolctl.agreement_state(task_json.parent)
            self.assertEqual(state["status"], "PENDING")
            entries = schoolctl.entry_lines(task_json.parent / "Task_agreement.txt")
            self.assertEqual([row["actor"] for row in entries], ["codex"])

    def test_dashboard_is_honest_about_estimates(self):
        dashboard = schoolctl.render_dashboard()
        self.assertIn("EVIDENCE-BASED ESTIMATES", dashboard)
        self.assertIn("not guarantees of correctness", dashboard)
        self.assertIn("Cross-agent collaboration", dashboard)


if __name__ == "__main__":
    unittest.main()

