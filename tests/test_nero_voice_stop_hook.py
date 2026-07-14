"""Offline tests for Nero's non-blocking Stop hook."""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import nero_voice_stop_hook as stop_hook


def _record(phase: str, text: str) -> str:
    return json.dumps({
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "phase": phase,
            "content": [{"type": "output_text", "text": text}],
        },
    })


def test_extracts_final_answer_not_commentary():
    with TemporaryDirectory() as tmp:
        transcript = Path(tmp) / "turn.jsonl"
        transcript.write_text(
            _record("commentary", "Working on it") + "\n" + _record("final_answer", "Ready, Toni."),
            encoding="utf-8",
        )
        assert stop_hook.extract_final_answer(transcript) == "Ready, Toni."


def test_launch_voice_is_hard_disabled():
    with TemporaryDirectory() as tmp:
        output = Path(tmp) / "reply.wav"
        output.write_bytes(b"old")
        with patch.object(stop_hook.subprocess, "Popen") as mocked:
            try:
                stop_hook.launch_voice(
                    "Ready, Toni.", "session-1", worker=Path("worker.py"), output=output,
                    python_executable="python",
                )
            except RuntimeError as exc:
                assert "hard-disabled" in str(exc)
            else:
                raise AssertionError("hosted-only policy must block voice workers")
        mocked.assert_not_called()
        assert output.exists()


def test_dispatch_without_receiver_does_not_launch_worker():
    with TemporaryDirectory() as tmp:
        transcript = Path(tmp) / "turn.jsonl"
        transcript.write_text(_record("final_answer", "Ready, Toni."), encoding="utf-8")
        payload = json.dumps({"session_id": "session-1", "transcript_path": str(transcript)})
        config = {
            "voice_enabled": True,
            "auto_speak": True,
            "delivery_policy": "text-first-background",
            "dispatch_delivery": "disabled-no-receiver",
        }
        with (
            patch.object(stop_hook, "_read_config", return_value=config),
            patch.object(stop_hook, "resolve_session_route", return_value="dispatch"),
            patch.object(stop_hook, "launch_voice") as launch,
            patch.object(stop_hook.sys, "stdin") as stdin,
        ):
            stdin.read.return_value = payload
            assert stop_hook.main() == 0
        launch.assert_not_called()


def _run() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"  OK {test.__name__}")
    print(f"\n  {len(tests)} Stop-hook tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
