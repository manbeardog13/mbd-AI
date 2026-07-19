"""Cold file bridge for the opt-in Windows Desktop Familiar.

The bridge never launches the Familiar and never starts a model, server, or
background worker.  It only translates semantic PresenceIntent values into a
small, bounded command file when an already-running Familiar is explicitly
selected by its caller.
"""
from __future__ import annotations

import json
import msvcrt
import os
import tempfile
import time
import uuid
from pathlib import Path

from .base import PresenceRuntime
from ..types import PresenceIntent, PresenceLevel, PresenceState


class FamiliarRuntime(PresenceRuntime):
    """Translate renderer-neutral intents to the Familiar's v2 line protocol."""

    def __init__(self, command_path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self._path = Path(command_path or root / "familiar" / "runtime" / "command.txt")
        self._spool = self._path.parent / f"{self._path.stem}.d"
        self._running = False

    @property
    def name(self) -> str:
        return "familiar-file-v2"

    @property
    def max_presence_level(self) -> PresenceLevel:
        # The shipped overlay is an animated status surface. It does not yet
        # provide the eye tracking, gestures, or environmental interaction
        # implied by the higher capability tiers.
        return PresenceLevel.L1_MINIMAL_MANIFESTATION

    @property
    def supported_capabilities(self) -> set[str]:
        return {
            "ambient_glow", "state_indicator", "emergence_sequence",
        }

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        if self._running:
            self._write(json.dumps({
                "event": "pet.dismiss", "label": "",
                "confirmed": False, "provenance": "",
            }, separators=(",", ":")))
        self._running = False

    def is_running(self) -> bool:
        return self._running

    @staticmethod
    def _label(intent: PresenceIntent) -> str:
        raw = intent.metadata.get("label", "") if isinstance(intent.metadata, dict) else ""
        if not isinstance(raw, str):
            return ""
        return " ".join(ch for ch in raw.split() if ch.isprintable())[:160]

    @staticmethod
    def _command(intent: PresenceIntent) -> str:
        activity = ""
        if isinstance(intent.metadata, dict):
            value = intent.metadata.get("activity", "")
            if isinstance(value, str):
                activity = value.lower()
        activity_map = {
            "claude": "claude.started",
            "claude_channel": "claude.started",
            "codex": "codex.started",
            "working": "codex.started",
            "codex_build": "codex.started",
            "heavy": "agents.dual_active",
            "dual": "agents.dual_active",
            "dual_agent": "agents.dual_active",
            "failed": "task.failed",
            "review": "user.action_required",
            "waiting": "user.action_required",
            "critical": "system.critical",
        }
        if activity in activity_map:
            return activity_map[activity]
        if activity in {"success", "repository_push"}:
            metadata = intent.metadata if isinstance(intent.metadata, dict) else {}
            provenance = metadata.get("provenance", "")
            confirmed = metadata.get("confirmed") is True
            valid_provenance = (
                isinstance(provenance, str)
                and 0 < len(provenance) <= 160
                and provenance.strip() == provenance
                and all(ch.isprintable() for ch in provenance)
            )
            if confirmed and valid_provenance:
                return ("task.succeeded" if activity == "success"
                        else "git.push_succeeded")
        state_map = {
            PresenceState.ABSENT: "pet.dismiss",
            PresenceState.EMERGING: "runtime.started",
            PresenceState.IDLE: "all.work_complete",
            PresenceState.LISTENING: "user.mentions_nero",
            PresenceState.THINKING: "nero.thinking",
            PresenceState.SPEAKING: "nero.speaking",
            PresenceState.ALERT: "user.action_required",
            # CELEBRATING is presentation intent, not proof of completion.
            PresenceState.CELEBRATING: "all.work_complete",
            PresenceState.CONCERNED: "task.failed",
            PresenceState.DISSOLVING: "pet.dismiss",
        }
        return state_map.get(intent.state, "all.work_complete")

    def set_intent(self, intent: PresenceIntent) -> None:
        if not self._running:
            return
        command = self._command(intent)
        label = self._label(intent)
        metadata = intent.metadata if isinstance(intent.metadata, dict) else {}
        confirmed = command in {"task.succeeded", "git.push_succeeded"}
        provenance = metadata.get("provenance", "") if confirmed else ""
        envelope = {
            "event": command,
            "label": label,
            "confirmed": confirmed,
            "provenance": provenance,
        }
        self._write(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))

    def _write(self, payload: str) -> None:
        if (not payload or len(payload) > 512
                or any(ch in payload for ch in "\r\n\0")):
            raise ValueError("Familiar command is invalid")
        self._spool.mkdir(parents=True, exist_ok=True)
        lock_path = self._spool / ".capacity.lock"
        with open(lock_path, "a+b") as lock:
            if lock.seek(0, os.SEEK_END) == 0:
                lock.write(b"\0"); lock.flush(); os.fsync(lock.fileno())
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            try:
                pending_count = pending_bytes = 0
                for path in self._spool.glob("*.cmd"):
                    try:
                        pending_bytes += path.stat().st_size
                        pending_count += 1
                    except FileNotFoundError:
                        continue
                if pending_count >= 32 or pending_bytes >= 16384:
                    raise RuntimeError(
                        "Familiar event spool is full; consumer acknowledgement required")
                name = f"{time.time_ns():020d}-{os.getpid():010d}-{uuid.uuid4().hex}.cmd"
                destination = self._spool / name
                fd, tmp = tempfile.mkstemp(
                    prefix=".event-", suffix=".tmp", dir=self._spool)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(payload + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(tmp, destination)
                finally:
                    try:
                        os.unlink(tmp)
                    except FileNotFoundError:
                        pass
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
