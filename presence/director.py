"""The Presence Director — the ONE place the brain talks to.

Contract with the brain:

    from presence import PresenceDirector, PresenceIntent, PresenceState, EmotionState
    from presence.runtime_bridge import LogRuntime

    director = PresenceDirector(runtime=LogRuntime())
    director.start()
    director.emerge()                                        # nothing → visible
    director.set_intent(PresenceIntent(PresenceState.LISTENING))
    director.set_intent(PresenceIntent(PresenceState.THINKING, EmotionState.FOCUSED, 0.4))
    director.set_intent(PresenceIntent(PresenceState.SPEAKING))
    director.dissolve()                                      # visible → nothing
    director.stop()

The Director is renderer-agnostic. Which runtime is active is a construction
detail. The brain doesn't need to change if you swap Live2D for Godot for
Unreal — you just pass a different PresenceRuntime.

The Director also subscribes to Voice Director events so it can react to
voice.started / voice.speaking / voice.finished / voice.interrupted without
the brain having to coordinate. See ``bind_to_voice()``.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Optional

from .runtime_bridge.base import PresenceRuntime
from .types import EmotionState, PresenceIntent, PresenceLevel, PresenceState

if TYPE_CHECKING:
    from voice.events import VoiceEvent

log = logging.getLogger("nero.presence.director")


class PresenceDirector:
    """Semantic-intent broker between the brain and the active runtime.

    Responsibilities:
        - Forward brain intents to the runtime, capped at the runtime's
          declared max level.
        - Manage lifecycle (start / stop) alongside the runtime.
        - Own the emergence + dissolution sequences so the brain never has
          to code "how does Nero appear."
        - Optionally subscribe to Voice Director events and translate them
          into presence intents so voice.speaking → state=SPEAKING happens
          automatically.

    The Director itself is renderer-agnostic. It knows about intents,
    levels, and events — never about animations, particles, or assets.
    """

    def __init__(
        self,
        runtime: PresenceRuntime,
        requested_level: PresenceLevel = PresenceLevel.L1_MINIMAL_MANIFESTATION,
    ) -> None:
        self._runtime = runtime
        # Cap requested level at runtime's ceiling — graceful degradation
        self._active_level = PresenceLevel(min(requested_level, runtime.max_presence_level))
        self._current_state = PresenceState.ABSENT
        self._current_emotion = EmotionState.NEUTRAL
        self._voice_bound = False
        self._voice_callback = self._on_voice_event  # bound method, referenced for unsub
        self._lock = threading.RLock()

    # ---- properties ----

    @property
    def runtime_name(self) -> str:
        return self._runtime.name

    @property
    def active_level(self) -> PresenceLevel:
        return self._active_level

    @property
    def current_state(self) -> PresenceState:
        return self._current_state

    # ---- lifecycle ----

    def start(self) -> None:
        """Start the underlying runtime. Safe to call multiple times."""
        with self._lock:
            if self._runtime.is_running():
                return
            self._runtime.start()
            log.info(
                "presence director started (runtime=%s, level=%s)",
                self._runtime.name,
                self._active_level.name,
            )

    def stop(self) -> None:
        """Stop the runtime. If bound to voice, unsubscribes first."""
        with self._lock:
            if self._voice_bound:
                self.unbind_from_voice()
            if not self._runtime.is_running():
                return
            self._runtime.stop()
            self._current_state = PresenceState.ABSENT
            log.info("presence director stopped")

    def is_running(self) -> bool:
        return self._runtime.is_running()

    # ---- the semantic-intent API ----

    def set_intent(self, intent: PresenceIntent) -> None:
        """Forward a semantic intent to the runtime.

        The brain calls this. Never fails on the caller's side — if the
        runtime raises, it's caught and logged (voice + chat must never
        break because visuals broke).
        """
        with self._lock:
            self._current_state = intent.state
            self._current_emotion = intent.emotion
        try:
            self._runtime.set_intent(intent)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "runtime %s raised on set_intent(state=%s): %s",
                self._runtime.name,
                intent.state.value,
                exc,
            )

    # ---- manifestation: never appears, always emerges ----

    def emerge(
        self,
        emotion: EmotionState = EmotionState.NEUTRAL,
        step_delay_s: float = 0.35,
    ) -> None:
        """Manifestation sequence: nothing → mist → eyes → silhouette → idle.

        Runs synchronously (blocking) — the caller controls timing. If you
        want async emergence, run this in a thread.

        The sequence emits intents in the order:
            EMERGING @ 0.15  (background darkens, mist begins)
            EMERGING @ 0.35  (particles + faint eyes)
            EMERGING @ 0.60  (eyes strengthen, silhouette resolves)
            EMERGING @ 0.85  (character materializes)
            IDLE      @ 1.00  (breathing begins)
        """
        if not self.is_running():
            log.warning("emerge() called on stopped director — ignoring")
            return

        for intensity in (0.15, 0.35, 0.60, 0.85):
            self.set_intent(PresenceIntent(
                state=PresenceState.EMERGING,
                emotion=emotion,
                intensity=intensity,
            ))
            time.sleep(step_delay_s)

        self.set_intent(PresenceIntent(
            state=PresenceState.IDLE,
            emotion=emotion,
            intensity=1.0,
        ))

    def dissolve(
        self,
        emotion: EmotionState = EmotionState.NEUTRAL,
        step_delay_s: float = 0.35,
    ) -> None:
        """Reverse manifestation: idle → particles disperse → silhouette fades → eyes last → absent.

        Same intent-only design — the runtime interprets the fade timing.
        """
        if not self.is_running():
            return

        for intensity in (0.85, 0.60, 0.35, 0.15):
            self.set_intent(PresenceIntent(
                state=PresenceState.DISSOLVING,
                emotion=emotion,
                intensity=intensity,
            ))
            time.sleep(step_delay_s)

        self.set_intent(PresenceIntent(
            state=PresenceState.ABSENT,
            emotion=emotion,
            intensity=0.0,
        ))

    # ---- Voice Director coordination (opt-in) ----

    def bind_to_voice(self) -> None:
        """Subscribe to voice events and translate them into presence intents.

        After binding:
            voice.started    → state=SPEAKING at intensity 0.7
            voice.speaking   → keeps state=SPEAKING at intensity 0.9
            voice.finished   → state=IDLE at intensity 1.0
            voice.interrupted→ state=IDLE at intensity 0.6

        The Director never modifies voice; it just observes. Idempotent.
        """
        if self._voice_bound:
            return
        # Import lazily so presence/ has no hard runtime dep on voice/
        from voice import events as voice_events

        voice_events.subscribe(self._voice_callback)
        self._voice_bound = True
        log.info("presence director bound to voice events")

    def unbind_from_voice(self) -> None:
        """Undo bind_to_voice(). Idempotent."""
        if not self._voice_bound:
            return
        from voice import events as voice_events

        voice_events.unsubscribe(self._voice_callback)
        self._voice_bound = False
        log.info("presence director unbound from voice events")

    def _on_voice_event(self, event: "VoiceEvent") -> None:
        """Voice → Presence translation. Runs in whichever thread fires the event."""
        kind = event.kind
        profile = event.profile

        if kind == "voice.started":
            self.set_intent(PresenceIntent(
                state=PresenceState.SPEAKING,
                emotion=self._current_emotion,
                intensity=0.7,
                voice_profile=profile,
            ))
        elif kind == "voice.speaking":
            self.set_intent(PresenceIntent(
                state=PresenceState.SPEAKING,
                emotion=self._current_emotion,
                intensity=0.9,
                voice_profile=profile,
                metadata={"sample_rate": event.metadata.get("sample_rate")},
            ))
        elif kind == "voice.finished":
            self.set_intent(PresenceIntent(
                state=PresenceState.IDLE,
                emotion=self._current_emotion,
                intensity=1.0,
                voice_profile=profile,
            ))
        elif kind == "voice.interrupted":
            self.set_intent(PresenceIntent(
                state=PresenceState.IDLE,
                emotion=self._current_emotion,
                intensity=0.6,
                voice_profile=profile,
            ))
        # Unknown event kinds are ignored — additive evolution stays safe
