"""Legacy Nero Stop hook, hard-disabled by hosted-only Host Mode."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

from nero_host_voice import resolve_session_route


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / ".codex" / "nero-host.json"
VOICE_WORKER = ROOT / "scripts" / "nero_host_voice.py"
VOICE_OUTPUT = ROOT / "data" / "host_voice" / "last_reply.wav"
HOSTED_ONLY_HARD_DISABLED = True
HOSTED_ONLY_REASON = "local Nero voice workers are hard-disabled by hosted-only Host Mode"


def _read_config(path: Path = CONFIG_PATH) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def extract_final_answer(transcript_path: Path) -> str | None:
    """Return the last model-visible final answer, never commentary or tools."""
    final: str | None = None
    try:
        lines = transcript_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            record = json.loads(line)
            payload = record.get("payload", {})
        except (json.JSONDecodeError, AttributeError):
            continue
        if not (
            record.get("type") == "response_item"
            and payload.get("type") == "message"
            and payload.get("role") == "assistant"
            and payload.get("phase") == "final_answer"
        ):
            continue
        pieces = [
            str(item.get("text", ""))
            for item in payload.get("content", [])
            if isinstance(item, dict) and item.get("type") == "output_text"
        ]
        text = "\n".join(piece for piece in pieces if piece).strip()
        if text:
            final = text
    return final


def launch_voice(
    text: str,
    session_id: str,
    *,
    worker: Path = VOICE_WORKER,
    output: Path = VOICE_OUTPUT,
    python_executable: str = sys.executable,
) -> int:
    """Detach a single voice job and return its process id without waiting."""
    if HOSTED_ONLY_HARD_DISABLED:
        raise RuntimeError(HOSTED_ONLY_REASON)
    text = text[:4096]  # Keep the Windows command line bounded; worker applies the speech cap.
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)  # Never leave a stale reply behind the stable link.
    command = [
        python_executable,
        str(worker),
        "--base64",
        encoded,
        "--output",
        str(output),
        "--session-id",
        session_id,
    ]
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs).pid


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    config = _read_config()
    if HOSTED_ONLY_HARD_DISABLED or config.get("runtime_policy") == "hosted-only":
        return 0
    if config.get("voice_enabled") is not True or config.get("auto_speak") is not True:
        return 0
    if config.get("delivery_policy") != "text-first-background":
        return 0
    transcript = payload.get("transcript_path")
    session_id = str(payload.get("session_id") or "")
    if not transcript or not session_id:
        return 0
    route = resolve_session_route(session_id)
    if route == "dispatch" and config.get("dispatch_delivery") == "disabled-no-receiver":
        return 0
    text = extract_final_answer(Path(transcript))
    if not text:
        return 0
    try:
        launch_voice(text, session_id)
    except OSError:
        return 0  # Voice must never delay or fail the text result.
    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
