"""Semantic types the brain uses to communicate with the Presence Director.

These are stable across renderers. Adding a new renderer must not require
changing these types; extending them (new emotion, new state) is allowed
only additively so existing runtimes keep working.

The types deliberately carry NO animation-specific detail. There is no
``play_animation`` here. The brain says *"speaking, warm, intensity 0.6"*
and the runtime decides what animations, particles, lighting, and timing
express that.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class PresenceLevel(IntEnum):
    """Capability tiers. Higher = more manifestation surface.

    The Director understands the active level and gracefully enables or
    disables capabilities without changing the brain interface. A runtime
    declares its ``max_presence_level``; the Director caps requests at
    that ceiling.
    """

    L0_VOICE_ONLY               = 0   # no visual manifestation at all
    L1_MINIMAL_MANIFESTATION    = 1   # eyes, particles, ambient glow, state indicator
    L2_ANIMATED_PORTRAIT        = 2   # shoulders-up + breathing + eye movement + idle expression
    L3_HALF_BODY_COMPANION      = 3   # arms, posture, additional idle behavior
    L4_FULL_BODY_COMPANION      = 4   # complete body, procedural movement, environmental interaction
    L5_IMMERSIVE                = 5   # VR / AR / mixed reality


LEVEL_CAPABILITIES: dict[PresenceLevel, set[str]] = {
    PresenceLevel.L0_VOICE_ONLY: set(),
    PresenceLevel.L1_MINIMAL_MANIFESTATION: {
        "eyes",
        "particles",
        "ambient_glow",
        "state_indicator",
        "emergence_sequence",
    },
    PresenceLevel.L2_ANIMATED_PORTRAIT: {
        # inherits L1
        "eyes", "particles", "ambient_glow", "state_indicator", "emergence_sequence",
        "portrait",
        "breathing",
        "eye_movement",
        "idle_expression",
        "gaze_direction",
    },
    PresenceLevel.L3_HALF_BODY_COMPANION: {
        # inherits L2
        "eyes", "particles", "ambient_glow", "state_indicator", "emergence_sequence",
        "portrait", "breathing", "eye_movement", "idle_expression", "gaze_direction",
        "arms",
        "posture",
        "hand_gestures",
        "shoulder_movement",
    },
    PresenceLevel.L4_FULL_BODY_COMPANION: {
        # inherits L3
        "eyes", "particles", "ambient_glow", "state_indicator", "emergence_sequence",
        "portrait", "breathing", "eye_movement", "idle_expression", "gaze_direction",
        "arms", "posture", "hand_gestures", "shoulder_movement",
        "full_body",
        "procedural_movement",
        "environmental_interaction",
        "dynamic_lighting",
    },
    PresenceLevel.L5_IMMERSIVE: {
        # inherits L4
        "eyes", "particles", "ambient_glow", "state_indicator", "emergence_sequence",
        "portrait", "breathing", "eye_movement", "idle_expression", "gaze_direction",
        "arms", "posture", "hand_gestures", "shoulder_movement",
        "full_body", "procedural_movement", "environmental_interaction", "dynamic_lighting",
        "spatial_audio",
        "room_scale_positioning",
        "user_gaze_tracking",
        "world_anchoring",
    },
}


class PresenceState(str, Enum):
    """The high-level state the brain wants Nero to be in.

    Adding a new state is backward-compatible as long as runtimes fall back
    to a sensible default (typically IDLE) when they don't recognize it.
    """

    ABSENT       = "absent"        # not visible; runtime should show nothing
    EMERGING     = "emerging"      # manifestation sequence in progress (mist → eyes → silhouette → materialize)
    IDLE         = "idle"          # visible, at rest, subtle breathing
    LISTENING    = "listening"     # attention shifted to user input
    THINKING     = "thinking"      # processing / reasoning
    SPEAKING     = "speaking"      # voice output in progress
    ALERT        = "alert"         # important information, still and focused
    CELEBRATING  = "celebrating"   # positive outcome
    CONCERNED    = "concerned"     # negative outcome / caution
    DISSOLVING   = "dissolving"    # reverse of emerging — voice done, particles dispersing, eyes last


class EmotionState(str, Enum):
    """Emotional coloring layered on top of the state.

    Runtimes interpret the (state, emotion) pair; unknown emotions fall back
    to NEUTRAL. Keep this small and finite — anything more granular becomes
    a taste-driven mess.
    """

    NEUTRAL     = "neutral"
    FOCUSED     = "focused"
    WARM        = "warm"
    AMUSED      = "amused"        # Manbeardog's quiet humor
    PROTECTIVE  = "protective"
    CONCERNED   = "concerned"


@dataclass(frozen=True)
class PresenceIntent:
    """Semantic intent — the ONLY thing the brain sends to the Presence Director.

    Never contains animation IDs, asset paths, or renderer parameters. The
    Director + runtime are responsible for interpreting this into whatever
    visible motion supports the intent.

    Fields
    ------
    state : PresenceState
        The high-level state to be in.
    emotion : EmotionState
        Coloring on top of the state. Defaults to NEUTRAL.
    intensity : float
        0.0..1.0 — how strongly to express state + emotion. 0.0 = barely
        perceptible, 1.0 = as expressive as the runtime supports.
    voice_profile : str
        Which voice is speaking (for runtime coordination — e.g. a whisper
        profile might trigger a closer-mic visual). Purely a hint.
    metadata : dict
        Escape hatch for renderer-specific hints. Runtimes MUST tolerate
        unknown keys (ignore them). Do not put required behavior here.
    """

    state: PresenceState
    emotion: EmotionState = EmotionState.NEUTRAL
    intensity: float = 0.5
    voice_profile: str = "nero_prime"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Clamp intensity to [0.0, 1.0] without raising — resilient to caller drift
        if not 0.0 <= self.intensity <= 1.0:
            object.__setattr__(self, "intensity", max(0.0, min(1.0, self.intensity)))
