"""voice.manager.voice_manager — the single routing authority (presentation layer).

*"Given a voice request, select the best available presentation path and attempt
audio delivery."* The Voice Manager composes the **Voice Capability Graph**
("can this voice perform?") and the **Engine Health Cache** ("should this engine
be attempted?"), walks an **injected** fallback chain, attempts synthesis, records
health outcomes, and emits telemetry. It is an ORCHESTRATOR — never a brain.

**Owns:** candidate resolution · capability + health checks · the synthesis
attempt · fallback progression · a clear result · telemetry.
**Does NOT own:** reasoning, user-intent detection, personality generation,
memory, security/permissions, capability execution, engine synthesis logic, or
preference storage.

It **never creates or infers** fallback relationships — ordering comes entirely
from injected data (`fallback_map`; wired to `cast.json` in Stage 5). It imports
nothing from `app/` and makes no executive calls. Telemetry is observational only:
it never influences routing, never touches health state, never triggers recovery.

Routing chain:  preferred voice → injected personality fallbacks → emergency voice
(NERO PRIME) → text-only. The result's `outcome` distinguishes primary / fallback
/ text_only for future diagnostics. Never raises; never returns None.
"""
from __future__ import annotations

import time
from typing import Callable

from ..local_tts.base import AudioResult, VoiceRequest
from ..local_tts.engine_health import EngineHealthCache
from ..local_tts.voice_capability_graph import VoiceCapabilityGraph

# Routing outcomes — carried on AudioResult.outcome.
OUTCOME_PRIMARY = "primary"      # the preferred voice produced audio
OUTCOME_FALLBACK = "fallback"    # a fallback voice produced audio
OUTCOME_TEXT_ONLY = "text_only"  # every candidate failed — no audio


class VoiceManager:
    """The single presentation-layer routing authority. Small on purpose: a
    constructor and `speak()`. No workers, queues, scheduling, sessions, caches,
    or conversation state — those belong elsewhere."""

    def __init__(
        self,
        graph: VoiceCapabilityGraph,
        health: EngineHealthCache,
        *,
        emergency_voice: str = "nero_prime",
        fallback_map: dict | None = None,
        telemetry: Callable[[dict], None] | None = None,
    ) -> None:
        self._graph = graph
        self._health = health
        self._emergency = emergency_voice
        self._fallback = dict(fallback_map or {})   # voice_id -> ordered fallback voice_ids
        self._telemetry = telemetry

    def speak(self, request: VoiceRequest) -> AudioResult:
        """Route `request` and attempt delivery. Returns an AudioResult whose
        `outcome` is 'primary', 'fallback', or 'text_only'."""
        candidates = self._candidates(request)
        preferred = candidates[0] if candidates else self._emergency

        for voice_id in candidates:
            cap = self._graph.get(voice_id)
            if cap is None:
                continue                                        # voice not registered
            if request.language and request.language not in cap.languages:
                self._emit({"event": "skip", "reason": "language", "voice": voice_id})
                continue
            if not self._graph.can_perform(voice_id):
                self._emit({"event": "skip", "reason": "unavailable",
                            "voice": voice_id, "engine": cap.engine})
                continue
            if not self._health.should_attempt(cap.engine):
                self._emit({"event": "skip", "reason": "cooldown",
                            "voice": voice_id, "engine": cap.engine})
                continue

            resolved = self._graph.resolve(voice_id)
            engine = resolved.engine if resolved else None
            if engine is None:
                continue

            started = time.perf_counter()
            try:
                result = engine.synthesize(_with_voice(request, voice_id))
            except Exception as exc:  # noqa: BLE001 - an engine crash becomes a health failure, never an app crash
                self._health.record_failure(cap.engine, f"{type(exc).__name__}: {exc}")
                self._emit({"event": "engine_failed", "voice": voice_id,
                            "engine": cap.engine, "error": str(exc)})
                continue
            latency_ms = round((time.perf_counter() - started) * 1000, 1)

            if result.ok and result.audio:
                self._health.record_success(cap.engine)
                result.outcome = OUTCOME_PRIMARY if voice_id == preferred else OUTCOME_FALLBACK
                self._emit({"event": "selected", "voice": voice_id, "engine": cap.engine,
                            "outcome": result.outcome, "latency_ms": latency_ms})
                return result

            # a clean failure (ok False) — record and keep falling back
            self._health.record_failure(cap.engine, result.error or "no audio")
            self._emit({"event": "engine_failed", "voice": voice_id,
                        "engine": cap.engine, "error": result.error})

        # every candidate exhausted — an explicit text-only result, never silent
        self._emit({"event": "text_only", "requested": preferred})
        return AudioResult(ok=False, engine="", voice_id=preferred,
                           error="no voice could deliver this response",
                           outcome=OUTCOME_TEXT_ONLY)

    def _candidates(self, request: VoiceRequest) -> list[str]:
        """Ordered candidates: preferred → injected fallbacks → emergency (deduped,
        order preserved). The manager knows the ORDER, never the *reason* two
        voices are related — that is injected data (cast.json, Stage 5)."""
        preferred = (request.voice_id or "").strip() or self._emergency
        order = [preferred, *self._fallback.get(preferred, ()), self._emergency]
        seen: set[str] = set()
        out: list[str] = []
        for voice_id in order:
            if voice_id and voice_id not in seen:
                seen.add(voice_id)
                out.append(voice_id)
        return out

    def _emit(self, event: dict) -> None:
        if self._telemetry is None:
            return
        try:
            self._telemetry(event)
        except Exception:  # noqa: BLE001 - telemetry is observational; it must never affect routing
            pass


def _with_voice(request: VoiceRequest, voice_id: str) -> VoiceRequest:
    """A copy of the request targeting a specific candidate voice (delivery metadata
    passed through untouched — the manager generates no personality)."""
    return VoiceRequest(
        text=request.text, voice_id=voice_id, language=request.language,
        speed=request.speed, delivery=request.delivery,
    )
