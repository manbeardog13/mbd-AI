"""The RuntimeService contract + ServiceHealth dataclass.

Every Nero subsystem that owns lifecycle state (Presence Director today,
future Memory Manager / Scheduler / Vision / Automation Engine) implements
``RuntimeService``. The ``LifecycleManager`` drives them uniformly.

Kept deliberately minimal — this is a pattern, not a framework.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

HealthStatus = Literal["ok", "degraded", "unavailable"]


@dataclass(frozen=True)
class ServiceHealth:
    """A snapshot of one service's health.

    Fields
    ------
    name : str
        The service's stable identifier (e.g. "presence").
    running : bool
        Is the service currently active? Never guess — reflect actual state.
    status : "ok" | "degraded" | "unavailable"
        Coarse assessment. ``ok`` = fully working. ``degraded`` = running but
        with limits (e.g. runtime disconnected but Director alive). ``unavailable``
        = not running at all or broken.
    details : dict
        Service-specific structured info — active runtime, last event, timings,
        etc. Consumers must tolerate missing / unknown keys.
    """

    name: str
    running: bool
    status: HealthStatus
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "running": self.running,
            "status": self.status,
            "details": dict(self.details),
        }


class RuntimeService(ABC):
    """Contract for any long-lived Nero subsystem.

    Async by convention — matches FastAPI's lifespan model. Services whose
    internals are synchronous should still expose async methods (with sync
    bodies wrapped in ``asyncio.to_thread`` when they might block).

    Rules for implementations:

    1. ``start`` and ``stop`` MUST be idempotent. Calling ``start`` on an
       already-running service is a no-op, not an error.
    2. ``stop`` MUST NOT raise for any reason a manager cares about — a
       broken stop is logged; other services still shut down.
    3. Failures inside a service MUST NOT propagate to the manager. Report
       them via ``health()`` (status="unavailable" or "degraded") instead.
    4. Services MUST NOT hold references to each other directly. Coordinate
       via events (see voice.events) or via explicit dependency injection at
       construction time.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier used in logs, health reports, and the manager."""

    @abstractmethod
    async def start(self) -> None:
        """Bring the service online. Idempotent."""

    @abstractmethod
    async def stop(self) -> None:
        """Shut the service down cleanly. Idempotent. Must not raise."""

    @abstractmethod
    async def health(self) -> ServiceHealth:
        """Report current health. Called on demand by the health endpoint."""
