"""Offline safety and behavior tests for the Nero Host Voice bridge."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import nero_host_voice as voice


class FakeResponse:
    status = 200
    headers = {"Content-Type": "audio/wav"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return b"RIFF" + b"\x00" * 32


def test_clean_for_speech_removes_code_links_and_tokens():
    raw = "# Done\nSee [the file](https://example.test). ```python\nsecret()\n``` sk-example_token_123456789"
    cleaned = voice.clean_for_speech(raw)
    assert cleaned == "Done See the file. [redacted]"


def test_clean_for_speech_truncates_at_a_sentence_boundary():
    cleaned = voice.clean_for_speech("First complete sentence. " + "word " * 100, max_chars=80)
    assert cleaned.startswith("First complete sentence.")
    assert cleaned.endswith("…")
    assert len(cleaned) <= 80


def test_only_loopback_speak_endpoint_is_allowed():
    assert voice._loopback_speak_endpoint("http://127.0.0.1:8080/api/speak").endswith("/api/speak")
    for endpoint in ("https://127.0.0.1/api/speak", "http://example.com/api/speak", "http://127.0.0.1/api/chat"):
        try:
            voice._loopback_speak_endpoint(endpoint)
        except voice.HostVoiceError:
            pass
        else:
            raise AssertionError(f"Unsafe endpoint accepted: {endpoint}")


def test_synthesize_is_hard_disabled_before_network():
    with patch.object(voice, "urlopen", return_value=FakeResponse()) as mocked:
        try:
            voice.synthesize("Hello Toni.", "http://127.0.0.1:8080/api/speak")
        except voice.HostVoiceError as exc:
            assert "hard-disabled" in str(exc)
        else:
            raise AssertionError("hosted-only policy must block local synthesis")
    mocked.assert_not_called()


def test_session_route_never_enables_desktop_playback():
    with TemporaryDirectory() as tmp:
        routes = Path(tmp) / "routes.json"
        routes.write_text(json.dumps({
            "sessions": {
                "desktop-session": {"route": "desktop", "expires_at": 200},
                "dispatch-session": {"route": "dispatch", "expires_at": 200},
            }
        }), encoding="utf-8")
        with patch.object(voice, "DEFAULT_ROUTES_PATH", routes):
            with patch.object(voice.time, "time", return_value=100):
                assert voice.should_play({"playback_target": "session-auto"}, session_id="desktop-session") == (False, "off")
                assert voice.should_play({"playback_target": "session-auto"}, session_id="dispatch-session") == (False, "off")
                assert voice.should_play({"playback_target": "session-auto"}, session_id="missing") == (False, "off")


def _run() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  OK {test.__name__}")
    print(f"\n  {len(tests)} Host Voice tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
