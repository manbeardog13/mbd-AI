"""Start your personal AI.

    python run.py

Then open the printed address in your browser. On the same machine that's
http://localhost:8080 . From your phone or laptop over Tailscale, use your
PC's Tailscale address instead (see docs/REMOTE_ACCESS.md).
"""
from __future__ import annotations

import uvicorn

from app import db
from app.config import load_config


def main() -> None:
    db.init_db()
    cfg = load_config()

    print()
    print(f"  ── {cfg.ai_name} ──")
    print(f"  Brain:  {cfg.model}  (via Ollama at {cfg.ollama_host})")
    print(f"  Open:   http://localhost:{cfg.port}")
    print("  Stop:   Ctrl+C")
    print()

    uvicorn.run("app.main:app", host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
