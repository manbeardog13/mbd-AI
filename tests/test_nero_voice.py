from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "verify" / "verify_nero_voice.py"
SPEC = importlib.util.spec_from_file_location("nero_voice_test", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class VoiceVerifierTests(unittest.TestCase):
    def test_goldens_all_pass(self):
        probes = M.parse_goldens(M.GOLDENS)
        self.assertGreaterEqual(len(probes), 12)
        for name, register, body in probes:
            self.assertEqual(M.lint(body, register), [], f"golden {name} failed")

    def test_banned_lexicon_caught(self):
        errs = M.lint("As an AI, I'd be happy to leverage this seamlessly.", "generic")
        self.assertTrue(any("banned" in e for e in errs))

    def test_exclamation_inflation_caught(self):
        errs = M.lint("Done!! Amazing!! So great!!", "celebration")
        self.assertTrue(any("exclamation" in e for e in errs))

    def test_apology_spiral_caught(self):
        errs = M.lint("Sorry about that. Really sorry again.", "confession")
        self.assertTrue(any("apology spiral" in e for e in errs))

    def test_uncertainty_needs_calibration(self):
        errs = M.lint("It will definitely work perfectly.", "uncertainty")
        self.assertTrue(any("calibration" in e for e in errs))

    def test_refusal_needs_alternative(self):
        errs = M.lint("No. That is not allowed.", "refusal")
        self.assertTrue(any("alternative" in e for e in errs))

    def test_confession_needs_fix(self):
        errs = M.lint("I made a mistake and it was wrong of me.", "confession")
        self.assertTrue(any("same-breath fix" in e for e in errs))

    def test_interrupt_needs_return_path(self):
        errs = M.lint("Pausing everything now.", "interrupt")
        self.assertTrue(any("return path" in e for e in errs))

    def test_signature_emoji_policy(self):
        errs = M.lint("Fixed it, my mistake — repaired and pushed. \U0001F7E3", "confession")
        self.assertTrue(any("not allowed" in e for e in errs))

    def test_clean_nero_line_passes(self):
        line = ("Migration sealed — 5 phases, 15 commits, every verifier "
                "green. Good day's work for all three of us. \U0001F7E3")
        self.assertEqual(M.lint(line, "celebration"), [])


if __name__ == "__main__":
    unittest.main()
