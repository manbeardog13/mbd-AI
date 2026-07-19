"""PresenceService — adapts the Presence Director to the RuntimeService contract.

Responsibilities:
    - Build the configured PresenceRuntime (LogRuntime / NullRuntime / future Live2D)
    - Instantiate and start the PresenceDirector
    - Bind the Director to voice events so voice → presence coordination is automatic
    - Report structured health for the /api/runtime/health endpoint
    - Clean shutdown (unbind, stop director) on ``stop``

Renderer specifics NEVER leak here. This service knows about "runtime name"
as an opaque string; the mapping name→PresenceRuntime lives in
``build_runtime()`` and only there.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from presence import PresenceDirector, PresenceLevel
from presence.runtime_bridge import Live2DRuntime, LogRuntime, NullRuntime, PresenceRuntime

from ..service import RuntimeService, ServiceHealth

log = logging.getLogger("nero.runtime.presence")


def build_runtime(
    name: str,
    level: PresenceLevel,
    settings: dict[str, Any] | None = None,
) -> PresenceRuntime:
    """Instantiate a PresenceRuntime by opaque name.

    ``settings`` is an opaque dict passed through from the presence config
    (``presence.settings`` block). Each runtime interprets it per its own
    schema — e.g. LogRuntime ignores it; Live2DRuntime reads
    ``websocket_url``, ``reconnect_backoff_s``, etc.

    Adding a new runtime = importing the runtime class + adding a case here.
    Runtime-specific configuration lives INSIDE the runtime, never leaks
    to the app-config layer.
    """
    settings = settings or {}
    n = (name or "").strip().lower()
    if n in ("null", "none", "off"):
        return NullRuntime()
    if n == "log":
        return LogRuntime(level=level)
    if n == "live2d":
        return Live2DRuntime(settings=settings, level=level)
    # Future runtimes:
    #   if n == "godot":  from presence.runtime_bridge.godot import GodotRuntime; ...
    #   if n == "unreal": from presence.runtime_bridge.unreal import UnrealRuntime; ...
    raise ValueError(
        f"unknown presence runtime: {name!r} "
        f"(available: null, log, live2d)"
    )


class PresenceService(RuntimeService):
    """Wraps PresenceDirector as a Nero RuntimeService.

    Construct via ``from_config(cfg)`` to build from the loaded Config
    (respects presence.enabled / runtime / level / debug), or pass a
    prebuilt runtime directly for tests.
    """

    def __init__(
        self,
        *,
        runtime_name: str = "log",
        level: PresenceLevel = PresenceLevel.L0_VOICE_ONLY,
        debug: bool = False,
        bind_voice: bool = True,
        runtime_settings: dict[str, Any] | None = None,
    ) -> None:
        self._runtime_name = runtime_name
        self._requested_level = level
        self._debug = debug
        self._bind_voice = bind_voice
        self._runtime_settings = dict(runtime_settings or {})
        self._runtime: PresenceRuntime | None = None
        self._director: PresenceDirector | None = None
        self._last_event: str | None = None
        self._last_state: str | None = None

    # ---- construction helpers ----

    @classmethod
    def from_config(cls, cfg: Any) -> "PresenceService":
        """Build from a loaded Config, respecting presence.* settings."""
        return cls(
            runtime_name=cfg.presence_runtime,
            level=PresenceLevel(cfg.presence_level),
            debug=cfg.presence_debug,
            bind_voice=True,
            runtime_settings=dict(getattr(cfg, "presence_runtime_settings", {}) or {}),
        )

    # ---- RuntimeService protocol ----

    @property
    def name(self) -> str:
        return "presence"

    async def start(self) -> None:
        if self._director is not None and self._director.is_running():
            return  # idempotent

        # Building the runtime is a sync operation — no need for to_thread.
        self._runtime = build_runtime(
            self._runtime_name,
            self._requested_level,
            self._runtime_settings,
        )
        self._director = PresenceDirector(
            runtime=self._runtime,
            requested_level=self._requested_level,
        )
        # Also sync — start just flips flags in Null/Log runtimes.
        self._director.start()

        if self._bind_voice:
            self._director.bind_to_voice()
            # Wrap the raw voice-event subscription so we can also update
            # health details (last_event) without touching Director internals.
            self._install_health_tap()

        log.info(
            "Presence Director initialized (runtime=%s, level=%s, voice_bound=%s)",
            self._runtime.name,
            self._director.active_level.name,
            self._bind_voice,
        )

    async def stop(self) -> None:
        if self._director is None:
            return
        try:
            # Director.stop() handles unbind + runtime.stop()
            self._director.stop()
        finally:
            self._director = None
            self._runtime = None
        log.info("Presence Director stopped")

    async def health(self) -> ServiceHealth:
        d = self._director
        r = self._runtime

        if d is None or r is None:
            return ServiceHealth(
                name=self.name,
                running=False,
                status="unavailable",
                details={"reason": "director not started"},
            )

        running = d.is_running()
        status: str = "ok" if running else "unavailable"

        details: dict[str, Any] = {
            "runtime": r.name,
            "runtime_max_level": r.max_presence_level.name,
            "active_level": d.active_level.name,
            "current_state": d.current_state.value,
            "voice_bound": self._bind_voice,
            "debug": self._debug,
            "last_voice_event": self._last_event,
            "last_presence_state": self._last_state,
        }
        # Runtimes that expose a health_snapshot() (e.g. Live2DRuntime with
        # connection state) merge their diagnostics under details.runtime_health.
        snap_fn = getattr(r, "health_snapshot", None)
        if callable(snap_fn):
            try:
                details["runtime_health"] = snap_fn()
                # Downgrade to "degraded" if the runtime reports itself
                # disconnected but the director is otherwise running.
                if isinstance(details["runtime_health"], dict) and details["runtime_health"].get("connected") is False:
                    status = "degraded"
            except Exception as exc:  # noqa: BLE001
                details["runtime_health_error"] = str(exc)
        return ServiceHealth(name=self.name, running=running, status=status, details=details)

    # ---- internals ----

    def _install_health_tap(self) -> None:
        """Subscribe a lightweight callback that just records the last event
        for health reporting. Runs alongside the Director's own subscriber."""
        from voice import events as voice_events

        def _tap(event: Any) -> None:
            try:
                self._last_event = event.kind
                # Director will update current state; capture it after director processes
                if self._director is not None:
                    self._last_state = self._director.current_state.value
            except Exception:  # noqa: BLE001
                pass

        voice_events.subscribe(_tap)
        # Store reference so we can unsubscribe on stop — future improvement
        self._health_tap = _tap
