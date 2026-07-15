"""Voice profiles — logical voice identities for the Voice Director.

The brain requests a profile by name (nero_prime, nero_whisper, nero_late_night,
etc.); the profile bundles everything needed to render that identity:

    - which blend / voice to use
    - Kokoro speed
    - lang
    - optional banshee effects config
    - text preprocessing hints (future)

Profiles decouple *what character speaks* from *how it's implemented*. Adding
new profiles is a data change (edit presets.py), not a code change.

See voice/profiles/README.md for the profile schema and the emotional-state
mapping strategy.
"""
from .profile import VoiceProfile, synthesize_with_profile
from .presets import PRESETS, get_profile

__all__ = ["VoiceProfile", "synthesize_with_profile", "PRESETS", "get_profile"]
