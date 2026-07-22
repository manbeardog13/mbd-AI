"""voice.manager.telemetry — Voice Telemetry (observe + aggregate, never decide).

*The Event Bus reports facts. Voice Telemetry summarizes facts. The Action Journal
records executive history.* Three separate concerns — this module is the middle
one, and only that.

Voice Telemetry is a **bus subscriber**. It receives immutable `VoiceEvent` facts
(Stage 7), aggregates them into small in-memory counters, and exposes an immutable
`VoiceTelemetrySnapshot` for dashboards / debugging. It is an **observer**: facts
flow in, summaries flow out, and nothing flows back into routing.

**MAY:** count events · keep rolling statistics · summarize latency · track failure
/ fallback / engine / voice / text-only frequency · expose immutable snapshots.
**MAY NOT:** make routing decisions · mutate health state · trigger fallbacks ·
select voices · change a DeliveryPlan · write memory · learn personality behavior ·
persist anything · become an Action Journal · import any executive/application
system.

Updates are **synchronous and in-process** — `handle()` runs on the same thread as
the emit (inside the Voice Manager's telemetry fan-out), so it does only O(1)
counter work; snapshotting (which copies maps) happens on demand, off the hot path.
No async, no queue, no background worker, no broker — NERO is a single-owner local
AI and needs none of that.

**Dependency direction:** this module imports only the event *vocabulary*
(`VoiceEvent`, `VoiceEventType`) — the fact contract it consumes. It imports
nothing about the Voice Manager, the Capability Graph, the Engine Health cache, or
the Performance Director. It is one subscriber among many; the bus knows nothing
about it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

from .events import VoiceEvent, VoiceEventType

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VoiceTelemetrySnapshot:
    """An immutable, point-in-time summary. The two map fields are read-only
    (`MappingProxyType`) copies, so a snapshot is fully detached from the live
    collector — later events never change an old snapshot."""

    total_events: int = 0
    selected_count: int = 0            # primary_count + fallback_count
    primary_count: int = 0
    fallback_count: int = 0
    engine_failures: int = 0
    cooldown_skips: int = 0
    unavailable_skips: int = 0
    language_skips: int = 0
    text_only_count: int = 0
    per_voice_counts: Mapping = field(default_factory=lambda: MappingProxyType({}))
    per_engine_failures: Mapping = field(default_factory=lambda: MappingProxyType({}))
    average_latency_ms: float = 0.0
    last_event_timestamp: str = ""
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.per_voice_counts, MappingProxyType):
            object.__setattr__(self, "per_voice_counts",
                               MappingProxyType(dict(self.per_voice_counts)))
        if not isinstance(self.per_engine_failures, MappingProxyType):
            object.__setattr__(self, "per_engine_failures",
                               MappingProxyType(dict(self.per_engine_failures)))

    def as_dict(self) -> dict:
        return {
            "total_events": self.total_events,
            "selected_count": self.selected_count,
            "primary_count": self.primary_count,
            "fallback_count": self.fallback_count,
            "engine_failures": self.engine_failures,
            "cooldown_skips": self.cooldown_skips,
            "unavailable_skips": self.unavailable_skips,
            "language_skips": self.language_skips,
            "text_only_count": self.text_only_count,
            "per_voice_counts": dict(self.per_voice_counts),
            "per_engine_failures": dict(self.per_engine_failures),
            "average_latency_ms": self.average_latency_ms,
            "last_event_timestamp": self.last_event_timestamp,
            "schema_version": self.schema_version,
        }


class VoiceTelemetry:
    """A bus subscriber that aggregates voice-lifecycle facts into in-memory
    counters. Small on purpose: `handle` (the subscribe callback), `snapshot`, and
    an `attach` convenience. No persistence, no routing, no health, no learning."""

    def __init__(self) -> None:
        self._total = 0
        self._primary = 0
        self._fallback = 0
        self._engine_failures = 0
        self._cooldown_skips = 0
        self._unavailable_skips = 0
        self._language_skips = 0
        self._text_only = 0
        self._per_voice: dict[str, int] = {}
        self._per_engine_failures: dict[str, int] = {}
        self._latency_sum = 0.0
        self._latency_count = 0
        self._last_ts = ""

    def handle(self, event: VoiceEvent) -> None:
        """Aggregate one event. O(1); reads only the event's read-only payload and
        updates private counters. Observes — never acts."""
        self._total += 1
        if event.timestamp:
            self._last_ts = event.timestamp

        etype = event.type
        payload = event.payload
        if etype == VoiceEventType.VOICE_SELECTED:
            self._primary += 1
            self._count_voice(payload)
            self._add_latency(payload)
        elif etype == VoiceEventType.FALLBACK_USED:
            self._fallback += 1
            self._count_voice(payload)
            self._add_latency(payload)
        elif etype == VoiceEventType.ENGINE_FAILED:
            self._engine_failures += 1
            engine = payload.get("engine")
            if engine:
                self._per_engine_failures[engine] = self._per_engine_failures.get(engine, 0) + 1
        elif etype == VoiceEventType.ENGINE_COOLDOWN:
            self._cooldown_skips += 1
        elif etype == VoiceEventType.VOICE_SKIPPED:
            reason = payload.get("reason")
            if reason == "unavailable":
                self._unavailable_skips += 1
            elif reason == "language":
                self._language_skips += 1
        elif etype == VoiceEventType.TEXT_ONLY_RESULT:
            self._text_only += 1
        # DELIVERY_APPLIED and any unrecognized type count toward total_events only.

    def snapshot(self) -> VoiceTelemetrySnapshot:
        """An immutable summary of everything observed so far."""
        avg = (self._latency_sum / self._latency_count) if self._latency_count else 0.0
        return VoiceTelemetrySnapshot(
            total_events=self._total,
            selected_count=self._primary + self._fallback,
            primary_count=self._primary,
            fallback_count=self._fallback,
            engine_failures=self._engine_failures,
            cooldown_skips=self._cooldown_skips,
            unavailable_skips=self._unavailable_skips,
            language_skips=self._language_skips,
            text_only_count=self._text_only,
            per_voice_counts=MappingProxyType(dict(self._per_voice)),
            per_engine_failures=MappingProxyType(dict(self._per_engine_failures)),
            average_latency_ms=avg,
            last_event_timestamp=self._last_ts,
            schema_version=SCHEMA_VERSION,
        )

    def attach(self, bus) -> Callable[[], None]:
        """Subscribe this collector to a Voice Event Bus and return the bus's
        unsubscribe handle. Duck-typed — any object exposing `subscribe(callback)`
        works, so no bus/manager type is imported and no new coupling is created."""
        return bus.subscribe(self.handle)

    # ---- internal, O(1) helpers ----
    def _count_voice(self, payload: Mapping) -> None:
        voice = payload.get("voice")
        if voice:
            self._per_voice[voice] = self._per_voice.get(voice, 0) + 1

    def _add_latency(self, payload: Mapping) -> None:
        latency = payload.get("latency_ms")
        if isinstance(latency, (int, float)) and not isinstance(latency, bool):
            self._latency_sum += float(latency)
            self._latency_count += 1
