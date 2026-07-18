"""Declarative cast profiles and logical Voice Director presets."""

from .loader import (
    DEFAULT_CAST_PATH,
    Cast,
    CastError,
    VoiceProfile as CastVoiceProfile,
    load_cast,
)
from .profile import VoiceProfile, synthesize_with_profile
from .presets import PRESETS, get_profile

__all__ = [
    "Cast",
    "CastError",
    "CastVoiceProfile",
    "DEFAULT_CAST_PATH",
    "PRESETS",
    "VoiceProfile",
    "get_profile",
    "load_cast",
    "synthesize_with_profile",
]
