"""LogRuntime — logs every intent as if it were being rendered.

The tool for verifying the brain → voice → presence signal chain without
needing an actual rig or renderer. Every ``set_intent`` prints a compact
line describing what a real renderer would do. Useful during development,
regression tests, and demos of the architecture without visual assets.

Declares support for ALL L1 capabilities so the Director sends the full
emergence sequence through it, letting you eyeball the pipeline in text.
"""
from __future__ import annotations

import logging
import time
from typing import TextIO

from ..types import (
    LEVEL_CAPABILITIES,
    PresenceIntent,
    PresenceLevel,
)
from .base import PresenceRuntime

log = logging.getLogger("nero.presence.log_runtime")


class LogRuntime(PresenceRuntime):
    """A runtime that just prints what a real renderer would do.

    Configurable output stream (defaults to Python logging). Useful for
    integration tests where you want to assert on the intent stream, and
    for interactive debugging where you want to watch the pipeline work.

    Parameters
    ----------
    stream : TextIO | None
        If given, intent lines are written to this stream (e.g. sys.stdout)
        in addition to being logged. If None, only logging is used.
    level : PresenceLevel
        The maximum presence level this runtime claims to support. Defaults
        to L2 (portrait) so most intents flow through unaltered.
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        level: PresenceLevel = PresenceLevel.L2_ANIMATED_PORTRAIT,
    ) -> None:
        self._running = False
        self._stream = stream
        self._level = level
        self._t0: float | None = None

    @property
    def name(self) -> str:
        return "log"

    @property
    def max_presence_level(self) -> PresenceLevel:
        return self._level

    @property
    def supported_capabilities(self) -> set[str]:
        # Declare everything the current level allows; runtime "supports"
        # them in the sense of being able to log about them.
        return LEVEL_CAPABILITIES[self._level].copy()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._t0 = time.perf_counter()
        self._write("[log-runtime] START — presence pipeline is now live")

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._write("[log-runtime] STOP  — presence pipeline shut down")

    def is_running(self) -> bool:
        return self._running

    def set_intent(self, intent: PresenceIntent) -> None:
        if not self._running:
            return  # dropped silently — matches how a stopped renderer would behave
        line = self._format_intent(intent)
        self._write(line)

    # ---- internals ----

    def _format_intent(self, intent: PresenceIntent) -> str:
        elapsed = 0.0 if self._t0 is None else time.perf_counter() - self._t0
        parts = [
            f"[log-runtime t={elapsed:6.2f}s]",
            f"state={intent.state.value:<11}",
            f"emotion={intent.emotion.value:<10}",
            f"intensity={intent.intensity:.2f}",
            f"voice={intent.voice_profile}",
        ]
        if intent.metadata:
            parts.append(f"meta={intent.metadata}")
        return " ".join(parts)

    def _write(self, line: str) -> None:
        log.info(line)
        if self._stream is not None:
            print(line, file=self._stream, flush=True)
