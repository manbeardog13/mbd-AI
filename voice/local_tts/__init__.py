"""Local TTS engines and their shared contract.

Stage 1 exposes only the contract (`base`); concrete engine bodies (kokoro,
mms_hr, xtts) arrive in later stages and depend on nothing but this interface.
"""
from .base import (
    AudioResult,
    BaseTTSEngine,
    EngineHealth,
    EngineStatus,
    NullEngine,
    TTSEngine,
    VoiceRequest,
)

__all__ = [
    "AudioResult", "BaseTTSEngine", "EngineHealth", "EngineStatus",
    "NullEngine", "TTSEngine", "VoiceRequest",
]
