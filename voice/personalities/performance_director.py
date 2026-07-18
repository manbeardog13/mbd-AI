"""voice.personalities.performance_director — "how should this be delivered?"

The Performance Director is a **pure, deterministic, presentation-layer
transformation**. It takes the Brain's raw *delivery intent* (the free-form
``delivery`` dict on a ``VoiceRequest``) and normalizes it into a canonical,
clamped, engine-agnostic ``DeliveryPlan`` — then returns a **new** ``VoiceRequest``
carrying that plan. Nothing else.

**The four-way split (this is the whole point).** docs/VOICE.md describes a single
"Voice Director" that chose *both* the voice *and* the delivery style. V1.2.1 split
that responsibility:

    Brain            decides WHAT is said        (cognition — elsewhere)
    Performance Dir. decides HOW it is delivered  (THIS module)
    Voice Manager    decides WHO says it          (routing — Stage 4)
    Engine           decides HOW audio is produced (synthesis — later)

The Director is the *delivery-style half* of the Bible's Voice Director, with the
routing half removed. It sits **upstream** of the Manager (Option A):

    Brain -> VoiceRequest(raw delivery) -> direct() -> VoiceRequest(canonical plan)
          -> Voice Manager (speak) -> engine (synthesize)

**It is (MAY):** a deterministic delivery-metadata → DeliveryPlan transformer.
**It is NOT (MAY NOT):** a reasoning engine, personality storage, a memory system,
an emotion-simulation system, a voice router, a fallback manager, a security
component, a capability, or an action executor. It performs **no** LLM call, **no**
randomness, **no** I/O, **no** text/sentiment analysis (it reads the *intent* dict,
never the *meaning* of the response text), and it makes **no** routing, voice,
engine, health, or capability decision. Same intent in -> identical plan out
(the Principle of Least Intelligence: the simplest deterministic mechanism that is
correct).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..local_tts.base import VoiceRequest

SCHEMA_VERSION = 1

# ---- canonical vocabularies (small + documented; engines honor best-effort) ----
CANONICAL_EMOTIONS = frozenset({
    "neutral", "serious", "warm", "playful", "calm", "intense", "confident", "gentle",
})
DEFAULT_EMOTION = "neutral"

CANONICAL_EFFECTS = frozenset({
    "subtle_system_alert", "whisper", "radio", "reverb", "emphasis",
})

PAUSE_LEVELS = frozenset({"none", "short", "long"})
DEFAULT_PAUSE = "short"

_PACE_WORDS = {"slow": 0.85, "normal": 1.0, "fast": 1.15}
DEFAULT_PACE = 1.0
_PACE_MIN, _PACE_MAX = 0.5, 2.0

DEFAULT_LEVEL = 0.5   # neutral midpoint for the 0..1 dials when unspecified


@dataclass(frozen=True)
class DeliveryPlan:
    """The canonical, engine-agnostic delivery instructions. Complete schema:
    every field always present and correctly typed, every value normalized. This
    is *how* a response is delivered — never *what*, *who*, or *whether*."""

    emotion: str = DEFAULT_EMOTION
    authority: float = DEFAULT_LEVEL
    warmth: float = DEFAULT_LEVEL
    intensity: float = DEFAULT_LEVEL
    humor: float = DEFAULT_LEVEL          # the TARS-style dial (Toni's standing requirement)
    pace: float = DEFAULT_PACE
    pauses: str = DEFAULT_PAUSE
    effects: tuple[str, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def as_dict(self) -> dict:
        """Deterministic serialization — the dict placed onto VoiceRequest.delivery."""
        return {
            "emotion": self.emotion,
            "authority": self.authority,
            "warmth": self.warmth,
            "intensity": self.intensity,
            "humor": self.humor,
            "pace": self.pace,
            "pauses": self.pauses,
            "effects": list(self.effects),
            "schema_version": self.schema_version,
        }


def _clamp01(value: object) -> float:
    """A number clamped to [0, 1]; anything unparseable / NaN -> the neutral default."""
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_LEVEL
    if v != v:            # NaN
        return DEFAULT_LEVEL
    return max(0.0, min(1.0, v))


def _normalize_emotion(value: object) -> str:
    if isinstance(value, str) and value.strip().lower() in CANONICAL_EMOTIONS:
        return value.strip().lower()
    return DEFAULT_EMOTION


def _normalize_pace(value: object) -> float:
    """A word (slow/normal/fast) or a numeric multiplier -> a clamped float; else default."""
    if isinstance(value, str):
        key = value.strip().lower()
        if key in _PACE_WORDS:
            return _PACE_WORDS[key]
        try:
            v = float(key)
        except ValueError:
            return DEFAULT_PACE
    else:
        try:
            v = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return DEFAULT_PACE
    if v != v:            # NaN
        return DEFAULT_PACE
    return max(_PACE_MIN, min(_PACE_MAX, v))


def _normalize_pauses(value: object) -> str:
    if isinstance(value, str) and value.strip().lower() in PAUSE_LEVELS:
        return value.strip().lower()
    return DEFAULT_PAUSE


def _normalize_effects(delivery: dict) -> tuple[str, ...]:
    """Accept ``effects`` (list) or the singular ``effect`` (str); keep only canonical
    names, deduped, order preserved. Unknown effects are dropped, never passed raw."""
    raw = delivery.get("effects", delivery.get("effect", ()))
    if isinstance(raw, str):
        candidates: list = [raw]
    elif isinstance(raw, (list, tuple)):
        candidates = list(raw)
    else:
        candidates = []
    out: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, str):
            continue
        name = item.strip().lower()
        if name in CANONICAL_EFFECTS and name not in seen:
            seen.add(name)
            out.append(name)
    return tuple(out)


class PerformanceDirector:
    """Stateless, deterministic delivery interpreter. Its whole surface is
    ``direct(request) -> VoiceRequest`` (plus ``plan()`` for the raw DeliveryPlan).
    No configuration, no state, no learning, no adaptation."""

    def plan(self, delivery: object) -> DeliveryPlan:
        """Normalize a raw delivery-intent dict into the canonical DeliveryPlan."""
        d = delivery if isinstance(delivery, dict) else {}
        return DeliveryPlan(
            emotion=_normalize_emotion(d.get("emotion")),
            authority=_clamp01(d.get("authority")),
            warmth=_clamp01(d.get("warmth")),
            intensity=_clamp01(d.get("intensity")),
            humor=_clamp01(d.get("humor")),
            pace=_normalize_pace(d.get("pace")),
            pauses=_normalize_pauses(d.get("pauses")),
            effects=_normalize_effects(d),
            schema_version=SCHEMA_VERSION,
        )

    def direct(self, request: VoiceRequest) -> VoiceRequest:
        """Return a NEW VoiceRequest whose ``delivery`` is the canonical plan.

        Shapes **delivery only**: ``text``, ``voice_id``, ``language`` and ``speed``
        pass through untouched, and the input request is never mutated. The Director
        never creates or changes ``voice_id`` — choosing the voice is the Manager's
        job, not the Director's.
        """
        plan = self.plan(request.delivery)
        return VoiceRequest(
            text=request.text,
            voice_id=request.voice_id,      # never invented, never altered — not routing
            language=request.language,
            speed=request.speed,
            delivery=plan.as_dict(),
        )


# Module-level convenience over a shared stateless Director (deterministic).
_DEFAULT_DIRECTOR = PerformanceDirector()


def direct(request: VoiceRequest) -> VoiceRequest:
    """Normalize ``request``'s delivery intent via the default Performance Director."""
    return _DEFAULT_DIRECTOR.direct(request)
