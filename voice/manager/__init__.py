"""Voice orchestration — the Voice Manager and (later) telemetry, events, health,
warm startup. The manager is the single routing authority in the presentation
layer; it composes the other voice components but absorbs none of their duties.
"""
from .voice_manager import (
    OUTCOME_FALLBACK,
    OUTCOME_PRIMARY,
    OUTCOME_TEXT_ONLY,
    VoiceManager,
)

__all__ = [
    "VoiceManager", "OUTCOME_PRIMARY", "OUTCOME_FALLBACK", "OUTCOME_TEXT_ONLY",
]
