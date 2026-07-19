#!/usr/bin/env python3
"""Loopback-only static host for Nero: Voidbound Codex.

This is deliberately separate from Nero's disabled standalone runtime. It
serves immutable game assets, exposes no application API, and writes no data.
Browser persistence stays in localStorage.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = (ROOT / "app" / "static").resolve()
GAME_ROOT = (STATIC_ROOT / "adventure").resolve()
GAME_ENTRY = (GAME_ROOT / "index.html").resolve()
SERVER_ID = "nero-voidbound-codex/1"
CONTENT_TYPE_OVERRIDES = {
    # Project-owned contract: do not inherit host registry disagreement between
    # application/javascript and text/javascript for executable assets.
    ".js": "text/javascript; charset=utf-8",
    ".webp": "image/webp",
}


class VoidboundHandler(BaseHTTPRequestHandler):
    server_version = SERVER_ID

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        path = unquote(urlsplit(self.path).path)
        if path == "/health":
            self._send_bytes(
                json.dumps({"ok": True, "app": SERVER_ID}).encode("utf-8"),
                "application/json; charset=utf-8",
                cache=False,
            )
            return
        if path in {"/", "/adventure", "/adventure/"}:
            self._send_file(GAME_ENTRY, cache=False)
            return
        if path.startswith("/adventure/"):
            base_root = GAME_ROOT
            relative_path = path.removeprefix("/adventure/")
        elif path.startswith("/static/"):
            base_root = STATIC_ROOT
            relative_path = path.removeprefix("/static/")
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        candidate = (base_root / relative_path).resolve()
        try:
            candidate.relative_to(base_root)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_file(candidate, cache=True)

    def _send_file(self, path: Path, *, cache: bool) -> None:
        content_type = CONTENT_TYPE_OVERRIDES.get(path.suffix.lower())
        if content_type is None:
            content_type, _ = mimetypes.guess_type(path.name)
        self._send_bytes(path.read_bytes(), content_type or "application/octet-stream", cache=cache)

    def _send_bytes(self, payload: bytes, content_type: str, *, cache: bool) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "public, max-age=3600" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'none'; "
            "media-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        # Keep the launcher quiet; failures remain visible via HTTP status.
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve Voidbound Codex on loopback only.")
    parser.add_argument("--port", type=int, default=8788)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("error: --port must be between 1024 and 65535")
    if not GAME_ENTRY.is_file():
        raise SystemExit(f"error: game entry not found: {GAME_ENTRY}")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), VoidboundHandler)
    print(f"Voidbound Codex: http://127.0.0.1:{args.port}/adventure", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
