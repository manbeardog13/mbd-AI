"""Runtime bridges — the pluggable rendering layer for the Presence Director.

Every runtime implements ``PresenceRuntime`` (see ``base.py``). The Director
holds a reference to exactly one runtime at a time and forwards semantic
``PresenceIntent`` objects to it. The runtime is responsible for translating
intent into visible motion (or a no-op).

Shipped in-package:
    - NullRuntime  — accepts intents, does nothing. Tests + headless mode.
    - LogRuntime   — logs every intent + event. Verifies the pipeline without
                     needing a renderer.

Not shipped in this package (separate implementations, each in its own
process):
    - Live2DRuntime  — WebSocket bridge to a Cubism viewer.
    - GodotRuntime   — subprocess + JSON commands.
    - UnrealRuntime  — Remote Control API bridge.
"""
from .base import PresenceRuntime
from .familiar import FamiliarRuntime
from .live2d import Live2DRuntime
from .log import LogRuntime
from .null import NullRuntime

__all__ = ["PresenceRuntime", "NullRuntime", "LogRuntime", "Live2DRuntime",
           "FamiliarRuntime"]
