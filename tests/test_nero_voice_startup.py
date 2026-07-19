"""Offline tests for the one-shot Nero SessionStart routing audit."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import nero_voice_startup as startup


SETTINGS = {"default_route": "desktop", "lease_minutes": 30}


def test_recent_remote_attachment_selects_dispatch():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        marker = root / "session" / "upload" / "photo.jpg"
        marker.parent.mkdir(parents=True)
        marker.write_bytes(b"test")
        marker.touch()
        route, reason = startup.detect_route("session", env={}, attachments_root=root, settings=SETTINGS)
        assert (route, reason) == ("dispatch", "remote-attachment-present")


def test_remote_attachment_keeps_dispatch_classification():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        marker = root / "session" / "photo.jpg"
        marker.parent.mkdir(parents=True)
        marker.write_bytes(b"test")
        route, reason = startup.detect_route(
            "session", env={}, attachments_root=root, now=marker.stat().st_mtime + 7200, settings=SETTINGS,
        )
        assert (route, reason) == ("dispatch", "remote-attachment-present")


def test_no_dispatch_signal_uses_configured_default():
    with TemporaryDirectory() as tmp:
        route, reason = startup.detect_route(
            "session", env={}, attachments_root=Path(tmp), settings=SETTINGS,
        )
        assert (route, reason) == ("desktop", "configured-default")


def test_explicit_route_wins():
    route, reason = startup.detect_route("session", env={"NERO_VOICE_ROUTE": "off"}, settings=SETTINGS)
    assert (route, reason) == ("off", "explicit-environment")


def test_route_lease_is_hard_disabled():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "routes.json"
        try:
            startup.write_route(
                "session", "desktop", "test", routes_path=path, now=100, lease_minutes=30,
            )
        except RuntimeError as exc:
            assert "hard-disabled" in str(exc)
        else:
            raise AssertionError("hosted-only policy must block route leases")
        assert not path.exists()


def test_preload_is_hard_disabled():
    with TemporaryDirectory() as tmp:
        first = Path(tmp) / "runtime.md"
        second = Path(tmp) / "memory.md"
        first.write_text("runtime sentinel", encoding="utf-8")
        second.write_text("memory sentinel", encoding="utf-8")
        try:
            startup.preload_context((first, second))
        except RuntimeError as exc:
            assert "hard-disabled" in str(exc)
        else:
            raise AssertionError("hosted-only policy must block project preloading")


def test_warmup_launch_is_hard_disabled():
    with patch.object(startup.subprocess, "Popen") as mocked:
        try:
            startup.launch_voice_warmup(worker=Path("warm.py"), python_executable="python")
        except RuntimeError as exc:
            assert "hard-disabled" in str(exc)
        else:
            raise AssertionError("hosted-only policy must block voice warmup")
    mocked.assert_not_called()


def _run() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  OK {test.__name__}")
    print(f"\n  {len(tests)} startup voice-route tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
