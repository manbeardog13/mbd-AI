"""The abstract PresenceRuntime interface.

Every renderer (Live2D, Godot, Unreal, Null, Log, future) implements this.
The Director never talks to a specific renderer — only to a PresenceRuntime.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import PresenceIntent, PresenceLevel


class PresenceRuntime(ABC):
    """Contract for a rendering runtime that consumes PresenceIntent.

    Implementations MUST be resilient — a runtime that raises during
    ``set_intent`` should be caught by the Director so voice + chat are
    never affected by visual failures.

    Implementations MAY run in-process (Null, Log) or out-of-process
    (Live2D via WebSocket, Godot via subprocess, Unreal via Remote Control).
    That distinction is entirely encapsulated in the runtime; the Director
    does not know or care.
    """

    # ---- capability declarations (called by Director on construction) ----

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for this runtime, e.g. 'null', 'log', 'live2d'."""

    @property
    @abstractmethod
    def max_presence_level(self) -> PresenceLevel:
        """The highest PresenceLevel this runtime can honor.

        The Director will cap any requested level at this ceiling.
        """

    @property
    @abstractmethod
    def supported_capabilities(self) -> set[str]:
        """Capability strings this runtime can actually render.

        Should be a subset (or equal to) LEVEL_CAPABILITIES[max_presence_level].
        Lets the Director degrade gracefully — if a capability isn't
        supported, the intent that would exercise it is downgraded or dropped.
        """

    # ---- lifecycle ----

    @abstractmethod
    def start(self) -> None:
        """Boot the runtime. Connect subprocess, open WebSocket, load rig, etc.

        Must be idempotent — calling start() on an already-running runtime
        is a no-op, not an error.
        """

    @abstractmethod
    def stop(self) -> None:
        """Shut down the runtime cleanly. Must be idempotent."""

    @abstractmethod
    def is_running(self) -> bool:
        """Return True iff the runtime is currently active and accepting intents."""

    # ---- the actual work ----

    @abstractmethod
    def set_intent(self, intent: PresenceIntent) -> None:
        """Receive a semantic intent from the Director.

        The runtime interprets state + emotion + intensity into whatever
        visible motion it can produce. Should NEVER raise for unknown
        state/emotion enum values — degrade to a sensible default
        (typically IDLE + NEUTRAL) and continue.
        """
