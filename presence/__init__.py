"""Nero Presence Director — the visual counterpart to the Voice Director.

The Presence Director abstracts visual rendering behind a stable, semantic
interface. The brain communicates *intent* (state + emotion + intensity);
the Director + its active runtime translate that intent into whatever the
current renderer supports.

The renderer is pluggable. See ``presence/runtime_bridge/`` — Null and Log
runtimes ship in-package; Live2D / Godot / Unreal runtimes are separate
runtime implementations that plug into the same abstract interface.

The brain never knows which renderer is active. Presence Levels 0–5 declare
capability tiers; the Director gracefully degrades if the active runtime
can't reach the requested level.
"""
from .director import PresenceDirector
from .types import (
    EmotionState,
    PresenceIntent,
    PresenceLevel,
    PresenceState,
)

__all__ = [
    "PresenceDirector",
    "PresenceIntent",
    "PresenceState",
    "EmotionState",
    "PresenceLevel",
]
