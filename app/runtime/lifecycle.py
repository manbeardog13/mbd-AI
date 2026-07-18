"""LifecycleManager — owns the service list and drives startup/shutdown in order.

Startup: services start in registration order.
Shutdown: services stop in REVERSE registration order.

The manager isolates failures. If a service raises during start, it's logged
and marked unhealthy — other services continue. If a service raises during
stop, same treatment. The HTTP stack must never fail because a subsystem
failed.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from .service import RuntimeService, ServiceHealth

log = logging.getLogger("nero.runtime.lifecycle")


class LifecycleManager:
    """Ordered registry of RuntimeServices with uniform start/stop/health."""

    def __init__(self) -> None:
        self._services: list[RuntimeService] = []
        self._started: set[str] = set()

    # ---- registration ----

    def register(self, service: RuntimeService) -> None:
        """Register a service. Order matters — startup follows registration order."""
        if any(s.name == service.name for s in self._services):
            raise ValueError(f"service already registered: {service.name!r}")
        self._services.append(service)
        log.info("registered service: %s", service.name)

    def services(self) -> Iterable[RuntimeService]:
        return tuple(self._services)

    def get(self, name: str) -> RuntimeService | None:
        for s in self._services:
            if s.name == name:
                return s
        return None

    # ---- lifecycle ----

    async def start_all(self) -> None:
        """Start every registered service in registration order.

        A service that fails to start is logged; the manager continues with
        the remaining services. Failed services will report unhealthy via
        ``health_all``.
        """
        log.info("starting %d service(s): %s", len(self._services),
                 ", ".join(s.name for s in self._services))
        for svc in self._services:
            try:
                await svc.start()
                self._started.add(svc.name)
                log.info("service started: %s", svc.name)
            except Exception as exc:  # noqa: BLE001 — isolate failures
                log.error("service %s failed to start: %s", svc.name, exc, exc_info=True)

    async def stop_all(self) -> None:
        """Stop every started service in REVERSE registration order.

        Stop errors are logged and swallowed — shutdown must complete regardless.
        """
        for svc in reversed(self._services):
            if svc.name not in self._started:
                continue
            try:
                await svc.stop()
                log.info("service stopped: %s", svc.name)
            except Exception as exc:  # noqa: BLE001
                log.warning("service %s raised on stop (ignoring): %s", svc.name, exc)
        self._started.clear()

    # ---- health ----

    async def health_all(self) -> list[ServiceHealth]:
        """Collect health snapshots from every registered service.

        A service whose ``health`` call raises is reported as unavailable
        rather than propagating the exception.
        """
        snapshots: list[ServiceHealth] = []
        for svc in self._services:
            try:
                snap = await svc.health()
            except Exception as exc:  # noqa: BLE001
                snap = ServiceHealth(
                    name=svc.name,
                    running=False,
                    status="unavailable",
                    details={"error": f"health() raised: {exc!r}"},
                )
            snapshots.append(snap)
        return snapshots
