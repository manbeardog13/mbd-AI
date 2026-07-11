#!/usr/bin/env python3
"""
Nero — one-command setup & launcher.

Run this once with your system Python and it does everything:

    python bootstrap.py

It will:
  1. Check your Python version
  2. Create an isolated environment (.venv) and install dependencies
  3. Make sure Ollama is installed and running (with exact fix-it steps if not)
  4. Download Nero's brain (the model in config.yaml) if you don't have it
  5. Start Nero and tell you where to open it

It only uses Python's standard library, so it runs before anything is installed.
Re-running it is safe — it skips whatever is already done.

Options:
    python bootstrap.py --setup-only    # install everything but don't launch
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Always work from the folder this script lives in.
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

IS_WINDOWS = os.name == "nt"
VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / ("Scripts" if IS_WINDOWS else "bin") / (
    "python.exe" if IS_WINDOWS else "python"
)
OLLAMA_HOST = "http://127.0.0.1:11434"


# ---- pretty output ----------------------------------------------------

def step(msg: str) -> None:
    print(f"\n==> {msg}")


def ok(msg: str) -> None:
    print(f"    OK  {msg}")


def warn(msg: str) -> None:
    print(f"    !   {msg}")


def die(msg: str) -> None:
    print(f"\nXX  {msg}\n")
    sys.exit(1)


def banner() -> None:
    print("=" * 56)
    print("   Nero — setting up your personal AI")
    print("=" * 56)


# ---- helpers ----------------------------------------------------------

def read_model() -> str:
    """Read the model name from config without needing PyYAML (not yet installed)."""
    for name in ("config.yaml", "config.example.yaml"):
        p = ROOT / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("#") or not s.startswith("model:"):
                continue
            value = s.split(":", 1)[1].strip()
            # If the value isn't quoted, drop any trailing inline comment.
            if value and value[0] not in "\"'":
                value = value.split("#", 1)[0].strip()
            value = value.strip().strip('"').strip("'")
            if value:
                return value
    return "qwen2.5:14b"


def run(cmd: list[str], **kwargs) -> int:
    """Run a command, streaming its output. Returns the exit code."""
    try:
        return subprocess.run([str(c) for c in cmd], **kwargs).returncode
    except FileNotFoundError:
        return 127


def ollama_running() -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_HOST + "/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def model_installed(model: str) -> bool:
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=15
        )
        base = model.split(":")[0]
        return model in out.stdout or base in out.stdout
    except Exception:
        return False


def ollama_install_hint() -> str:
    if IS_WINDOWS:
        return (
            "Install Ollama for Windows:\n"
            "      • Download & run: https://ollama.com/download/windows\n"
            "        (or in PowerShell:  winget install Ollama.Ollama )"
        )
    if sys.platform == "darwin":
        return (
            "Install Ollama for macOS:\n"
            "      • Download: https://ollama.com/download/mac\n"
            "        (or:  brew install ollama )"
        )
    return (
        "Install Ollama for Linux:\n"
        "      • Run:  curl -fsSL https://ollama.com/install.sh | sh"
    )


# ---- steps ------------------------------------------------------------

def check_python() -> None:
    step("Checking Python version")
    if sys.version_info < (3, 10):
        die(
            f"Python 3.10+ is required (you have {sys.version.split()[0]}).\n"
            "    Get it from https://python.org/downloads and re-run this script."
        )
    ok(f"Python {sys.version.split()[0]}")


def setup_venv() -> None:
    step("Setting up the Python environment (.venv)")
    if VENV_PYTHON.exists():
        ok("Environment already exists")
    else:
        if run([sys.executable, "-m", "venv", str(VENV_DIR)]) != 0:
            die("Could not create the virtual environment.")
        ok("Created .venv")

    step("Installing dependencies (this can take a minute)")
    run([VENV_PYTHON, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    if run([VENV_PYTHON, "-m", "pip", "install", "-r", "requirements.txt"]) != 0:
        die("Dependency install failed. Check the output above and re-run.")
    ok("Dependencies installed")


def ensure_ollama() -> None:
    step("Checking Ollama (runs the model on your GPU)")
    if shutil.which("ollama") is None:
        die(
            "Ollama isn't installed yet.\n      "
            + ollama_install_hint()
            + "\n\n    Then run this script again:  python bootstrap.py"
        )
    ok("Ollama is installed")

    if not ollama_running():
        warn("Ollama isn't responding yet — trying to start it...")
        try:
            kwargs = {}
            if IS_WINDOWS:
                kwargs["creationflags"] = 0x00000008  # DETACHED_PROCESS
            else:
                kwargs["stdout"] = subprocess.DEVNULL
                kwargs["stderr"] = subprocess.DEVNULL
            subprocess.Popen(["ollama", "serve"], **kwargs)
        except Exception:
            pass
        for _ in range(10):
            time.sleep(1)
            if ollama_running():
                break
    if ollama_running():
        ok("Ollama is running")
    else:
        warn(
            "Couldn't confirm Ollama is running. Open the Ollama app "
            "(or run 'ollama serve'), then re-run this script."
        )


def ensure_model() -> None:
    model = read_model()
    step(f"Checking Nero's brain: {model}")
    if model_installed(model):
        ok("Model already downloaded")
        return
    print(f"    Downloading {model} (a few GB — one time only)...")
    if run(["ollama", "pull", model]) != 0:
        die(
            f"Couldn't download '{model}'.\n"
            "    Make sure Ollama is running, then re-run this script.\n"
            "    (You can also pick a smaller model in config.yaml — see docs/MODELS.md)"
        )
    ok("Model ready")


def launch() -> None:
    step("Starting Nero")
    print("    Open http://localhost:8080 in your browser.")
    print("    Stop Nero any time with Ctrl+C.\n")
    run([VENV_PYTHON, "run.py"])


# ---- main -------------------------------------------------------------

def main() -> None:
    setup_only = "--setup-only" in sys.argv[1:]
    banner()
    check_python()
    setup_venv()
    ensure_ollama()
    ensure_model()

    if setup_only:
        step("Setup complete")
        starter = "start.bat" if IS_WINDOWS else "./start.sh"
        print(f"    Everything is ready. Start Nero any time with:  {starter}")
        print("    (or:  python bootstrap.py )")
        return

    launch()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
