"""Semantic-intent → abstract-parameter → Cubism-parameter translation.

Three layers, on purpose:

1. **Semantic** — ``PresenceIntent`` (state, emotion, intensity). What the
   brain says. Renderer-agnostic. NEVER changes when the runtime changes.

2. **Abstract parameter** — a small vocabulary of renderer-neutral floats
   (``wolf_eye_intensity``, ``mist_density``, ``through_glow_intensity``,
   ``overall_visibility``). Named for what they *mean*, not what any
   specific rig calls them. This is the layer that codifies the Visual
   Bible §11 rules (wolf eyes appear first, dissolve last, etc.).

3. **Cubism parameter** — the actual Live2D parameter IDs the rig exposes
   (``ParamNeroWolfEyeGlow`` etc.). This mapping is a **single dictionary**
   at the bottom of this module; an artist rigging the model can rename
   parameters in their model, and only ``CUBISM_PARAM_MAP`` here changes.
   No Presence Director, no protocol, no config touched.

If Nero ever migrates from Live2D to Unreal (or Godot), a new file
alongside this one (``unreal_parameter_map.py``) reimplements the second
layer against Unreal-specific parameters. Layer 1 stays untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..types import EmotionState, PresenceIntent, PresenceState


# ---------------------------------------------------------------------------
# Layer 2 — abstract, renderer-neutral parameter names.
# These are the "controls" a presence rig conceptually exposes. Rigs on
# different engines implement them under their own conventions.
# ---------------------------------------------------------------------------

# Named for meaning. Keep this list small; expand only when the Visual Bible
# introduces new visual capabilities. Each key MUST be a float in [0.0, 1.0].
ABSTRACT_PARAMS: tuple[str, ...] = (
    "overall_visibility",     # gates the whole character in/out (0 = fully absent)
    "wolf_eye_intensity",     # brightness/bloom of the wolf-pauldron glow
    "mist_density",           # violet-mist ambient particle density
    "through_glow_intensity", # subtle glow behind the sunglass lenses
    "warmth_bloom",           # rare warm-rim highlight; only nonzero on WARM emotion
)


@dataclass(frozen=True)
class AbstractFrame:
    """A single frame of abstract-parameter values."""
    values: dict[str, float] = field(default_factory=dict)

    def clamped(self) -> "AbstractFrame":
        """Return a new frame with every value clamped to [0.0, 1.0]."""
        return AbstractFrame({k: max(0.0, min(1.0, float(v))) for k, v in self.values.items()})


# ---------------------------------------------------------------------------
# Layer 1 → Layer 2 : semantic intent → abstract parameters.
# Encodes the Visual Bible §9 (animation personality) and §11 (manifestation
# sequences). If the bible changes, adjust this function.
# ---------------------------------------------------------------------------

def intent_to_abstract(intent: PresenceIntent) -> AbstractFrame:
    """Translate a PresenceIntent into a frame of abstract parameter values.

    Pure function — no I/O, no state. Deterministic. Bible §11 rules baked in:
    during EMERGING the wolf eyes appear first and the through-glow arrives
    late; during DISSOLVING the wolf eyes are the last thing to dim.
    """
    s = intent.state
    e = intent.emotion
    i = intent.intensity

    # Warmth bloom is EMOTION-driven, not state-driven. Rarely triggered.
    warm = 0.35 if e == EmotionState.WARM else 0.0

    if s == PresenceState.ABSENT:
        return AbstractFrame({
            "overall_visibility":     0.0,
            "wolf_eye_intensity":     0.0,
            "mist_density":           0.0,
            "through_glow_intensity": 0.0,
            "warmth_bloom":           0.0,
        }).clamped()

    if s == PresenceState.EMERGING:
        # Wolf eyes appear first — leading the intensity by 40%, clamped.
        # Through-glow appears late — only after intensity crosses 0.4.
        return AbstractFrame({
            "overall_visibility":     i,
            "wolf_eye_intensity":     min(1.0, i * 1.5),
            "mist_density":           min(1.0, i * 1.1),
            "through_glow_intensity": max(0.0, (i - 0.4)) * 1.5,
            "warmth_bloom":           warm * i,
        }).clamped()

    if s == PresenceState.IDLE:
        return AbstractFrame({
            "overall_visibility":     1.0,
            "wolf_eye_intensity":     0.55,   # settled glow
            "mist_density":           0.25,   # ambient
            "through_glow_intensity": 0.30,
            "warmth_bloom":           warm,
        }).clamped()

    if s == PresenceState.LISTENING:
        return AbstractFrame({
            "overall_visibility":     1.0,
            "wolf_eye_intensity":     0.70,   # noticeable focus
            "mist_density":           0.30,
            "through_glow_intensity": 0.50,
            "warmth_bloom":           warm,
        }).clamped()

    if s == PresenceState.THINKING:
        return AbstractFrame({
            "overall_visibility":     1.0,
            "wolf_eye_intensity":     0.85,   # bible §9: energy gathers
            "mist_density":           0.40,   # slight thickening
            "through_glow_intensity": 0.70,
            "warmth_bloom":           warm * 0.5,
        }).clamped()

    if s == PresenceState.SPEAKING:
        # Bible §9: gentle breathing + subtle life. Through-glow rises with
        # the voice's own intensity (mapped from voice event intensity).
        return AbstractFrame({
            "overall_visibility":     1.0,
            "wolf_eye_intensity":     0.65,
            "mist_density":           0.30,
            "through_glow_intensity": 0.30 + 0.30 * i,   # 0.30..0.60 by voice intensity
            "warmth_bloom":           warm,
        }).clamped()

    if s == PresenceState.ALERT:
        # Bible §9: stillness. Full glow. No mist increase — stillness IS the alert.
        return AbstractFrame({
            "overall_visibility":     1.0,
            "wolf_eye_intensity":     1.0,
            "mist_density":           0.25,
            "through_glow_intensity": 0.90,
            "warmth_bloom":           0.0,
        }).clamped()

    if s == PresenceState.CELEBRATING:
        return AbstractFrame({
            "overall_visibility":     1.0,
            "wolf_eye_intensity":     0.70,
            "mist_density":           0.35,
            "through_glow_intensity": 0.55,
            "warmth_bloom":           0.7,    # rare — the warm rim shows
        }).clamped()

    if s == PresenceState.CONCERNED:
        return AbstractFrame({
            "overall_visibility":     1.0,
            "wolf_eye_intensity":     0.40,   # dimmed per bible §9
            "mist_density":           0.20,   # mist intensity drops
            "through_glow_intensity": 0.35,
            "warmth_bloom":           0.0,
        }).clamped()

    if s == PresenceState.DISSOLVING:
        # Bible §11.2: wolf eyes dim last. Others fade with intensity;
        # wolf-eye follows i * 1.2 - 0.1 so it stays lit while intensity drops.
        return AbstractFrame({
            "overall_visibility":     i,
            "wolf_eye_intensity":     max(0.0, i * 1.2 - 0.1),
            "mist_density":           i * 0.8,
            "through_glow_intensity": max(0.0, (i - 0.3)) * 1.5,
            "warmth_bloom":           0.0,
        }).clamped()

    # Unknown state — degrade to IDLE per PresenceRuntime contract (types.py)
    return intent_to_abstract(PresenceIntent(
        state=PresenceState.IDLE,
        emotion=e,
        intensity=i,
        voice_profile=intent.voice_profile,
    ))


# ---------------------------------------------------------------------------
# Layer 2 → Layer 3 : abstract parameters → Cubism-specific parameter IDs.
# THIS is the ONLY place Cubism parameter names appear anywhere in Nero.
#
# Naming convention for the rig: `ParamNero<Feature>`. The artist rigging
# `manbeardog__L1__v1` should create these exact parameters, or override
# this dict via CUBISM_PARAM_MAP_OVERRIDE from the runtime settings.
# ---------------------------------------------------------------------------

CUBISM_PARAM_MAP: dict[str, str] = {
    "overall_visibility":     "ParamNeroVisibility",
    "wolf_eye_intensity":     "ParamNeroWolfEyeGlow",
    "mist_density":           "ParamNeroMist",
    "through_glow_intensity": "ParamNeroThroughGlow",
    "warmth_bloom":           "ParamNeroWarmthBloom",
}


def abstract_to_cubism(
    frame: AbstractFrame,
    override_map: dict[str, str] | None = None,
) -> dict[str, float]:
    """Translate an AbstractFrame into a dict of Cubism parameter values.

    ``override_map`` lets the runtime's config change parameter names without
    editing this module — useful if the rig ships with different parameter
    names than the convention above.
    """
    param_map = {**CUBISM_PARAM_MAP, **(override_map or {})}
    out: dict[str, float] = {}
    for abstract_name, value in frame.values.items():
        cubism_name = param_map.get(abstract_name)
        if cubism_name:
            out[cubism_name] = float(value)
    return out


# ---------------------------------------------------------------------------
# Convenience: full pipeline in one call.
# ---------------------------------------------------------------------------

def intent_to_cubism(
    intent: PresenceIntent,
    override_map: dict[str, str] | None = None,
) -> dict[str, float]:
    """Convenience: semantic PresenceIntent → Cubism parameter dict.

    Equivalent to ``abstract_to_cubism(intent_to_abstract(intent), map)``.
    Kept as a separate function so callers can inspect the abstract layer
    (for tests, logs, or telemetry) without recomputing it.
    """
    return abstract_to_cubism(intent_to_abstract(intent), override_map)
