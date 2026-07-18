"""NullRuntime — accepts every intent, does nothing.

For headless mode, integration tests, and any code path where the Director
must exist but visible presence is not wanted (e.g., during automated testing
of the brain / voice pipeline).
"""
from __future__ import annotations

from ..types import PresenceIntent, PresenceLevel
from .base import PresenceRuntime


class NullRuntime(PresenceRuntime):
    """The no-op runtime. Silent, invisible, always healthy."""

    def __init__(self) -> None:
        self._running = False

    @property
    def name(self) -> str:
        return "null"

    @property
    def max_presence_level(self) -> PresenceLevel:
        return PresenceLevel.L0_VOICE_ONLY

    @property
    def supported_capabilities(self) -> set[str]:
        return set()

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def set_intent(self, intent: PresenceIntent) -> None:
        # By design, does nothing. NullRuntime absorbs every intent silently.
        return None
