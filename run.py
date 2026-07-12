"""Start your personal AI.

    python run.py

Then open the printed address in your browser. On the same machine that's
http://localhost:8080 . From your phone or laptop over Tailscale, use your
PC's Tailscale address instead (see docs/REMOTE_ACCESS.md).
"""
from __future__ import annotations

import socket
import sys

import uvicorn

from app import db
from app.config import load_config


def _port_busy(port: int) -> bool:
    """Is something already listening on this port on this machine?"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    db.init_db()
    cfg = load_config()

    # Friendly guard: if the port's taken (usually a leftover instance), say so
    # clearly with the exact fix, instead of a raw bind traceback.
    if _port_busy(cfg.port):
        print()
        print(f"  ⚠  Port {cfg.port} is already in use — {cfg.ai_name} may already be")
        print(f"     running. Open http://localhost:{cfg.port} to check.")
        print("     To stop the other instance and try again:")
        if sys.platform.startswith("win"):
            print(f"       Get-NetTCPConnection -LocalPort {cfg.port} -State Listen |")
            print("         ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
        else:
            print(f"       lsof -ti tcp:{cfg.port} | xargs kill")
        print("     (Or set a different `port:` in config.yaml.)")
        print()
        return

    print()
    print(f"  ── {cfg.ai_name} ──")
    print(f"  Brain:  {cfg.model}  (via Ollama at {cfg.ollama_host})")
    print(f"  Open:   http://localhost:{cfg.port}")
    print("  Stop:   Ctrl+C")
    print()

    uvicorn.run("app.main:app", host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
