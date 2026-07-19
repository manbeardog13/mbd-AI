"""voice.manager.startup — Warm Startup / Voice Runtime Initialization.

The **composition root** of the Voice Platform: it wires the sealed components from
Stages 1–8 together in a deterministic order and *reports* whether they are ready.
It is a **composer, not a commander** — the workshop table where the machine is
assembled, never the mechanic deciding which gear should turn.

    build_voice_runtime(engines, …)
      ├── load_cast(cast_path)                 → Cast            (Stage 5)
      ├── VoiceCapabilityGraph()               → graph           (Stage 2)
      ├── cast.populate(graph, engines)        → bind + validate (Stage 5)
      ├── EngineHealthCache(…)                 → health          (Stage 3)
      ├── VoiceEventBus(clock)                 → bus             (Stage 7)
      ├── VoiceTelemetry().attach(bus)         → telemetry       (Stage 8)
      └── VoiceManager(graph, health, …,
                       telemetry=bus.manager_sink())             (Stage 4)

**Owns:** object construction · dependency wiring · composition ordering · readiness
*reporting*.
**Does NOT own:** routing · fallback logic · voice ranking · engine selection · health
*decisions* · retries · recovery · memory · personality · LLM calls · Action Journal.

This is the **one** module allowed to import the Manager, Graph, Health, Bus, and
Telemetry together — its whole job is to construct them. It adds no cycle: startup
depends on the components; nothing depends on startup (one-way).

**Engines are injected, never created here** — the RTX-4070's real engines (and
their GPU warm-up) live behind the `TTSEngine` abstraction. Startup sees a plug, not
the electricity behind the wall, which keeps it model-independent and cloud-testable
(NullEngine / test doubles in the cloud; real engines on the local machine).

**Composition failure vs. operational readiness.** A manifest that won't load, a
missing engine binding, or a language a bound engine cannot produce is a
*configuration* failure → `StartupError`, no partial runtime. Engines merely being
*unavailable* is not a failure — it is reported by `VoiceReadiness`
(READY / DEGRADED / OFFLINE), never raised. Startup reports reality; it does not
negotiate with it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping

from ..local_tts.engine_health import EngineHealthCache
from ..local_tts.voice_capability_graph import VoiceCapabilityGraph
from ..profiles.loader import Cast, CastError, load_cast
from .events import VoiceEventBus
from .telemetry import VoiceTelemetry
from .voice_manager import VoiceManager

SCHEMA_VERSION = 1


class StartupError(Exception):
    """Voice runtime composition failed: the manifest could not be read/parsed, an
    engine binding was missing, or a declared language a bound engine cannot produce.
    Startup builds no partial runtime. This is a configuration/wiring failure — engines
    merely being unavailable at boot is *not* this; that is reported by VoiceReadiness."""


class ReadinessState(str, Enum):
    READY = "ready"        # the emergency voice can perform now — a guaranteed audio path
    DEGRADED = "degraded"  # some voice can perform, but the emergency voice cannot
    OFFLINE = "offline"    # no voice can perform now (the Manager returns text_only)


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(clock: Callable[[], datetime]) -> str:
    now = clock()
    return now if isinstance(now, str) else now.isoformat()


@dataclass(frozen=True)
class VoiceReadiness:
    """An immutable, point-in-time readiness summary — a *report*, not a decision.
    Derived purely by asking the Capability Graph 'can this voice perform now?'; it
    mutates nothing and owns no authority."""

    state: ReadinessState
    cast_loaded: bool
    total_voices: int
    available_voices: tuple[str, ...]
    emergency_voice: str
    emergency_available: bool
    engines: Mapping                    # read-only {engine_name: available_bool}
    checked_at: str
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.engines, MappingProxyType):
            object.__setattr__(self, "engines", MappingProxyType(dict(self.engines)))

    def as_dict(self) -> dict:
        return {
            "state": self.state.value, "cast_loaded": self.cast_loaded,
            "total_voices": self.total_voices,
            "available_voices": list(self.available_voices),
            "emergency_voice": self.emergency_voice,
            "emergency_available": self.emergency_available,
            "engines": dict(self.engines), "checked_at": self.checked_at,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class VoiceRuntime:
    """The composed, wired voice subsystem. A container — it holds the components and
    can re-probe readiness, and deliberately nothing more. Callers speak through
    ``runtime.manager.speak(...)``; the runtime is not a second interface hiding the
    routing authority."""

    manager: VoiceManager
    bus: VoiceEventBus
    telemetry: VoiceTelemetry | None
    graph: VoiceCapabilityGraph
    health: EngineHealthCache
    cast: Cast
    clock: Callable[[], datetime] = field(default=_default_clock, repr=False)

    def readiness(self) -> VoiceReadiness:
        """Re-probe live readiness (availability is live, so this is a method, not a
        stored value). Read-only: asks the Capability Graph, mutates nothing."""
        return _probe_readiness(self.graph, self.cast, self.clock)


def _probe_readiness(
    graph: VoiceCapabilityGraph, cast: Cast, clock: Callable[[], datetime]
) -> VoiceReadiness:
    caps = cast.capabilities()
    available: list[str] = []
    engines: dict[str, bool] = {}
    for cap in caps:
        resolved = graph.resolve(cap.voice_id)
        avail = bool(resolved and resolved.available)      # engine.available() — live
        if avail:
            available.append(cap.voice_id)
        engines[cap.engine] = engines.get(cap.engine, False) or avail

    emergency = cast.emergency_voice
    emergency_available = bool(emergency and graph.can_perform(emergency))
    if emergency_available:
        state = ReadinessState.READY
    elif available:
        state = ReadinessState.DEGRADED
    else:
        state = ReadinessState.OFFLINE

    return VoiceReadiness(
        state=state, cast_loaded=True, total_voices=len(caps),
        available_voices=tuple(available), emergency_voice=emergency,
        emergency_available=emergency_available,
        engines=MappingProxyType(dict(engines)), checked_at=_stamp(clock),
    )


def build_voice_runtime(
    *,
    engines: dict,
    cast_path=None,
    clock: Callable[[], datetime] | None = None,
    base_cooldown_s: float = 5.0,
    max_cooldown_s: float = 300.0,
    enable_telemetry: bool = True,
) -> VoiceRuntime:
    """Compose the voice subsystem from injected engines and a manifest, in a fixed,
    deterministic order, and return a wired :class:`VoiceRuntime`.

    Raises :class:`StartupError` on a composition failure (unreadable/invalid manifest,
    missing engine binding, or an unsupported declared language) — never a partial
    runtime. Operational unavailability (engines simply not up) is reported by
    ``runtime.readiness()``, not raised. Startup constructs; it makes no routing,
    health, or recovery decision, and it creates no engines.
    """
    if not isinstance(engines, dict):
        raise StartupError("engines must be a dict of {engine_name: TTSEngine}")
    clock = clock or _default_clock

    # 1. Cast (structural validation) ----------------------------------------
    try:
        cast = load_cast(cast_path)
    except CastError as exc:
        raise StartupError(f"voice runtime startup failed: {exc}") from None

    # 2. Capability Graph + engine binding / language validation -------------
    graph = VoiceCapabilityGraph()
    try:
        cast.populate(graph, engines)
    except CastError as exc:
        raise StartupError(f"voice runtime startup failed: {exc}") from None

    # 3. Engine Health (constructed only — no record_*; history starts at runtime)
    health = EngineHealthCache(base_cooldown_s=base_cooldown_s, max_cooldown_s=max_cooldown_s)

    # 4. Event Bus + (optional) Telemetry — the bus is always the observation seam
    bus = VoiceEventBus(clock=clock)
    telemetry: VoiceTelemetry | None = None
    if enable_telemetry:
        telemetry = VoiceTelemetry()
        telemetry.attach(bus)

    # 5. Voice Manager (constructed, never modified) — telemetry wired via the seam
    manager = VoiceManager(
        graph, health, emergency_voice=cast.emergency_voice,
        fallback_map=cast.fallback_map, telemetry=bus.manager_sink(),
    )

    return VoiceRuntime(manager=manager, bus=bus, telemetry=telemetry, graph=graph,
                        health=health, cast=cast, clock=clock)
