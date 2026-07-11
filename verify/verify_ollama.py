#!/usr/bin/env python3
"""Verify Ollama: installed, running, and Nero's configured model is present.

Fails (exit 1) with an exact fix-it line for whichever step is missing, so it
doubles as a troubleshooting tool on the local PC.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "http://127.0.0.1:11434"


def read_model() -> str:
    """Read the configured model without needing PyYAML (stdlib only)."""
    for name in ("config.yaml", "config.example.yaml"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("#") or not s.startswith("model:"):
                continue
            value = s.split(":", 1)[1].strip()
            if value and value[0] not in "\"'":
                value = value.split("#", 1)[0].strip()
            value = value.strip().strip('"').strip("'")
            if value:
                return value
    return "qwen2.5:14b"


def server_up() -> bool:
    try:
        with urllib.request.urlopen(HOST + "/api/tags", timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    if shutil.which("ollama") is None:
        print("  XX Ollama is not installed.")
        print("     Fix: install from https://ollama.com/download")
        return 1
    print("  OK Ollama is installed.")

    if not server_up():
        print("  XX Ollama server isn't reachable at 127.0.0.1:11434.")
        print("     Fix: start the Ollama app, or run `ollama serve`.")
        return 1
    print("  OK Ollama server is running.")

    model = read_model()
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=15
        )
        names = [ln.split()[0] for ln in out.stdout.splitlines()[1:] if ln.split()]
    except Exception as exc:  # noqa: BLE001
        print(f"  XX couldn't list Ollama models: {exc}")
        return 1

    wanted = {model}
    if ":" not in model:
        wanted.add(f"{model}:latest")
    if any(n in wanted for n in names):
        print(f"  OK Nero's model '{model}' is installed.")
        return 0

    print(f"  XX Nero's model '{model}' isn't installed.")
    print(f"     Fix: ollama pull {model}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
