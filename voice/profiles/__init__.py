"""voice.profiles — the declarative voice cast (identity as data).

`cast.json` holds *what a voice is*; `loader.py` holds *how to load one*. Behavior
lives in Stages 2 (Voice Capability Graph) and 4 (Voice Manager) — unchanged.
"""
from .loader import (
    DEFAULT_CAST_PATH, Cast, CastError, VoiceProfile, load_cast,
)

__all__ = ["Cast", "CastError", "VoiceProfile", "load_cast", "DEFAULT_CAST_PATH"]
