"""Voice event pub/sub.

The Voice Director emits events during synthesis so downstream systems
(Presence Director, telemetry, future observers) can react without the
Voice Director knowing what any of them are.

Design:
    - In-process pub/sub, thread-safe under a lock.
    - Callbacks receive a VoiceEvent dataclass.
    - Subscribers register at startup; callbacks that raise are logged
      and skipped so a broken subscriber cannot break voice output.
    - No external process transport in this module — the Presence
      Director's own runtime bridges handle any process-boundary crossing.

This module is imported by voice.director; consumers subscribe from wherever
they run (in the same process today, potentially over IPC later).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

log = logging.getLogger("nero.voice.events")

VoiceEventKind = Literal[
    "voice.started",              # synthesis about to begin
    "voice.speaking",             # audio chunk / partial ready (multiple per utterance possible)
    "voice.finished",             # synthesis completed successfully
    "voice.interrupted",          # synthesis failed or was aborted
    "voice.unsupported_language", # text is in a language the active profile cannot voice
]


@dataclass(frozen=True)
class VoiceEvent:
    """A single event from the voice subsystem."""

    kind: VoiceEventKind
    profile: str
    timestamp_iso: str
    metadata: dict[str, Any] = field(default_factory=dict)


Subscriber = Callable[[VoiceEvent], None]

_lock = threading.RLock()
_subscribers: list[Subscriber] = []


def subscribe(callback: Subscriber) -> None:
    """Register a callback to receive every VoiceEvent. Idempotent."""
    with _lock:
        if callback not in _subscribers:
            _subscribers.append(callback)


def unsubscribe(callback: Subscriber) -> None:
    """Remove a previously-subscribed callback. Silent if not present."""
    with _lock:
        if callback in _subscribers:
            _subscribers.remove(callback)


def subscribers() -> list[Subscriber]:
    """Snapshot of current subscribers (for introspection / testing)."""
    with _lock:
        return list(_subscribers)


def emit(
    kind: VoiceEventKind,
    profile: str,
    **metadata: Any,
) -> None:
    """Broadcast a VoiceEvent to all subscribers.

    Callbacks that raise are logged and skipped — a broken subscriber
    cannot break voice output.
    """
    event = VoiceEvent(
        kind=kind,
        profile=profile,
        timestamp_iso=_now_iso(),
        metadata=metadata,
    )
    with _lock:
        current = list(_subscribers)
    for cb in current:
        try:
            cb(event)
        except Exception as exc:  # noqa: BLE001
            log.warning("voice-event subscriber raised: %s (event=%s)", exc, event.kind)


def _now_iso() -> str:
    # UTC ISO-8601 with 'Z' suffix — safe for cross-process serialization
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
