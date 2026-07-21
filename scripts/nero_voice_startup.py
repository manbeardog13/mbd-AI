"""Legacy SessionStart helper, retained as a hosted-only no-op."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / ".codex" / "nero-host.json"
ROUTES_PATH = ROOT / "data" / "host_voice" / "session_routes.json"
REMOTE_ATTACHMENTS_ROOT = Path.home() / ".codex" / "codex-remote-attachments"
WARMUP_WORKER = ROOT / "scripts" / "nero_voice_warmup.py"
PRELOAD_FILES = (
    ROOT / "docs" / "NERO_CODEX_RUNTIME.md",
    ROOT / "docs" / "NERO_CODEX_MEMORY.md",
)
VALID_ROUTES = {"desktop", "dispatch", "off"}
HOSTED_ONLY_HARD_DISABLED = True
HOSTED_ONLY_REASON = "local Nero startup and preload are hard-disabled by hosted-only Host Mode"


def _read_json(path: Path, default: dict | None = None) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else (default or {})
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default or {}


def _settings(config_path: Path = CONFIG_PATH) -> dict:
    config = _read_json(config_path)
    audit = config.get("startup_audit", {})
    return audit if isinstance(audit, dict) else {}


def _has_remote_attachment(session_id: str, attachments_root: Path) -> bool:
    folder = attachments_root / session_id
    if not session_id or not folder.is_dir():
        return False
    try:
        return any(item.is_file() for item in folder.rglob("*"))
    except OSError:
        return False


def detect_route(
    session_id: str,
    *,
    env: dict[str, str] | None = None,
    attachments_root: Path = REMOTE_ATTACHMENTS_ROOT,
    now: float | None = None,
    settings: dict | None = None,
) -> tuple[str, str]:
    """Return a conservative route and a non-sensitive audit reason."""
    env = os.environ if env is None else env
    now = time.time() if now is None else now
    settings = _settings() if settings is None else settings

    explicit = str(env.get("NERO_VOICE_ROUTE", "")).strip().lower()
    if explicit in VALID_ROUTES:
        return explicit, "explicit-environment"

    originator = str(env.get("CODEX_INTERNAL_ORIGINATOR_OVERRIDE", "")).lower()
    if any(marker in originator for marker in ("dispatch", "remote", "mobile")):
        return "dispatch", "codex-originator"

    if _has_remote_attachment(session_id, attachments_root):
        return "dispatch", "remote-attachment-present"

    default_route = str(settings.get("default_route", "off")).lower()
    if default_route not in VALID_ROUTES:
        default_route = "off"
    return default_route, "configured-default"


def write_route(
    session_id: str,
    route: str,
    reason: str,
    *,
    routes_path: Path = ROUTES_PATH,
    now: float | None = None,
    lease_minutes: int = 240,
) -> dict:
    if HOSTED_ONLY_HARD_DISABLED:
        raise RuntimeError(HOSTED_ONLY_REASON)
    if not session_id:
        raise ValueError("Session id is required for a scoped voice route.")
    if route not in VALID_ROUTES:
        raise ValueError(f"Unsupported voice route: {route}")
    now = time.time() if now is None else now
    lease_minutes = max(1, min(int(lease_minutes), 1440))
    state = _read_json(routes_path, {"version": 1, "sessions": {}})
    sessions = state.setdefault("sessions", {})
    if not isinstance(sessions, dict):
        sessions = state["sessions"] = {}
    sessions = {
        key: value
        for key, value in sessions.items()
        if isinstance(value, dict) and float(value.get("expires_at", 0)) > now
    }
    state["sessions"] = sessions
    sessions[session_id] = {
        "route": route,
        "reason": reason,
        "updated_at": now,
        "expires_at": now + lease_minutes * 60,
    }
    routes_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = routes_path.with_suffix(routes_path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(routes_path)
    return sessions[session_id]


def preload_context(paths: tuple[Path, ...] = PRELOAD_FILES) -> str:
    """Load the complete compact Host Mode context for SessionStart injection."""
    if HOSTED_ONLY_HARD_DISABLED:
        raise RuntimeError(HOSTED_ONLY_REASON)
    chunks = ["NERO_HOST_PRELOAD_V1"]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            chunks.append(f"--- {path.name} ---\n{text}")
    return "\n\n".join(chunks)


def launch_voice_warmup(
    *,
    worker: Path = WARMUP_WORKER,
    python_executable: str = sys.executable,
) -> int:
    """Launch one detached warmup worker and return immediately."""
    if HOSTED_ONLY_HARD_DISABLED:
        raise RuntimeError(HOSTED_ONLY_REASON)
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
    return subprocess.Popen([python_executable, str(worker)], **kwargs).pid


def _hook_context(route: str, reason: str, preloaded: str = "") -> dict:
    if route == "desktop":
        instruction = "Nero Host Voice startup audit selected desktop playback. Return text first; the Stop hook may auto-play through the PC's default speakers."
    elif route == "dispatch":
        instruction = "Nero Host Voice startup audit detected Dispatch. Return text only; do not synthesize audio, play through the PC, or show a playback link."
    else:
        instruction = "Nero Host Voice startup audit selected silent mode. Return text only and do not auto-play audio."
    context = f"{instruction} Audit reason: {reason}."
    if preloaded:
        context += f"\n\nPreloaded project context follows; treat it as already read in full.\n{preloaded}"
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit and lease Nero's voice route for one Codex session.")
    parser.add_argument("--session-id", help="Override the hook/session id")
    parser.add_argument("--set-route", choices=sorted(VALID_ROUTES), help="Set a route explicitly")
    parser.add_argument("--audit", action="store_true", help="Print a compact audit result")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if HOSTED_ONLY_HARD_DISABLED:
        print(json.dumps({
            "enabled": False,
            "route": "off",
            "preloaded": False,
            "warmed": False,
            "reason": HOSTED_ONLY_REASON,
        }))
        return 0
    try:
        payload = {}
        if not sys.stdin.isatty():
            raw = sys.stdin.read().strip()
            if raw:
                payload = json.loads(raw)
        session_id = args.session_id or str(payload.get("session_id") or os.getenv("CODEX_THREAD_ID") or "")
        settings = _settings()
        if args.set_route:
            route, reason = args.set_route, "explicit-command"
        else:
            route, reason = detect_route(session_id, settings=settings)
        lease = int(settings.get("lease_minutes", 240))
        write_route(session_id, route, reason, lease_minutes=lease)
        source = str(payload.get("source") or "")
        if route == "desktop" and source == "startup" and settings.get("desktop_voice_warmup") is True:
            try:
                launch_voice_warmup()
            except OSError:
                pass
        if args.audit:
            print(json.dumps({"route": route, "reason": reason, "lease_minutes": lease}))
        else:
            preloaded = preload_context() if settings.get("preload_context") is True else ""
            print(json.dumps(_hook_context(route, reason, preloaded)))
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Nero voice startup audit failed safely: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
