#!/usr/bin/env python3
"""Verify the GPU. Reports the NVIDIA card + VRAM, or skips on a CPU-only box.

On the local Windows workstation this should PASS and list the GPU. In the
cloud dev environment there's no GPU, so it SKIPs (exit 2) rather than fails.
"""
from __future__ import annotations

import shutil
import subprocess
import sys


def main() -> int:
    if shutil.which("nvidia-smi") is None:
        print("  No nvidia-smi found — this machine is running in CPU mode.")
        print("  On your Windows PC this should list your NVIDIA GPU.")
        return 2  # skip, not fail

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  nvidia-smi failed to run: {exc}")
        return 1

    if out.returncode != 0 or not out.stdout.strip():
        print("  nvidia-smi reported no GPUs.")
        return 2

    for line in out.stdout.strip().splitlines():
        print(f"  GPU: {line.strip()}")
    print("  NVIDIA GPU detected and ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
