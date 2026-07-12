"""voice.manager.health — Voice Health Check (a stateless, read-only interpreter).

*Engine Health remembers. Telemetry observes. Startup assembles. The Health Report
**interprets** the current picture — and nobody decides for the Manager.*

This component answers exactly one question: **"What is the current observable health
picture of the voice subsystem?"** It never answers *"what should the system do
next?"* — it is a crystal-clear glass window, not a mysterious oracle.

It composes **three lenses** from three sovereign authorities, on demand, and owns
nothing:

    Availability lens   ← Capability Graph   "can voices currently perform?"
    Attempt-health lens ← Engine Health      "would this engine be allowed an attempt?"
    Execution lens      ← Telemetry snapshot  "what has happened?"
    overall (advisory)  ← a pure rollup       (descriptive only — the Manager never reads it)

**Owns:** interpretation / presentation of a single immutable report.
**Refuses to own:** routing · fallback · voice selection · recovery / restart / reload
· retries · health mutation (never calls ``record_*``) · its own state · persistence ·
learning / scoring / prediction / confidence · Event Bus subscription (Telemetry
already subscribes; this reads its *snapshot*) · any executive coupling.

**Dependency direction:** it reads the Graph, Engine Health, and a Telemetry snapshot
by **duck typing** — it imports **no** voice module (not the Voice Manager, not
Startup, nothing from ``app``). Pull-only and stateless: every call re-reads live
state, mirroring Startup's ``readiness()``. Nothing imports this module (one-way).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping

SCHEMA_VERSION = 1


class VoiceHealthLevel(str, Enum):
    """The advisory rollup. Descriptive only — never consumed by the Voice Manager."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(clock: Callable[[], datetime]) -> str:
    now = clock()
    return now if isinstance(now, str) else now.isoformat()


@dataclass(frozen=True)
class EngineHealthView:
    """The attempt-health of one engine — a read-only view, never a live handle."""

    status: str                 # HealthStatus value: unknown/available/failing/cooldown/recovering
    should_attempt: bool
    consecutive_failures: int


@dataclass(frozen=True)
class RecentExecution:
    """The execution lens — a detached copy of the Telemetry snapshot's key counters."""

    engine_failures: int
    fallback_count: int
    text_only_count: int
    selected_count: int
    average_latency_ms: float
    per_engine_failures: Mapping = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.per_engine_failures, MappingProxyType):
            object.__setattr__(self, "per_engine_failures",
                               MappingProxyType(dict(self.per_engine_failures)))


@dataclass(frozen=True)
class VoiceHealthReport:
    """An immutable, three-lens snapshot of the voice subsystem's health right now.
    A report, not a decision: it presents each lens plus a transparent advisory
    rollup, and mutates nothing."""

    # Availability lens (Capability Graph)
    available_voices: tuple[str, ...]
    total_voices: int
    emergency_available: bool
    # Attempt-health lens (Engine Health)
    engines: Mapping            # {engine_name: EngineHealthView}
    gated_engines: tuple[str, ...]
    # Execution lens (Telemetry)
    recent: RecentExecution | None
    # Advisory rollup (descriptive only)
    overall: VoiceHealthLevel
    checked_at: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.engines, MappingProxyType):
            object.__setattr__(self, "engines", MappingProxyType(dict(self.engines)))

    def as_dict(self) -> dict:
        return {
            "available_voices": list(self.available_voices),
            "total_voices": self.total_voices,
            "emergency_available": self.emergency_available,
            "engines": {name: {"status": v.status, "should_attempt": v.should_attempt,
                               "consecutive_failures": v.consecutive_failures}
                        for name, v in self.engines.items()},
            "gated_engines": list(self.gated_engines),
            "recent": (None if self.recent is None else {
                "engine_failures": self.recent.engine_failures,
                "fallback_count": self.recent.fallback_count,
                "text_only_count": self.recent.text_only_count,
                "selected_count": self.recent.selected_count,
                "average_latency_ms": self.recent.average_latency_ms,
                "per_engine_failures": dict(self.recent.per_engine_failures),
            }),
            "overall": self.overall.value,
            "checked_at": self.checked_at,
            "schema_version": self.schema_version,
        }


