"""voice.local_tts.base — the TTSEngine contract (Voice Stage 1, API-first).

This is the *contract* every TTS engine implements, defined **before** any engine
body exists. "The engine is replaceable; Nero's personality is not"
(docs/VOICE.md). An engine's only job is to turn a finalized `VoiceRequest` into
audio and to report its own health — no cognition, no memory, no decisions, and
(Decision 1) it never touches the Trust Engine, the Action Journal, or capability
dispatch. Voice is an output interface.

Nothing engine-specific lives here. Concrete engines (kokoro, mms_hr, xtts) come
in later stages and subclass `BaseTTSEngine`; `NullEngine` is the always-
unavailable reference implementation and the ultimate fallback sentinel. Future
code depends on the `TTSEngine` Protocol, never on a concrete engine.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, runtime_checkable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EngineStatus(str, Enum):
    """An engine's runtime health, as reported by `health()`."""

    READY = "ready"              # available, last operation succeeded
    DEGRADED = "degraded"        # available, but a recent operation failed
    UNAVAILABLE = "unavailable"  # deps/models absent — cannot synthesize
    UNKNOWN = "unknown"          # not probed yet


@dataclass
class EngineHealth:
    """A point-in-time health report — Voice Telemetry data, never the Journal."""

    status: EngineStatus = EngineStatus.UNKNOWN
    detail: str = ""
    checked_at: str = ""
    last_success: str = ""
    last_failure: str = ""
    failure_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "status": self.status.value, "detail": self.detail,
            "checked_at": self.checked_at, "last_success": self.last_success,
            "last_failure": self.last_failure, "failure_reason": self.failure_reason,
        }


@dataclass
class VoiceRequest:
    """Finalized output from the Brain: text + delivery metadata.

    Voice NEVER produces this — it only receives it (Decision 1). `delivery`
    carries the Performance Director's instructions (emotion / authority / warmth /
    pace / …) derived from brain_context elsewhere; the engine only renders them.
    """

    text: str
    voice_id: str = ""          # which cast profile, e.g. "nero_prime"
    language: str = "en"        # language hint, e.g. "en" / "hr"
    speed: float = 1.0
    delivery: dict = field(default_factory=dict)


@dataclass
class AudioResult:
    """The rendered audio, or a clean failure. Best-effort: never raises to callers."""

    ok: bool
    audio: bytes = b""          # WAV bytes; empty on failure
    sample_rate: int = 0
    engine: str = ""
    voice_id: str = ""
    duration_ms: float = 0.0
    error: str = ""
    # Routing outcome, set ONLY by the VoiceManager (engines leave it ""):
    # "primary" | "fallback" | "text_only" — for future diagnostics.
    outcome: str = ""

    @classmethod
    def failure(cls, engine: str, error: str, voice_id: str = "") -> "AudioResult":
        return cls(ok=False, engine=engine, voice_id=voice_id, error=error)


@runtime_checkable
class TTSEngine(Protocol):
    """The replaceable engine contract. Everything downstream depends on THIS."""

    name: str

    def available(self) -> bool: ...
    def languages(self) -> list[str]: ...
    def voices(self) -> list[str]: ...
    def synthesize(self, request: VoiceRequest) -> AudioResult: ...
    def health(self) -> EngineHealth: ...


class BaseTTSEngine(ABC):
    """Shared, engine-agnostic scaffolding: health bookkeeping + timing, so a real
    engine body only implements the `_`-prefixed hooks (added in later stages).

    No engine-specific logic lives here — this is the standard health/synthesis
    envelope every engine gets for free, keeping `TTSEngine` behaviour consistent.
    """

    name: str = "base"
    _languages: tuple[str, ...] = ()
    _voices: tuple[str, ...] = ()

    def __init__(self) -> None:
        self._health = EngineHealth(status=EngineStatus.UNKNOWN, checked_at=_now())

    # ---- the public contract ----
    def available(self) -> bool:
        try:
            return bool(self._available())
        except Exception:  # noqa: BLE001 - an availability probe must never raise
            return False

    def languages(self) -> list[str]:
        return list(self._languages)

    def voices(self) -> list[str]:
        return list(self._voices)

    def health(self) -> EngineHealth:
        if not self.available():
            self._health.status = EngineStatus.UNAVAILABLE
            self._health.detail = "engine unavailable (deps/models absent)"
        self._health.checked_at = _now()
        return self._health

    def synthesize(self, request: VoiceRequest) -> AudioResult:
        """Render `request`, recording health + timing. Never raises (best-effort)."""
        if request is None or not (request.text or "").strip():
            return AudioResult.failure(self.name, "empty request")
        if not self.available():
            self._record_failure("engine unavailable")
            return AudioResult.failure(self.name, "engine unavailable", request.voice_id)
        started = time.perf_counter()
        try:
            data, rate = self._synthesize(request)
        except Exception as exc:  # noqa: BLE001 - best-effort; caller falls back
            self._record_failure(f"{type(exc).__name__}: {exc}")
            return AudioResult.failure(self.name, str(exc), request.voice_id)
        duration_ms = (time.perf_counter() - started) * 1000
        if not data:
            self._record_failure("engine returned no audio")
            return AudioResult.failure(self.name, "no audio produced", request.voice_id)
        self._record_success()
        return AudioResult(
            ok=True, audio=data, sample_rate=int(rate or 0), engine=self.name,
            voice_id=request.voice_id, duration_ms=round(duration_ms, 1),
        )

    # ---- health recording ----
    def _record_success(self) -> None:
        self._health.status = EngineStatus.READY
        self._health.last_success = _now()
        self._health.failure_reason = ""

    def _record_failure(self, reason: str) -> None:
        # available-but-failing = DEGRADED; otherwise UNAVAILABLE.
        self._health.status = (
            EngineStatus.DEGRADED if self.available() else EngineStatus.UNAVAILABLE
        )
        self._health.last_failure = _now()
        self._health.failure_reason = reason

    # ---- hooks a real engine implements in a later stage ----
    @abstractmethod
    def _available(self) -> bool: ...

    @abstractmethod
    def _synthesize(self, request: VoiceRequest) -> tuple[bytes, int]:
        """Return (wav_bytes, sample_rate). May raise — the envelope contains it."""
        ...


class NullEngine(BaseTTSEngine):
    """The always-unavailable reference engine: the fallback sentinel and a test
    double. Never produces audio; it exists to prove the contract's failure paths.
    """

    name = "null"

    def _available(self) -> bool:
        return False

    def _synthesize(self, request: VoiceRequest) -> tuple[bytes, int]:
        raise RuntimeError("NullEngine never synthesizes")
