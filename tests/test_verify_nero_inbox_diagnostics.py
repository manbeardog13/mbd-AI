from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "verify" / "verify_nero_inbox.py"
SPEC = importlib.util.spec_from_file_location("nero_inbox_diagnostics_test", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        ["python", "scripts/inboxctl.py", "brief"],
        returncode,
        stdout=stdout,
        stderr=stderr,
    )


class InboxVerifierDiagnosticsTests(unittest.TestCase):
    def test_nonzero_process_preserves_empty_stdout_and_stderr(self):
        result = completed(2, "", '{"ok": false, "error": "brief failed"}\r\n')
        with self.assertRaisesRegex(AssertionError, "returncode=2") as raised:
            M.require_brief_output(result, "Today's summary:")
        message = str(raised.exception)
        self.assertIn("stdout=''", message)
        self.assertIn("brief failed", message)

    def test_output_on_stderr_is_not_accepted_as_brief_stdout(self):
        result = completed(0, "", "Today's summary:\r\nBrief ID: wrong-stream\r\n")
        with self.assertRaisesRegex(AssertionError, "empty stdout") as raised:
            M.require_brief_output(result, "Today's summary:")
        self.assertIn("stderr=", str(raised.exception))

    def test_none_stdout_is_diagnosed_before_string_methods(self):
        result = completed(2, None, "underlying subprocess failure")
        with self.assertRaisesRegex(AssertionError, "subprocess failed") as raised:
            M.require_brief_output(result, "Today's summary:")
        self.assertIn("stdout=None", str(raised.exception))
        self.assertNotIn("has no attribute", str(raised.exception))

    def test_crlf_utf8_brief_is_normalized_and_parsed(self):
        result = completed(
            stdout=(
                "Dobar dan, Toni.\r\nToday's summary:\r\n"
                "Brief ID: brief-123\r\nEstimated reading time: 15 seconds.\r\n"
            )
        )
        rendered, brief_id = M.require_brief_output(result, "Today's summary:")
        self.assertEqual(brief_id, "brief-123")
        self.assertNotIn("\r", rendered)
        self.assertIn("Dobar dan, Toni.", rendered)

    def test_missing_brief_id_has_precise_diagnostic(self):
        result = completed(
            stdout="Today's summary:\nEstimated reading time: 15 seconds.\n"
        )
        with self.assertRaisesRegex(AssertionError, "Brief ID") as raised:
            M.require_brief_output(result, "Today's summary:")
        self.assertIn("stdout=", str(raised.exception))

    def test_malformed_acknowledgement_preserves_output(self):
        result = completed(stdout="not-json\r\n")
        with self.assertRaisesRegex(AssertionError, "not valid JSON") as raised:
            M.require_acknowledgement(result, "brief-123")
        self.assertIn("not-json", str(raised.exception))

    def test_missing_acknowledged_field_is_precise(self):
        result = completed(stdout='{"ok": true}\r\n')
        with self.assertRaisesRegex(AssertionError, "missing required"):
            M.require_acknowledgement(result, "brief-123")

    def test_valid_acknowledgement_is_parsed(self):
        result = completed(
            stdout='{"ok": true, "acknowledged": "brief-123"}\r\n'
        )
        payload = M.require_acknowledgement(result, "brief-123")
        self.assertTrue(payload["ok"])

    def test_subprocess_decoder_is_explicit_utf8(self):
        fake = completed(stdout="{}\n")
        with mock.patch.object(M.subprocess, "run", return_value=fake) as run:
            M.run("status")
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "strict")
        self.assertTrue(kwargs["text"])

    def test_adaptive_markers_are_deterministic(self):
        for marker in (
            "Today's highlights:",
            "I'll keep this brief.",
            "Today's summary:",
        ):
            with self.subTest(marker=marker):
                result = completed(
                    stdout=(
                        f"{marker}\r\nBrief ID: adaptive-1\r\n"
                        "Estimated reading time: 15 seconds.\r\n"
                    )
                )
                _rendered, brief_id = M.require_brief_output(result, marker)
                self.assertEqual(brief_id, "adaptive-1")


if __name__ == "__main__":
    unittest.main()
