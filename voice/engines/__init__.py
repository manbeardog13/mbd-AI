"""voice.engines — concrete TTS engine bodies (the "voice creatures").

Engine *bodies* live here, separate from engine *orchestration* (`voice/manager/`)
and from the sealed *contract* (`voice/local_tts/base.py`). Each body implements the
`BaseTTSEngine` contract and turns text into real audio; it never routes, never
chooses a voice, never decides fallback or health — those live above it, sealed.
"""
from .kokoro import (
    FakeKokoroBackend, KokoroBackend, KokoroEngine, RealKokoroBackend,
)

__all__ = ["KokoroEngine", "KokoroBackend", "FakeKokoroBackend", "RealKokoroBackend"]
