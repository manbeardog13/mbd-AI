"""Local TTS engines, their shared contract, and the voice capability graph.

Model-independent foundation: the engine contract (`base`) and the runtime
"can THIS voice perform right now?" directory (`voice_capability_graph`).
Concrete engine bodies (kokoro, mms_hr, xtts) arrive in later stages and depend
on nothing but this interface.
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
from .voice_capability_graph import (
    QualityLevel,
    ResolvedVoice,
    VoiceCapability,
    VoiceCapabilityGraph,
)
from .engine_health import (
    EngineHealthCache,
    EngineHealthRecord,
    HealthStatus,
)

__all__ = [
    "AudioResult", "BaseTTSEngine", "EngineHealth", "EngineStatus",
    "NullEngine", "TTSEngine", "VoiceRequest",
    "QualityLevel", "ResolvedVoice", "VoiceCapability", "VoiceCapabilityGraph",
    "EngineHealthCache", "EngineHealthRecord", "HealthStatus",
]
