"""voice.rendering — Rendering: *how* speech should sound (engine-independent).

The middle of the four separate concepts: Identity (cast) says *who*; **Rendering**
(this package) says *how it should sound*; Capability (the graph) says *what is
possible*; the Engine says *how the native waveform is made*. Rendering is never
merged with any of them, and it never contains engine-specific detail.
"""
from .casting import VoiceCasting
from .profile import (
    DEFAULT_PROFILES_PATH, RenderingError, RenderingProfile, RenderingProfiles,
)

__all__ = [
    "RenderingProfile", "RenderingProfiles", "RenderingError",
    "DEFAULT_PROFILES_PATH", "VoiceCasting",
]
