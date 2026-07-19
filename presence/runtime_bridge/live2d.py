"""Live2D runtime — WebSocket bridge to a Cubism viewer.

Design:

    Presence Director  ──sync set_intent──▶  Live2DRuntime  ──async WS send──▶  Viewer
                                                    │
                                                    ├── background thread
                                                    │   with own asyncio loop
                                                    │
                                                    └── reconnect + fault recovery

The Director's ``set_intent`` is synchronous. WebSocket I/O is async. This
runtime bridges them by owning a dedicated background thread with its own
event loop. ``set_intent`` calls enqueue a message; the background task
pops from the queue and sends it. If the connection is down, messages are
dropped after being logged (buffering old intents would produce stale
animation the moment reconnect happens).

**Voice + chat must never block on visual state.** If the viewer is
unreachable, disconnected, or slow, the Director keeps receiving events;
they're logged and dropped, and ``health()`` reports "degraded". Nothing
propagates.

**No placeholder animation.** This runtime speaks the Cubism parameter
protocol against whatever rig is loaded on the viewer side. Until a real
Manbeardog rig exists, the runtime still starts, connects to a mock or
inspector viewer, and honors the protocol. It just has nothing to look at.

Protocol: see ``live2d_protocol.md`` in this directory.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

from ..types import LEVEL_CAPABILITIES, PresenceIntent, PresenceLevel
from .base import PresenceRuntime
from .live2d_parameter_map import (
    CUBISM_PARAM_MAP,
    abstract_to_cubism,
    intent_to_abstract,
)

log = logging.getLogger("nero.presence.live2d")

PROTOCOL_VERSION = 1

# Default connection settings. Overridable via the runtime's `settings` dict
# from the presence config (see app/config.py::presence_runtime_settings).
_DEFAULTS: dict[str, Any] = {
    "websocket_url":          "ws://127.0.0.1:3939/nero",
    "reconnect_backoff_s":    (1.0, 2.0, 5.0, 10.0, 30.0),  # sequence; last value repeats
    "max_reconnect_attempts": 0,          # 0 = forever
    "send_queue_max":         256,        # drop-oldest if we hit this
    "connect_timeout_s":      5.0,
    "ping_interval_s":        20.0,
    "ping_timeout_s":         20.0,
    "param_blend_ms":         100,        # smooth transitions between intent frames
    "cubism_param_overrides": {},         # dict[abstract_name -> cubism_param_name]
}


class Live2DRuntime(PresenceRuntime):
    """PresenceRuntime that speaks to a Live2D Cubism viewer over WebSocket.

    Constructor takes an opaque ``settings`` dict (from the presence config).
    Every setting has a documented default; missing keys use the default.
    """

    def __init__(
        self,
        settings: dict[str, Any] | None = None,
        level: PresenceLevel = PresenceLevel.L1_MINIMAL_MANIFESTATION,
    ) -> None:
        cfg = {**_DEFAULTS, **(settings or {})}
        self._url: str = cfg["websocket_url"]
        self._backoff: tuple[float, ...] = tuple(cfg["reconnect_backoff_s"])
        self._max_attempts: int = int(cfg["max_reconnect_attempts"])
        self._queue_max: int = int(cfg["send_queue_max"])
        self._connect_timeout: float = float(cfg["connect_timeout_s"])
        self._ping_interval: float = float(cfg["ping_interval_s"])
        self._ping_timeout: float = float(cfg["ping_timeout_s"])
        self._blend_ms: int = int(cfg["param_blend_ms"])
        self._param_overrides: dict[str, str] = dict(cfg["cubism_param_overrides"])
        self._level: PresenceLevel = level

        # Lifecycle state
        self._running: bool = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._connected: bool = False
        self._last_error: str | None = None
        self._last_sent_at: float | None = None
        self._messages_sent: int = 0
        self._messages_dropped: int = 0
        self._reconnect_count: int = 0
        self._viewer_hello: dict[str, Any] | None = None

    # ---- PresenceRuntime protocol ----

    @property
    def name(self) -> str:
        return "live2d"

    @property
    def max_presence_level(self) -> PresenceLevel:
        return self._level

    @property
    def supported_capabilities(self) -> set[str]:
        return LEVEL_CAPABILITIES[self._level].copy()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._thread_main,
            name="live2d-runtime",
            daemon=True,
        )
        self._thread.start()
        log.info("Live2D runtime started (url=%s, level=%s)", self._url, self._level.name)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        # Signal the background loop to shut down; queue-put a sentinel.
        loop = self._loop
        if loop is not None and not loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._enqueue(None), loop)
        t = self._thread
        if t is not None:
            t.join(timeout=5.0)
        self._thread = None
        self._loop = None
        self._queue = None
        self._connected = False
        log.info("Live2D runtime stopped")

    def is_running(self) -> bool:
        return self._running

    def set_intent(self, intent: PresenceIntent) -> None:
        if not self._running:
            return  # dropped silently — matches a stopped renderer

        # Semantic → abstract → Cubism. Do the translation on the caller's
        # thread (cheap; pure math). Only the wire send is async.
        cubism = abstract_to_cubism(intent_to_abstract(intent), self._param_overrides)
        msg = {
            "v":       PROTOCOL_VERSION,
            "kind":    "params",
            "state":   intent.state.value,
            "emotion": intent.emotion.value,
            "params":  cubism,
            "blend_ms": self._blend_ms,
        }

        loop = self._loop
        if loop is None or loop.is_closed():
            self._messages_dropped += 1
            return

        try:
            fut = asyncio.run_coroutine_threadsafe(self._enqueue(msg), loop)
            # Don't wait for the send — we return immediately; Director's
            # set_intent must not block on network I/O.
            _ = fut
        except Exception as exc:  # noqa: BLE001 — never propagate to Director
            log.warning("live2d enqueue failed: %s", exc)
            self._messages_dropped += 1

    def health_snapshot(self) -> dict[str, Any]:
        """Diagnostic snapshot used by PresenceService.health(). Sync-safe."""
        return {
            "connected":         self._connected,
            "websocket_url":     self._url,
            "reconnect_count":   self._reconnect_count,
            "messages_sent":     self._messages_sent,
            "messages_dropped":  self._messages_dropped,
            "last_sent_at":      self._last_sent_at,
            "last_error":        self._last_error,
            "viewer_hello":      self._viewer_hello,
        }

    # ---- background thread + async loop ----

    def _thread_main(self) -> None:
        """Owns the runtime's event loop. Runs until _running is False."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._queue = asyncio.Queue(maxsize=self._queue_max)

        try:
            loop.run_until_complete(self._async_main())
        except Exception as exc:  # noqa: BLE001 — thread must exit cleanly
            log.error("live2d background thread crashed: %s", exc, exc_info=True)
            self._last_error = f"thread crash: {exc}"
        finally:
            try:
                loop.close()
            except Exception:  # noqa: BLE001
                pass

    async def _async_main(self) -> None:
        """Connect / reconnect loop. Owns the sender co-task per connection."""
        attempts_left = self._max_attempts if self._max_attempts > 0 else -1

        while self._running:
            try:
                await self._one_connection()
                # Clean disconnect (viewer went away): try to reconnect
                if not self._running:
                    return
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001
                self._connected = False
                self._last_error = str(exc)
                log.warning("live2d connection failed: %s", exc)

            if not self._running:
                return
            if attempts_left == 0:
                log.warning("live2d: max_reconnect_attempts exhausted, giving up")
                return
            if attempts_left > 0:
                attempts_left -= 1

            delay = self._backoff_delay()
            log.info("live2d: reconnecting in %.1fs", delay)
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return
            self._reconnect_count += 1

    async def _one_connection(self) -> None:
        """One full connect → serve → clean shutdown cycle."""
        # Lazy import so the presence package is importable without websockets.
        import websockets

        async with websockets.connect(
            self._url,
            open_timeout=self._connect_timeout,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
            max_size=1_000_000,
        ) as ws:
            self._connected = True
            self._last_error = None
            log.info("live2d: connected to %s", self._url)

            # Say hello. Viewer should reply with its own hello + capabilities.
            hello = {
                "v":                PROTOCOL_VERSION,
                "kind":             "hello",
                "director":         "nero.presence",
                "expected_params":  list(CUBISM_PARAM_MAP.values()),
                "blend_ms_default": self._blend_ms,
            }
            await ws.send(json.dumps(hello))

            recv_task = asyncio.create_task(self._recv_loop(ws))
            send_task = asyncio.create_task(self._send_loop(ws))

            done, pending = await asyncio.wait(
                {recv_task, send_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

            # If any task raised, surface it now.
            for t in done:
                if t.exception():
                    self._last_error = str(t.exception())

    async def _send_loop(self, ws) -> None:
        """Drain the queue, sending each JSON message over the socket."""
        assert self._queue is not None
        while True:
            msg = await self._queue.get()
            if msg is None:
                return  # sentinel — stop() was called
            try:
                await ws.send(json.dumps(msg))
                self._messages_sent += 1
                self._last_sent_at = time.time()
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"send failed: {exc}"
                log.warning("live2d send failed: %s", exc)
                return  # drop the connection; outer loop reconnects

    async def _recv_loop(self, ws) -> None:
        """Consume viewer messages. Currently we just observe hello + acks."""
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:  # noqa: BLE001
                    log.debug("live2d: viewer sent non-JSON: %r", raw[:120])
                    continue

                kind = msg.get("kind")
                if kind == "hello":
                    self._viewer_hello = msg
                    log.info(
                        "live2d: viewer hello — model=%s, params_available=%d",
                        msg.get("model"),
                        len(msg.get("params_available") or []),
                    )
                elif kind == "error":
                    log.warning("live2d: viewer reported error: %s", msg.get("detail"))
                    self._last_error = f"viewer: {msg.get('detail')}"
                # Other kinds ("ack", "status") logged at debug only
                else:
                    log.debug("live2d: viewer sent %s: %s", kind, msg)
        except Exception as exc:  # noqa: BLE001
            log.debug("live2d recv loop ended: %s", exc)

    async def _enqueue(self, msg: dict[str, Any] | None) -> None:
        """Put a message on the send queue. Drop oldest if full."""
        assert self._queue is not None
        if self._queue.full():
            # Discard one old message so the newest wins — stale intent is
            # worse than dropped intent for animation.
            try:
                _ = self._queue.get_nowait()
                self._messages_dropped += 1
            except asyncio.QueueEmpty:
                pass
        await self._queue.put(msg)

    def _backoff_delay(self) -> float:
        """Backoff schedule — walks through the tuple, last value repeats."""
        if not self._backoff:
            return 3.0
        idx = min(self._reconnect_count, len(self._backoff) - 1)
        return float(self._backoff[idx])
