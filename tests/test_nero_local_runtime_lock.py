"""Behavior tests for the permanent local Nero runtime lock."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NeroLocalRuntimeLockTests(unittest.TestCase):
    def test_run_launcher_exits_before_port_or_server_work(self) -> None:
        launcher = _load("nero_run_lock", ROOT / "run.py")
        with mock.patch.object(launcher, "_port_busy") as port_busy:
            self.assertEqual(launcher.main(), 2)
        port_busy.assert_not_called()

    def test_bootstrap_exits_before_install_or_ollama_work(self) -> None:
        bootstrap = _load("nero_bootstrap_lock", ROOT / "bootstrap.py")
        with (
            mock.patch.object(bootstrap, "setup_venv") as setup_venv,
            mock.patch.object(bootstrap, "ensure_ollama") as ensure_ollama,
            mock.patch.object(bootstrap, "ensure_models") as ensure_models,
        ):
            self.assertEqual(bootstrap.main(), 2)
        setup_venv.assert_not_called()
        ensure_ollama.assert_not_called()
        ensure_models.assert_not_called()

    def test_every_python_and_shell_entry_has_a_real_guard(self) -> None:
        verifier = _load("nero_presence_verifier_for_lock", ROOT / "verify" / "verify_nero_global_presence.py")
        for path in verifier.PYTHON_LOCAL_ENTRY_PATHS:
            with self.subTest(path=path):
                verifier._assert_python_constant_true(path)
        for path in verifier.SHELL_LOCAL_ENTRY_PATHS:
            with self.subTest(path=path):
                verifier._assert_shell_guard(path)

    def test_direct_local_api_is_locked_before_startup_and_requests(self) -> None:
        from starlette.requests import Request
        from app import main as app_main

        downstream_called = False

        async def downstream(_request):
            nonlocal downstream_called
            downstream_called = True
            raise AssertionError("hosted-only middleware called downstream")

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/chat",
            "raw_path": b"/api/chat",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 8080),
        }
        response = asyncio.run(app_main.hosted_only_lock(Request(scope), downstream))
        self.assertEqual(response.status_code, 410)
        self.assertFalse(downstream_called)

        with mock.patch.object(app_main.db, "init_db") as init_db:
            if hasattr(app_main, "lifespan"):
                async def enter_lifespan() -> None:
                    async with app_main.lifespan(app_main.app):
                        pass

                with mock.patch.object(app_main, "load_config") as load_config:
                    asyncio.run(enter_lifespan())
                load_config.assert_not_called()
            else:
                app_main._startup()
        init_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
