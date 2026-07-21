"""Dependency-free runner for every Nero Host Presence behavior suite."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TESTS = (
    ROOT / "tests" / "test_nero_global_presence.py",
    ROOT / "tests" / "test_nero_host_voice.py",
    ROOT / "tests" / "test_nero_local_runtime_lock.py",
    ROOT / "tests" / "test_nero_voice_startup.py",
    ROOT / "tests" / "test_nero_voice_stop_hook.py",
    ROOT / "tests" / "test_nero_voice_warmup.py",
)


def main() -> int:
    for test in TESTS:
        print(f"RUN {test.relative_to(ROOT)}", flush=True)
        result = subprocess.run([sys.executable, str(test)], cwd=ROOT, check=False)
        if result.returncode != 0:
            print(f"FAIL {test.relative_to(ROOT)} (exit {result.returncode})", file=sys.stderr)
            return result.returncode
    print(f"Nero Host contract passed: {len(TESTS)} suites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
