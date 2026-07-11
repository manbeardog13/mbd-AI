#!/usr/bin/env bash
# Start Nero on macOS / Linux:  ./start.sh
cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python" ]; then
    echo "First-time setup needed. Running bootstrap..."
    python3 bootstrap.py
else
    exec .venv/bin/python run.py
fi
