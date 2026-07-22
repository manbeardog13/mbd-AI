"""voice.manager.events — the Voice Event Bus (observational only).

*"Report what happened. Never influence what happens."*

A tiny, synchronous, in-process observation pipe. It **wraps** the Voice Manager's
existing ``telemetry`` callback (Option B) — the routing authority is not modified
and does not know who, if anyone, is listening:

    Voice Manager -> telemetry callback (existing contract) -> VoiceEventBus -> subscribers

Facts flow **out** to observers; nothing flows **back** into routing, health, or
delivery. Events describe what *happened* (``ENGINE_FAILED``), never what *should*
happen (there is no ``TRY_FALLBACK`` — commands disguised as events are forbidden).

**MAY:** notify observers, carry value-copied lifecycle metadata, aid debugging,
enable future dashboards/metrics.
**MAY NOT:** select voices, mark engines healthy/unhealthy, alter a DeliveryPlan,
write memory, trigger tools, call security, dispatch actions — or become a second
brain or a second Action Journal (this bus is ephemeral, executive-blind, and
never persists). It runs synchronously with **no async, no threads, no queues, no
persistence**. It is a small observation pipe, not a framework.

**Dependency direction is one-way:** this module imports nothing about the Voice
Manager, the Capability Graph, the Engine Health cache, the Performance Director,
or any executive system (Action Journal / memory / security / agent). The Manager
depends on a callback; the bus is one implementation of that callback.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping

SCHEMA_VERSION = 1


class VoiceEventType(str, Enum):
    """The minimal, lifecycle-focused vocabulary. Past-tense facts only."""

    VOICE_SELECTED = "voice_selected"       # the preferred voice produced audio
    FALLBACK_USED = "fallback_used"         # a fallback voice produced audio
    ENGINE_FAILED = "engine_failed"         # an engine failed a synthesis attempt
    ENGINE_COOLDOWN = "engine_cooldown"     # a candidate skipped: its engine is cooling down
    VOICE_SKIPPED = "voice_skipped"         # a candidate skipped: unavailable / wrong language
    TEXT_ONLY_RESULT = "text_only_result"   # every candidate exhausted — no audio
    # Defined for a stable schema; NOT emitted in this stage. The future
    # Brain -> Director -> Manager orchestrator is its correct emitter (the
    # Performance Director stays pure and the Voice Manager stays unchanged).
    DELIVERY_APPLIED = "delivery_applied"


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class VoiceEvent:
    """An immutable fact about the voice lifecycle.

    ``payload`` is coerced to a **read-only** mapping of value-copied scalars — it
    never holds references to live Manager / Graph / Health / Engine objects, so a
    subscriber cannot reach runtime state through it. ``timestamp`` and ``sequence``
    are stamped by the bus at emit time (single source of ordering truth)."""

    type: VoiceEventType
    payload: Mapping = field(default_factory=lambda: MappingProxyType({}))
    timestamp: str = ""
    sequence: int = -1
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.payload, MappingProxyType):
            # shallow copy detaches from the source dict; values are scalars
            object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def as_dict(self) -> dict:
        return {
            "type": self.type.value, "payload": dict(self.payload),
            "timestamp": self.timestamp, "sequence": self.sequence,
            "schema_version": self.schema_version,
        }


# ---- mapping from the Manager's existing telemetry dicts to typed events ----
def _map_event(kind: object, telemetry: dict) -> VoiceEventType | None:
    if kind == "selected":
        return (VoiceEventType.FALLBACK_USED
                if telemetry.get("outcome") == "fallback"
                else VoiceEventType.VOICE_SELECTED)
    if kind == "engine_failed":
        return VoiceEventType.ENGINE_FAILED
    if kind == "skip":
        reason = telemetry.get("reason")
        if reason == "cooldown":
            return VoiceEventType.ENGINE_COOLDOWN
        if reason in ("language", "unavailable"):
            return VoiceEventType.VOICE_SKIPPED
        return None                             # unknown skip reason -> ignore
    if kind == "text_only":
        return VoiceEventType.TEXT_ONLY_RESULT
    return None                                 # unknown/unmapped -> ignore, never crash


def from_manager_event(telemetry: object) -> VoiceEvent | None:
    """Translate one Voice Manager telemetry dict into a VoiceEvent, or None if it
    is unknown/unmapped. Never raises — unknown telemetry is safely ignored so voice
    execution is never affected."""
    if not isinstance(telemetry, dict):
        return None
    etype = _map_event(telemetry.get("event"), telemetry)
    if etype is None:
        return None
    payload = {k: v for k, v in telemetry.items() if k != "event"}
    return VoiceEvent(type=etype, payload=payload)


class VoiceEventBus:
    """A synchronous, deterministic, in-process pub/sub. The smallest durable
    surface: ``subscribe`` / ``unsubscribe`` / ``emit`` / ``manager_sink``. No
    persistence, no async, no threads, no queues."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._subscribers: list[Callable[[VoiceEvent], None]] = []
        self._clock = clock or _default_clock
        self._seq = 0

    def subscribe(self, callback: Callable[[VoiceEvent], None]) -> Callable[[], None]:
        """Register an observer (subscription order is preserved). Returns a
        zero-arg handle that detaches this subscriber."""
        self._subscribers.append(callback)
        return lambda: self.unsubscribe(callback)

    def unsubscribe(self, callback: Callable[[VoiceEvent], None]) -> None:
        """Remove an observer. Idempotent — removing an absent callback is a no-op."""
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def emit(self, event: VoiceEvent) -> None:
        """Stamp the event with the next sequence + a timestamp and deliver it to
        every subscriber, in subscription order. Each subscriber runs inside its own
        guard: one bad observer cannot affect another — or voice execution. With no
        subscribers this is near-zero overhead (no stamping, no fan-out)."""
        subscribers = tuple(self._subscribers)     # snapshot: (un)subscribe during emit is safe
        if not subscribers:
            return
        stamped = replace(event, sequence=self._seq, timestamp=self._stamp())
        self._seq += 1
        for callback in subscribers:
            try:
                callback(stamped)
            except Exception:  # noqa: BLE001 - observers are isolated; a failure never propagates
                pass

    def manager_sink(self) -> Callable[[dict], None]:
        """Return a ``Callable[[dict], None]`` to pass as the Voice Manager's
        existing ``telemetry=`` argument. It translates telemetry dicts into
        VoiceEvents and emits them — wrapping the existing seam without changing it."""
        def sink(telemetry: dict) -> None:
            if not self._subscribers:
                return                             # near-zero overhead when nobody listens
            event = from_manager_event(telemetry)
            if event is not None:
                self.emit(event)
        return sink

    def _stamp(self) -> str:
        now = self._clock()
        return now if isinstance(now, str) else now.isoformat()
