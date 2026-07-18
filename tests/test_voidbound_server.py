from __future__ import annotations

import importlib.util
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("serve_voidbound", ROOT / "scripts" / "serve_voidbound.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VoidboundServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MODULE.VoidboundHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get(self, path: str):
        return urlopen(self.base + path, timeout=2)  # noqa: S310 - loopback test fixture

    def test_health_identifies_the_static_host(self) -> None:
        with self.get("/health") as response:
            body = json.load(response)
        self.assertEqual(body, {"ok": True, "app": "nero-voidbound-codex/1"})

    def test_game_and_assets_are_served(self) -> None:
        for path, content_type in [
            ("/adventure/", "text/html"),
            ("/adventure/styles.css", "text/css"),
            ("/adventure/game.js", "text/javascript"),
            ("/adventure/assets/iskra-v2.webp", "image/webp"),
            ("/adventure/assets/nero-void-guardian-v2.webp", "image/webp"),
            ("/adventure/assets/mia-v2-provisional.webp", "image/webp"),
            ("/adventure/assets/voidbound-companions-keyart-v1.png", "image/png"),
            ("/static/icon.svg", "image/svg+xml"),
        ]:
            with self.subTest(path=path), self.get(path) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(content_type, response.headers["Content-Type"])
                self.assertGreater(len(response.read()), 100)

    def test_security_headers_deny_network_connections(self) -> None:
        with self.get("/adventure/") as response:
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("connect-src 'none'", response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")

    def test_unknown_and_traversal_paths_fail_closed(self) -> None:
        for path in ["/api/memories", "/static/%2e%2e/README.md", "/adventure/%2e%2e/index.html"]:
            with self.subTest(path=path), self.assertRaises(HTTPError) as raised:
                self.get(path)
            self.assertIn(raised.exception.code, {403, 404})
            raised.exception.close()


if __name__ == "__main__":
    unittest.main()
