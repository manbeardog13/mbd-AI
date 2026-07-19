"""voice.local_tts.voice_capability_graph — "can THIS voice perform right now?"

The Voice Platform's runtime directory of voice capabilities. It answers the
*live* question — can a given voice perform **right now** — not the static one
("does an engine exist"). Availability is always resolved by asking the engine's
current state (`engine.available()`), never cached as truth: runtime discovery
only.

**Naming (Toni's lock):** this is the **Voice Capability Graph**, never a
"Capability Registry" — that name belongs to the executive Capability Registry
(ADR-0007), a completely different subsystem on the executive path. This graph
touches nothing executive: it maps voice identity → engine → language → features →
availability → quality, and reports (as Voice Telemetry, never the Journal).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .base import TTSEngine


class QualityLevel(str, Enum):
    """A voice's quality tier — informs selection/fallback, not availability."""

    PREMIUM = "premium"
    STANDARD = "standard"
    BASIC = "basic"


@dataclass(frozen=True)
class VoiceCapability:
    """What a voice *is* (static identity) — not whether it can perform now."""

    voice_id: str                       # e.g. "nero_prime"
    engine: str                         # the provider engine's `name`
    languages: tuple[str, ...] = ()     # e.g. ("en", "hr")
    features: tuple[str, ...] = ()      # e.g. ("emotion", "effects", "streaming")
    quality: QualityLevel = QualityLevel.STANDARD


@dataclass
class ResolvedVoice:
    """A live resolution: the capability, its engine, and whether it can perform NOW."""

    capability: VoiceCapability
    engine: TTSEngine
    available: bool


def _safe_available(engine: TTSEngine) -> bool:
    try:
        return bool(engine.available())
    except Exception:  # noqa: BLE001 - an availability probe must never raise
        return False


class VoiceCapabilityGraph:
    """Runtime directory. Availability is resolved against the engine's LIVE state
    on every query — nothing is cached as "available", so an engine that goes down
    is reflected immediately (runtime discovery)."""

    def __init__(self) -> None:
        self._caps: dict[str, VoiceCapability] = {}      # voice_id -> capability
        self._engines: dict[str, TTSEngine] = {}         # engine name -> engine

    def register(self, capability: VoiceCapability, engine: TTSEngine) -> None:
        """Add a voice and the engine that provides it.

        Registration asserts nothing about live availability — that is always
        asked via `can_perform()`. The capability's declared engine must match the
        engine's own `name`, so the graph can't silently point a voice at the
        wrong engine.
        """
        if capability.engine != getattr(engine, "name", None):
            raise ValueError(
                f"capability.engine {capability.engine!r} != engine.name "
                f"{getattr(engine, 'name', None)!r}"
            )
        self._caps[capability.voice_id] = capability
        self._engines[engine.name] = engine

    def voices(self) -> list[str]:
        """Every registered voice id (regardless of live availability)."""
        return list(self._caps.keys())

    def get(self, voice_id: str) -> VoiceCapability | None:
        return self._caps.get(voice_id)

    def can_perform(self, voice_id: str) -> bool:
        """Can THIS voice perform RIGHT NOW? Registered AND its engine is live."""
        cap = self._caps.get(voice_id)
        if cap is None:
            return False
        engine = self._engines.get(cap.engine)
        return engine is not None and _safe_available(engine)

    def resolve(self, voice_id: str) -> ResolvedVoice | None:
        """The capability + its engine + live availability, or None if unknown."""
        cap = self._caps.get(voice_id)
        if cap is None:
            return None
        engine = self._engines.get(cap.engine)
        if engine is None:
            return None
        return ResolvedVoice(cap, engine, _safe_available(engine))

    def available_voices(self, language: str | None = None) -> list[VoiceCapability]:
        """Only the voices that can perform RIGHT NOW (optionally for a language)."""
        out: list[VoiceCapability] = []
        for voice_id, cap in self._caps.items():
            if not self.can_perform(voice_id):
                continue
            if language and language not in cap.languages:
                continue
            out.append(cap)
        return out

    def snapshot(self) -> list[dict]:
        """A telemetry view: every voice + its live availability + quality.

        Voice Telemetry data (engine status / availability) — never written to the
        Action Journal, which records executive actions only.
        """
        return [
            {
                "voice_id": voice_id, "engine": cap.engine,
                "languages": list(cap.languages), "features": list(cap.features),
                "quality": cap.quality.value, "available": self.can_perform(voice_id),
            }
            for voice_id, cap in self._caps.items()
        ]
