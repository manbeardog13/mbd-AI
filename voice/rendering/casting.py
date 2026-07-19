"""voice.rendering.casting — the Voice Casting mapper (pure, deterministic).

The answer to the one Stage-13 question — *who owns `DeliveryPlan → RenderingProfile`?*
— is **Candidate C: a new pure mapper**, here. It combines a persona's IDENTITY-derived
base rendering (from `RenderingProfiles`) with the moment's `DeliveryPlan` **modulation**
into a final engine-agnostic `RenderingProfile`:

    cast(voice_id, delivery) = base(voice_id) ⊕ modulate(delivery)

**It owns:** deterministic translation from feeling → rendering.
**It refuses:** state · routing · fallback · voice selection · health · telemetry ·
learning · I/O · randomness. Same `(voice_id, delivery)` in → identical profile out.

It reads the `delivery` dict **duck-typed** (the `pace` / `intensity` keys a Stage-6
`DeliveryPlan` carries) and imports **nothing** about the Voice Manager, Capability
Graph, Engine Health, Telemetry, or Startup — the dependency is one-way. The result is
placed on a new `VoiceRequest`'s `delivery` field (reusing the sealed free-form seam),
so the semantic DeliveryPlan is consumed here and never reaches the engine.
"""
from __future__ import annotations

from ..local_tts.base import VoiceRequest
from .profile import RenderingProfile, RenderingProfiles

_NEUTRAL_PACE = 1.0        # a Stage-6 DeliveryPlan.pace of 1.0 == no change
_NEUTRAL_INTENSITY = 0.5   # a Stage-6 DeliveryPlan.intensity midpoint


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _num(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    v = float(value)
    return default if v != v else v        # NaN -> default


class VoiceCasting:
    """Casts an utterance into a rendering. A thin, stateless, deterministic bridge —
    constructed once over the loaded rendering data, then called per utterance."""

    def __init__(self, profiles: RenderingProfiles) -> None:
        self._profiles = profiles

    def cast(self, voice_id: str, delivery: object = None) -> RenderingProfile:
        """`base(voice_id)` modulated by the DeliveryPlan's `pace` / `intensity`.
        Feeling never changes *who* (`voice_character` stays the persona's), only *how*
        (speed / energy). Minimal + deterministic; richer modulation is additive."""
        base = self._profiles.get(voice_id or "")
        d = delivery if isinstance(delivery, dict) else {}
        pace = _num(d.get("pace"), _NEUTRAL_PACE)
        intensity = _num(d.get("intensity"), _NEUTRAL_INTENSITY)
        return RenderingProfile(
            voice_character=base.voice_character,             # identity-driven, never modulated
            speed=_clamp(base.speed * pace, 0.5, 2.0),        # pace scales the persona's baseline
            pitch=base.pitch,
            energy=_clamp((base.energy + intensity) / 2.0, 0.0, 1.0),
            pause_style=base.pause_style,
            schema_version=base.schema_version,
        )

    def cast_request(self, request: VoiceRequest) -> VoiceRequest:
        """Return a NEW VoiceRequest whose `delivery` carries the RenderingProfile
        (replacing the semantic DeliveryPlan). `text` / `voice_id` / `language` /
        `speed` pass through untouched; the input is never mutated."""
        profile = self.cast(request.voice_id, request.delivery)
        return VoiceRequest(
            text=request.text, voice_id=request.voice_id, language=request.language,
            speed=request.speed, delivery=profile.as_dict(),
        )
