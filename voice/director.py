"""The Voice Director.

One entry point:

    from voice import director as voice_director
    result = voice_director.synthesize("nero_prime", "Good evening, Toni.")
    if result.audio:
        play(result.audio)   # 24 kHz mono 16-bit PCM WAV bytes
    else:
        log(result.reason)   # "unsupported-language" | "unknown-profile" | ...

Delegates to:
    - voice.language.profile_supports_text(...)        — language routing (Phase 3+4)
    - voice.profiles.get_profile(name)                — resolves the logical
      identity into a full config (blend + speed + effects)
    - voice.profiles.synthesize_with_profile(...)     — runs Kokoro + banshee
    - _wav_bytes(...)                                  — encodes to WAV

Caches the Kokoro engine (one instance per process, serialized under a lock)
so repeated calls don't reload the 310 MB model. Returns a ``SynthesisResult``
where ``audio`` is ``None`` when synthesis did not produce audio; ``reason``
always tells the caller why so it can decide what to signal upstream.
"""
from __future__ import annotations

import io
import logging
import threading
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np

from . import events as voice_events
from .language import detect_language, profile_supports_text
from .profiles import get_profile, synthesize_with_profile

log = logging.getLogger("nero.voice.director")

_REPO_ROOT = Path(__file__).resolve().parent.parent

_lock = threading.RLock()
_kokoro = None  # cached engine, lazy-loaded


SynthesisReason = Literal[
    "ok",                    # audio produced normally
    "empty-text",            # caller passed no text
    "unknown-profile",       # profile name did not resolve
    "unsupported-language",  # profile.lang does not match the detected language of text
    "engine-unavailable",    # kokoro-onnx not installed / Kokoro failed to load
    "synthesis-failed",      # engine raised during synthesis
]


@dataclass(frozen=True)
class SynthesisResult:
    """What ``synthesize`` returns. ``reason`` is always populated.

    Callers may branch on ``audio`` (truthy = play it) and use ``reason`` to
    decide what to signal upstream (HTTP header, UI hint, log line).
    """

    audio: bytes | None
    reason: SynthesisReason
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.reason == "ok" and self.audio is not None


def _ensure_kokoro():
    """Return a cached Kokoro instance. Loads on first call under a lock."""
    global _kokoro
    with _lock:
        if _kokoro is None:
            # Import lazily so this module is safe to import even if kokoro-onnx
            # is not installed (the director just won't be able to synthesize).
            from kokoro_onnx import Kokoro

            model = _REPO_ROOT / "models" / "kokoro-v1.0.onnx"
            voices = _REPO_ROOT / "models" / "voices-v1.0.bin"
            _kokoro = Kokoro(str(model), str(voices))
        return _kokoro


def _wav_bytes(samples: np.ndarray, rate: int) -> bytes:
    """Encode a float32 mono waveform (-1..1) as 16-bit PCM WAV bytes.

    Matches the WAV encoding used by ``app/tts.py::_wav_bytes`` so the audio
    format on the wire is unchanged.
    """
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate) or 24000)
        w.writeframes(pcm)
    return buf.getvalue()


def synthesize(profile_name: str, text: str) -> SynthesisResult:
    """Speak ``text`` in the named voice profile.

    Owns language routing — if the profile's ``lang`` doesn't match the
    detected language of the text, returns ``SynthesisResult(audio=None,
    reason="unsupported-language", metadata={...})`` without invoking Kokoro.
    Callers (typically the ``/api/speak`` handler) use ``reason`` to signal
    upstream (e.g. an ``X-Voice-Reason`` HTTP header).

    Voice is best-effort — this function does not raise. Every failure path
    is captured as a specific ``SynthesisReason``.
    """
    text = (text or "").strip()
    if not text:
        return SynthesisResult(audio=None, reason="empty-text")

    try:
        profile = get_profile(profile_name)
    except KeyError as exc:
        log.warning("unknown voice profile: %s (%s)", profile_name, exc)
        return SynthesisResult(
            audio=None,
            reason="unknown-profile",
            metadata={"profile": profile_name, "detail": str(exc)},
        )

    # Language routing — the Voice Director owns this. Refuse to synthesize
    # rather than produce garbled cross-language audio.
    if not profile_supports_text(profile, text):
        detected = detect_language(text)
        log.info(
            "profile %s cannot voice text — profile.lang=%s, detected=%s",
            profile_name,
            profile.lang,
            detected,
        )
        voice_events.emit(
            "voice.unsupported_language",
            profile_name,
            detected=detected,
            profile_lang=profile.lang,
            text_length=len(text),
        )
        return SynthesisResult(
            audio=None,
            reason="unsupported-language",
            metadata={"detected": detected, "profile_lang": profile.lang},
        )

    try:
        kokoro = _ensure_kokoro()
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        log.warning("kokoro not available: %s", exc)
        return SynthesisResult(
            audio=None,
            reason="engine-unavailable",
            metadata={"detail": str(exc)},
        )

    voice_events.emit("voice.started", profile_name, text_length=len(text))
    try:
        samples, rate = synthesize_with_profile(profile, text, kokoro)
        wav = _wav_bytes(samples, rate)
        duration_s = round(len(samples) / rate, 3) if rate else 0.0
        voice_events.emit(
            "voice.speaking",
            profile_name,
            sample_rate=int(rate),
            duration_s=duration_s,
            byte_length=len(wav),
        )
        voice_events.emit("voice.finished", profile_name, duration_s=duration_s)
        return SynthesisResult(
            audio=wav,
            reason="ok",
            metadata={"sample_rate": int(rate), "duration_s": duration_s},
        )
    except Exception as exc:  # noqa: BLE001 — voice is best-effort, never break chat
        log.warning("synthesis failed (profile=%s): %s", profile_name, exc)
        voice_events.emit("voice.interrupted", profile_name, reason=str(exc))
        return SynthesisResult(
            audio=None,
            reason="synthesis-failed",
            metadata={"detail": str(exc)},
        )


def available(profile_name: str = "nero_prime") -> bool:
    """Cheap probe: does the given profile exist and can we import Kokoro?"""
    try:
        get_profile(profile_name)
    except KeyError:
        return False
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False
    return True
