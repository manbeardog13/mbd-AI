from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_without_site_packages(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-S", "-c", code],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class VoiceProfilesMinimalImportTests(unittest.TestCase):
    def test_package_import_does_not_require_numpy(self):
        result = run_without_site_packages(
            "import voice.profiles; from voice.profiles import load_cast"
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rendering_capability_reports_missing_numpy_clearly(self):
        result = run_without_site_packages(
            "from voice.profiles import VoiceProfile; "
            "VoiceProfile('test', 'test', 'missing.npy').load_blend()"
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NumPy is required to load voice blends", result.stderr)
        self.assertIn("optional voice capability", result.stderr)


if __name__ == "__main__":
    unittest.main()
