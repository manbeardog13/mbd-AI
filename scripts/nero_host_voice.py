"""Legacy Nero voice bridge, hard-disabled by hosted-only Host Mode."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / ".codex" / "nero-host.json"
DEFAULT_OUTPUT_PATH = ROOT / "data" / "host_voice" / "last_reply.wav"
DEFAULT_ROUTES_PATH = ROOT / "data" / "host_voice" / "session_routes.json"
HOSTED_ONLY_HARD_DISABLED = True
HOSTED_ONLY_REASON = "local Nero voice is hard-disabled by hosted-only Host Mode"


class HostVoiceError(RuntimeError):
    """A safe, user-facing host voice failure."""


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load and minimally validate the project-owned host voice settings."""
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HostVoiceError(f"Host voice config not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HostVoiceError(f"Host voice config is unreadable: {exc}") from exc
    if not isinstance(config, dict):
        raise HostVoiceError("Host voice config must contain a JSON object.")
    return config


def _loopback_speak_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise HostVoiceError("Host voice endpoint must be an HTTP loopback address.")
    if parsed.path.rstrip("/") != "/api/speak" or parsed.query or parsed.fragment:
        raise HostVoiceError("Host voice endpoint must target only /api/speak.")
    return endpoint


def clean_for_speech(text: str, max_chars: int = 700) -> str:
    """Turn a final reply into concise speech without code, links, or tokens."""
    max_chars = max(80, min(int(max_chars), 2000))
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    cleaned = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\b(?:sk|ghp|github_pat)-[A-Za-z0-9_-]{12,}\b", "[redacted]", cleaned)
    cleaned = re.sub(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", "[redacted]", cleaned, flags=re.I)
    cleaned = re.sub(r"</?[^>]+>", " ", cleaned)
    cleaned = re.sub(r"(?m)^\s{0,3}(?:#{1,6}|>|[-*+]\s|\d+[.)]\s)+", "", cleaned)
    cleaned = cleaned.translate(str.maketrans({"`": "", "*": "", "_": "", "~": ""}))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise HostVoiceError("There is no safe natural-language text to speak.")
    if len(cleaned) <= max_chars:
        return cleaned

    preview = cleaned[: max_chars + 1]
    floor = max_chars // 2
    sentence_end = max(preview.rfind(mark, floor, max_chars) for mark in ".!?")
    cut = sentence_end + 1 if sentence_end >= floor else preview.rfind(" ", floor, max_chars)
    if cut < floor:
        cut = max_chars
    return cleaned[:cut].rstrip(" ,;:-") + "…"


def synthesize(text: str, endpoint: str, timeout_seconds: float = 120.0) -> bytes:
    """Call Nero's voice-only endpoint and return validated WAV bytes."""
    if HOSTED_ONLY_HARD_DISABLED:
        raise HostVoiceError(HOSTED_ONLY_REASON)
    endpoint = _loopback_speak_endpoint(endpoint)
    request = Request(
        endpoint,
        data=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "audio/wav"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", response.getcode())
            reason = response.headers.get("X-Voice-Reason", "voice unavailable")
            if status == 204:
                raise HostVoiceError(f"Nero voice is unavailable: {reason}")
            audio = response.read()
            content_type = response.headers.get("Content-Type", "")
    except HostVoiceError:
        raise
    except Exception as exc:
        raise HostVoiceError(f"Nero voice request failed: {exc}") from exc
    if status != 200 or "audio/wav" not in content_type.lower() or not audio.startswith(b"RIFF"):
        raise HostVoiceError("Nero voice returned an invalid audio response.")
    return audio


def save_wav(audio: bytes, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_bytes(audio)
    temporary.replace(output_path)
    return output_path


def play_wav(path: Path) -> None:
    if HOSTED_ONLY_HARD_DISABLED:
        raise HostVoiceError(HOSTED_ONLY_REASON)
    if sys.platform != "win32":
        raise HostVoiceError("Automatic host voice playback currently requires Windows.")
    try:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)
    except Exception as exc:
        raise HostVoiceError(f"Nero voice playback failed: {exc}") from exc


def resolve_session_route(
    session_id: str | None = None,
    *,
    routes_path: Path | None = None,
    now: float | None = None,
) -> str:
    """Resolve the current short-lived startup route; fail closed to off."""
    routes_path = DEFAULT_ROUTES_PATH if routes_path is None else routes_path
    session_id = session_id or os.getenv("CODEX_THREAD_ID") or ""
    if not session_id:
        return "off"
    try:
        state = json.loads(routes_path.read_text(encoding="utf-8"))
        entry = state.get("sessions", {}).get(session_id, {})
        route = str(entry.get("route", "off"))
        expires_at = float(entry.get("expires_at", 0))
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError, AttributeError):
        return "off"
    now = time.time() if now is None else now
    return route if route in {"desktop", "dispatch", "off"} and expires_at > now else "off"


def should_play(config: dict, *, no_play: bool = False, session_id: str | None = None) -> tuple[bool, str]:
    """Return playback decision and resolved route for observability."""
    if HOSTED_ONLY_HARD_DISABLED:
        return False, "off"
    target = str(config.get("playback_target", "fixed"))
    if target == "session-auto":
        route = resolve_session_route(session_id)
        return route == "desktop" and not no_play, route
    enabled = bool(config.get("playback", True)) and not no_play
    return enabled, "desktop" if enabled else "off"


def _input_text(args: argparse.Namespace) -> str:
    if args.base64 is not None:
        try:
            return base64.b64decode(args.base64, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise HostVoiceError("The supplied speech text is not valid UTF-8 base64.") from exc
    if args.text is not None:
        return args.text
    return sys.stdin.read()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report the hard-disabled legacy Nero voice bridge.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--base64", help="UTF-8 reply text encoded as base64")
    source.add_argument("--text", help="Reply text (base64 is safer for shell use)")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--session-id", help="Session whose startup route controls playback")
    parser.add_argument("--no-play", action="store_true")
    parser.add_argument("--status", action="store_true", help="Validate settings without speaking")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config(args.config)
        hard_disabled = HOSTED_ONLY_HARD_DISABLED or config.get("runtime_policy") == "hosted-only"
        enabled = config.get("voice_enabled") is True and not hard_disabled
        if args.status:
            print(json.dumps({
                "enabled": enabled,
                "mode": config.get("mode"),
                "runtime_policy": config.get("runtime_policy"),
                "route": "off",
                "would_play": False,
                "reason": HOSTED_ONLY_REASON,
            }))
            return 0
        if hard_disabled:
            raise HostVoiceError(HOSTED_ONLY_REASON)
        if not enabled:
            raise HostVoiceError("Nero Host Voice is disabled in project settings.")
        endpoint = _loopback_speak_endpoint(str(config.get("endpoint", "")))
        text = clean_for_speech(_input_text(args), int(config.get("max_chars", 700)))
        audio = synthesize(text, endpoint)
        output = save_wav(audio, args.output.resolve())
        played, route = should_play(config, no_play=args.no_play, session_id=args.session_id)
        if played:
            play_wav(output)
        print(json.dumps({
            "spoken": True,
            "played": played,
            "route": route,
            "characters": len(text),
            "output": str(output),
        }))
        return 0
    except HostVoiceError as exc:
        print(f"Host Voice: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