def _rollup(
    available_voices: tuple, emergency_available: bool, gated_engines: tuple,
    recent: RecentExecution | None,
) -> VoiceHealthLevel:
    """The advisory rollup — a pure function, exactly as specified. No weighting, no
    scoring, no confidence, no prediction."""
    if len(available_voices) == 0:
        return VoiceHealthLevel.OFFLINE
    degraded = (
        (not emergency_available)
        or bool(gated_engines)
        or (recent is not None and recent.engine_failures > 0)
        or (recent is not None and recent.text_only_count > 0)
    )
    return VoiceHealthLevel.DEGRADED if degraded else VoiceHealthLevel.HEALTHY


def _status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


def build_health_report(
    *,
    graph,
    engine_health,
    emergency_voice: str = "",
    telemetry=None,
    now: datetime | None = None,
    clock: Callable[[], datetime] | None = None,
) -> VoiceHealthReport:
    """Compose an immutable three-lens health report from the live authorities.

    Read-only and stateless: it *asks* the Capability Graph, Engine Health, and a
    Telemetry snapshot; it mutates nothing (never records health outcomes) and
    decides nothing. ``now`` is passed through to Engine Health's cooldown probing;
    ``clock`` stamps ``checked_at`` — both injectable for deterministic tests.
    """
    clock = clock or _default_clock

    # --- Availability lens (Capability Graph) ---
    all_voices = list(graph.voices())
    available = tuple(v for v in all_voices if graph.can_perform(v))
    emergency_available = bool(emergency_voice and graph.can_perform(emergency_voice))

    # --- Attempt-health lens (Engine Health) ---
    engine_names: list[str] = []
    seen: set[str] = set()
    for voice_id in all_voices:
        resolved = graph.resolve(voice_id)
        if resolved is None:
            continue
        name = resolved.capability.engine
        if name not in seen:
            seen.add(name)
            engine_names.append(name)

    engines: dict[str, EngineHealthView] = {}
    gated: list[str] = []
    for name in engine_names:
        should = bool(engine_health.should_attempt(name, now=now))
        record = engine_health.get(name)
        engines[name] = EngineHealthView(
            status=_status_value(engine_health.status(name, now=now)),
            should_attempt=should,
            consecutive_failures=(record.consecutive_failures if record is not None else 0),
        )
        if not should:
            gated.append(name)

    # --- Execution lens (Telemetry snapshot) ---
    recent: RecentExecution | None = None
    if telemetry is not None:
        snap = telemetry.snapshot()
        recent = RecentExecution(
            engine_failures=snap.engine_failures,
            fallback_count=snap.fallback_count,
            text_only_count=snap.text_only_count,
            selected_count=snap.selected_count,
            average_latency_ms=snap.average_latency_ms,
            per_engine_failures=MappingProxyType(dict(snap.per_engine_failures)),
        )

    overall = _rollup(available, emergency_available, tuple(gated), recent)
    return VoiceHealthReport(
        available_voices=available, total_voices=len(all_voices),
        emergency_available=emergency_available,
        engines=MappingProxyType(engines), gated_engines=tuple(gated),
        recent=recent, overall=overall, checked_at=_stamp(clock),
    )


def report_for_runtime(
    runtime, *, now: datetime | None = None, clock: Callable[[], datetime] | None = None,
) -> VoiceHealthReport:
    """Convenience over a composed runtime (Stage 9). Duck-typed — it reads
    ``runtime.graph`` / ``runtime.health`` / ``runtime.telemetry`` /
    ``runtime.cast.emergency_voice`` and imports nothing about Startup, so there is no
    coupling and no cycle."""
    cast = getattr(runtime, "cast", None)
    emergency = getattr(cast, "emergency_voice", "") if cast is not None else ""
    return build_health_report(
        graph=runtime.graph, engine_health=runtime.health,
        emergency_voice=emergency, telemetry=getattr(runtime, "telemetry", None),
        now=now, clock=clock,
    )
