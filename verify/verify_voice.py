#!/usr/bin/env python3
"""Self-test for the Voice Platform — Stage 1: the TTSEngine contract.

Model-independent and fully offline (no engine bodies, no models, no GPU): proves
the interface's health-reporting envelope and best-effort failure paths on any
machine. Engine bodies + all GPU/VRAM/latency verification are the local RTX-4070
environment's job (never cloud assumption). Exit 0 = pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import (  # noqa: E402
    BaseTTSEngine, EngineStatus, NullEngine, TTSEngine, VoiceRequest,
)
from voice.local_tts.voice_capability_graph import (  # noqa: E402
    QualityLevel, VoiceCapability, VoiceCapabilityGraph,
)
from voice.local_tts.engine_health import (  # noqa: E402
    EngineHealthCache, HealthStatus,
)
from voice.manager.voice_manager import (  # noqa: E402
    OUTCOME_FALLBACK, OUTCOME_PRIMARY, OUTCOME_TEXT_ONLY, VoiceManager,
)
from voice.profiles.loader import (  # noqa: E402
    DEFAULT_CAST_PATH, CastError, load_cast,
)
from voice.personalities.performance_director import (  # noqa: E402
    PerformanceDirector, direct as direct_delivery,
)
from voice.manager.events import (  # noqa: E402
    VoiceEvent, VoiceEventBus, VoiceEventType, from_manager_event,
)
from voice.manager.telemetry import (  # noqa: E402
    VoiceTelemetry, VoiceTelemetrySnapshot,
)
from voice.manager.startup import (  # noqa: E402
    ReadinessState, StartupError, VoiceRuntime, build_voice_runtime,
)
from voice.manager.health import (  # noqa: E402
    VoiceHealthLevel, VoiceHealthReport, build_health_report, report_for_runtime,
)

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


class _Stub(BaseTTSEngine):
    name = "stub"
    _languages = ("en", "hr")
    _voices = ("nero_prime",)

    def _available(self) -> bool:
        return True

    def _synthesize(self, request):
        return (b"fake-wav", 24_000)


def main() -> int:
    null = NullEngine()
    check("NullEngine is unavailable", null.available() is False)
    check("NullEngine health is UNAVAILABLE", null.health().status == EngineStatus.UNAVAILABLE)
    check("NullEngine.synthesize fails cleanly (never raises)",
          null.synthesize(VoiceRequest(text="hi")).ok is False)

    stub = _Stub()
    r = stub.synthesize(VoiceRequest(text="Good evening, Toni.", voice_id="nero_prime"))
    check("a stub engine synthesizes (ok + audio + rate)",
          r.ok and bool(r.audio) and r.sample_rate == 24_000)
    check("stub health becomes READY after success", stub.health().status == EngineStatus.READY)
    check("languages/voices reported", stub.languages() == ["en", "hr"] and stub.voices() == ["nero_prime"])
    check("empty request is a clean failure", stub.synthesize(VoiceRequest(text=" ")).ok is False)

    check("both engines satisfy the TTSEngine Protocol (API-first)",
          isinstance(stub, TTSEngine) and isinstance(null, TTSEngine))

    # ---- Stage 2: Voice Capability Graph (runtime discovery) ----
    graph = VoiceCapabilityGraph()
    graph.register(VoiceCapability("nero_prime", "stub", ("en", "hr"),
                                   ("emotion",), QualityLevel.PREMIUM), stub)
    graph.register(VoiceCapability("nero_demon", "null", ("en",)), null)
    check("graph lists all registered voices",
          set(graph.voices()) == {"nero_prime", "nero_demon"})
    check("can_perform is LIVE: available engine -> True, unavailable -> False",
          graph.can_perform("nero_prime") is True and graph.can_perform("nero_demon") is False)
    check("available_voices returns only voices live right now",
          [c.voice_id for c in graph.available_voices()] == ["nero_prime"])
    check("available_voices filters by language",
          [c.voice_id for c in graph.available_voices(language="hr")] == ["nero_prime"]
          and graph.available_voices(language="fr") == [])
    check("resolve returns capability + engine + live status",
          graph.resolve("nero_prime").available is True
          and graph.resolve("nero_demon").available is False)
    check("snapshot is a telemetry view with live availability",
          {r["voice_id"]: r["available"] for r in graph.snapshot()}
          == {"nero_prime": True, "nero_demon": False})

    # ---- Stage 3: Engine Health Cache (attempt gating, deterministic clock) ----
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
    hc = EngineHealthCache(base_cooldown_s=5.0, max_cooldown_s=30.0)
    check("unknown engine is attemptable (UNKNOWN)",
          hc.should_attempt("kokoro", now=t0) and hc.status("kokoro", now=t0) == HealthStatus.UNKNOWN)
    hc.record_failure("kokoro", "no audio", now=t0)
    check("failure -> COOLDOWN, attempts blocked (cached, no re-probe)",
          hc.status("kokoro", now=t0 + timedelta(seconds=2)) == HealthStatus.COOLDOWN
          and hc.should_attempt("kokoro", now=t0 + timedelta(seconds=2)) is False)
    check("cooldown expiry -> RECOVERING, attempt allowed",
          hc.should_attempt("kokoro", now=t0 + timedelta(seconds=6)) is True
          and hc.status("kokoro", now=t0 + timedelta(seconds=6)) == HealthStatus.RECOVERING)
    hc.record_success("kokoro", now=t0 + timedelta(seconds=6))
    check("recovery clears failure history (AVAILABLE, 0 failures)",
          hc.status("kokoro", now=t0 + timedelta(seconds=6)) == HealthStatus.AVAILABLE
          and hc.get("kokoro").consecutive_failures == 0)
    hc.record_failure("kokoro", now=t0)
    hc.record_success("mms_hr", now=t0)
    check("one broken engine does not affect another",
          hc.should_attempt("kokoro", now=t0 + timedelta(seconds=1)) is False
          and hc.should_attempt("mms_hr", now=t0 + timedelta(seconds=1)) is True)

    # ---- Stage 4: Voice Manager (single routing authority, composition) ----
    class _Ok(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self.calls = 0
        def _available(self): return True
        def _synthesize(self, request): self.calls += 1; return (b"wav", 24_000)

    class _Fail(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name
        def _available(self): return True
        def _synthesize(self, request): return (b"", 0)

    g4 = VoiceCapabilityGraph()
    e_prime, e_luna = _Ok("e_prime"), _Ok("e_luna")
    g4.register(VoiceCapability("nero_prime", "e_prime", ("en",)), e_prime)
    g4.register(VoiceCapability("nero_luna", "e_luna", ("en",)), e_luna)
    h4 = EngineHealthCache(base_cooldown_s=5.0)
    mgr = VoiceManager(g4, h4, emergency_voice="nero_prime",
                       fallback_map={"nero_prime": ("nero_luna",)})
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    check("preferred voice wins (outcome=primary), fallback untouched",
          r.ok and r.outcome == OUTCOME_PRIMARY and e_luna.calls == 0)
    h4.record_failure("e_prime", "down")   # prime engine now in cooldown
    r2 = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    check("unhealthy engine skipped -> fallback voice used (outcome=fallback)",
          r2.ok and r2.voice_id == "nero_luna" and r2.outcome == OUTCOME_FALLBACK)
    g5 = VoiceCapabilityGraph()
    g5.register(VoiceCapability("nero_prime", "null", ("en",)), null)
    r3 = VoiceManager(g5, EngineHealthCache()).speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    check("all engines down -> explicit text_only, never crash",
          r3.ok is False and r3.outcome == OUTCOME_TEXT_ONLY)

    # ---- Stage 5: Voice Profiles (cast.json + loader, declarative identity) ----
    class _Ok5(BaseTTSEngine):
        def __init__(self, name, langs=("en",)):
            super().__init__(); self.name = name; self._languages = tuple(langs)
        def _available(self): return True
        def _synthesize(self, request): return (b"wav", 24_000)

    class _Fail5(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)
        def _available(self): return True
        def _synthesize(self, request): return (b"", 0)

    shipped = load_cast(DEFAULT_CAST_PATH)
    check("shipped cast.json loads and validates (10 voices, emergency exists)",
          len(shipped.profiles) == 10
          and shipped.emergency_voice in {p.voice_id for p in shipped.profiles})

    def _tmp_cast(data) -> str:
        import json as _json
        import os as _os
        import tempfile as _tf
        fd, path = _tf.mkstemp(suffix=".json", prefix="verify_cast_")
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else _json.dumps(data))
        return path

    def _err(data) -> bool:
        import os as _os
        path = _tmp_cast(data)
        try:
            load_cast(path)
            return False
        except CastError:
            return True
        except Exception:            # any non-CastError leak is a failure of the contract
            return False
        finally:
            _os.remove(path)

    valid = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "e_prime", "languages": ["en"],
         "fallbacks": ["nero_luna"]},
        {"voice_id": "nero_luna", "engine": "e_luna", "languages": ["en"]},
    ]}
    cast5 = load_cast(_tmp_cast_cleanup := _tmp_cast(valid))
    import os as _os5
    _os5.remove(_tmp_cast_cleanup)

    g6 = VoiceCapabilityGraph()
    cast5.populate(g6, {"e_prime": _Ok5("e_prime"), "e_luna": _Ok5("e_luna")})
    check("loaded profiles populate the Capability Graph",
          set(g6.voices()) == {"nero_prime", "nero_luna"} and g6.can_perform("nero_prime"))

    g7 = VoiceCapabilityGraph()
    cast5.populate(g7, {"e_prime": _Fail5("e_prime"), "e_luna": _Ok5("e_luna")})
    mgr5 = VoiceManager(g7, EngineHealthCache(), emergency_voice=cast5.emergency_voice,
                        fallback_map=cast5.fallback_map)
    rr = mgr5.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    check("fallback is driven from cast data (prime fails -> luna delivers)",
          rr.ok and rr.voice_id == "nero_luna" and rr.outcome == OUTCOME_FALLBACK)

    lang_bad = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"]},
        {"voice_id": "nero_luna", "engine": "kokoro", "languages": ["hr"]},
    ]}
    cast_lang = load_cast(_p := _tmp_cast(lang_bad)); _os5.remove(_p)
    try:
        cast_lang.populate(VoiceCapabilityGraph(), {"kokoro": _Ok5("kokoro", ("en",))})
        lang_caught = False
    except CastError:
        lang_caught = True
    check("language mismatch fails loudly at load/wire time (Stage 4 finding)", lang_caught)

    try:
        cast5.populate(VoiceCapabilityGraph(), {"e_prime": _Ok5("e_prime")})  # e_luna missing
        eng_caught = False
    except CastError:
        eng_caught = True
    check("a missing engine binding is a CastError", eng_caught)

    check("malformed JSON -> CastError (never a raw JSONDecodeError)",
          _err("{ not json "))
    check("missing manifest file -> CastError (never a raw FileNotFoundError)",
          _missing_is_cast_error())
    check("duplicate voice_id -> CastError", _err(
          {"emergency": "a", "voices": [{"voice_id": "a", "engine": "e"},
                                        {"voice_id": "a", "engine": "e"}]}))
    check("circular fallback chain -> CastError", _err(
          {"emergency": "a", "voices": [{"voice_id": "a", "engine": "e", "fallbacks": ["b"]},
                                        {"voice_id": "b", "engine": "e", "fallbacks": ["a"]}]}))
    check("empty cast loads safely (0 voices, no crash)",
          _empty_cast_ok(_tmp_cast))

    # ---- Stage 6: Performance Director (deterministic delivery interpretation) ----
    class _Capture(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",); self.seen = None
        def _available(self): return True
        def _synthesize(self, request): self.seen = dict(request.delivery); return (b"wav", 24_000)

    director = PerformanceDirector()
    intent = {"emotion": "serious", "authority": 5.0, "pace": "slow",
              "effect": "subtle_system_alert", "humor": 0.7, "warmth": -1.0}
    p1 = director.direct(VoiceRequest(text="x", delivery=intent)).delivery
    p2 = direct_delivery(VoiceRequest(text="x", delivery=intent)).delivery
    check("delivery normalization is deterministic (same intent -> same plan)", p1 == p2)
    check("numeric dials clamp to [0,1] (authority 5.0 -> 1.0, warmth -1.0 -> 0.0)",
          p1["authority"] == 1.0 and p1["warmth"] == 0.0)
    check("pace word normalized (slow -> 0.85), unknown effect dropped, known kept",
          p1["pace"] == 0.85 and p1["effects"] == ["subtle_system_alert"])

    src_req = VoiceRequest(text="Dobar dan", voice_id="nero_luna", language="hr", speed=1.2,
                           delivery={"emotion": "warm"})
    out_req = director.direct(src_req)
    check("request identity preserved (text/voice_id/language/speed), input not mutated",
          out_req.text == "Dobar dan" and out_req.voice_id == "nero_luna"
          and out_req.language == "hr" and out_req.speed == 1.2
          and src_req.delivery == {"emotion": "warm"})
    check("Director owns no routing (never invents/changes voice_id)",
          director.direct(VoiceRequest(text="x", delivery={})).voice_id == ""
          and "voice_id" not in out_req.delivery and "voice" not in out_req.delivery)

    cap = _Capture("cap")
    g6d = VoiceCapabilityGraph()
    g6d.register(VoiceCapability("nero_prime", "cap", ("en",)), cap)
    mgr6 = VoiceManager(g6d, EngineHealthCache(), emergency_voice="nero_prime")
    directed = director.direct(VoiceRequest(text="hi", voice_id="nero_prime",
                                            delivery={"emotion": "serious", "pace": "fast"}))
    res6 = mgr6.speak(directed)
    check("canonical delivery reaches the engine unchanged through the Voice Manager",
          res6.ok and cap.seen == directed.delivery and cap.seen["pace"] == 1.15)

    # ---- Stage 7: Voice Event Bus (observational only, wraps the telemetry seam) ----
    from datetime import datetime as _dt, timezone as _tz
    _fixed = _dt(2026, 7, 12, 12, 0, 0, tzinfo=_tz.utc)

    check("telemetry dicts convert to typed events (selected/fallback/failed/text_only)",
          from_manager_event({"event": "selected", "outcome": "primary"}).type == VoiceEventType.VOICE_SELECTED
          and from_manager_event({"event": "selected", "outcome": "fallback"}).type == VoiceEventType.FALLBACK_USED
          and from_manager_event({"event": "engine_failed"}).type == VoiceEventType.ENGINE_FAILED
          and from_manager_event({"event": "text_only"}).type == VoiceEventType.TEXT_ONLY_RESULT
          and from_manager_event({"event": "mystery"}) is None)      # unknown -> ignored

    bus7 = VoiceEventBus(clock=lambda: _fixed)
    delivered: list = []
    bus7.subscribe(delivered.append)
    bus7.emit(VoiceEvent(type=VoiceEventType.VOICE_SELECTED, payload={"voice": "nero_prime"}))
    check("a subscriber receives an immutable, timestamped, sequenced event",
          len(delivered) == 1 and delivered[0].sequence == 0
          and delivered[0].timestamp == _fixed.isoformat())

    def _boom(_): raise RuntimeError("bad observer")
    seen7: list = []
    bus7.subscribe(_boom); bus7.subscribe(seen7.append)
    bus7.emit(VoiceEvent(type=VoiceEventType.ENGINE_FAILED))         # must not raise
    check("one failing subscriber does not stop the others", len(seen7) == 1)

    empty_bus = VoiceEventBus(clock=lambda: _fixed)
    try:
        empty_bus.emit(VoiceEvent(type=VoiceEventType.TEXT_ONLY_RESULT))
        zero_ok = True
    except Exception:
        zero_ok = False
    check("zero subscribers is a safe no-op", zero_ok)

    # real Manager -> telemetry callback -> bus (Option B; Manager unchanged)
    class _Fail7(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)
        def _available(self): return True
        def _synthesize(self, request): return (b"", 0)

    class _Ok7(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)
        def _available(self): return True
        def _synthesize(self, request): return (b"wav", 24_000)

    bus7b = VoiceEventBus(clock=lambda: _fixed)
    evs: list = []
    bus7b.subscribe(evs.append)
    g7 = VoiceCapabilityGraph()
    g7.register(VoiceCapability("nero_prime", "e_prime", ("en",)), _Fail7("e_prime"))
    g7.register(VoiceCapability("nero_luna", "e_luna", ("en",)), _Ok7("e_luna"))
    mgr7 = VoiceManager(g7, EngineHealthCache(), emergency_voice="nero_prime",
                        fallback_map={"nero_prime": ("nero_luna",)}, telemetry=bus7b.manager_sink())
    r7 = mgr7.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    kinds = [e.type for e in evs]
    check("real Manager drives real events through manager_sink(), fallback intact",
          r7.ok and r7.voice_id == "nero_luna"
          and VoiceEventType.ENGINE_FAILED in kinds and VoiceEventType.FALLBACK_USED in kinds)

    # ---- Stage 8: Voice Telemetry (observe + aggregate; a bus subscriber) ----
    from types import MappingProxyType as _MPT

    bus8 = VoiceEventBus()
    telem8 = VoiceTelemetry()
    telem8.attach(bus8)
    bus8.emit(VoiceEvent(type=VoiceEventType.VOICE_SELECTED,
                         payload={"voice": "nero_prime", "engine": "kokoro", "latency_ms": 10.0}))
    bus8.emit(VoiceEvent(type=VoiceEventType.FALLBACK_USED,
                         payload={"voice": "nero_luna", "engine": "e_luna", "latency_ms": 20.0}))
    bus8.emit(VoiceEvent(type=VoiceEventType.ENGINE_FAILED,
                         payload={"voice": "nero_prime", "engine": "e_prime", "error": "no audio"}))
    snap8 = telem8.snapshot()
    check("telemetry subscribes to the bus and aggregates facts",
          snap8.total_events == 3 and snap8.primary_count == 1 and snap8.fallback_count == 1
          and snap8.engine_failures == 1 and snap8.per_engine_failures["e_prime"] == 1
          and snap8.average_latency_ms == 15.0)

    check("snapshot is immutable (frozen + read-only maps)",
          isinstance(snap8, VoiceTelemetrySnapshot)
          and isinstance(snap8.per_voice_counts, _MPT) and _frozen(snap8))

    a8, b8 = VoiceTelemetry(), VoiceTelemetry()
    a8.handle(VoiceEvent(type=VoiceEventType.VOICE_SELECTED, payload={"voice": "nero_prime"}))
    check("telemetry instances are isolated",
          a8.snapshot().primary_count == 1 and b8.snapshot().primary_count == 0)

    # real Manager -> telemetry callback -> bus -> telemetry (routing unaffected)
    class _Fail8(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)
        def _available(self): return True
        def _synthesize(self, request): return (b"", 0)

    class _Ok8(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)
        def _available(self): return True
        def _synthesize(self, request): return (b"wav", 24_000)

    bus8b = VoiceEventBus()
    telem8b = VoiceTelemetry(); telem8b.attach(bus8b)
    g8 = VoiceCapabilityGraph()
    g8.register(VoiceCapability("nero_prime", "e_prime", ("en",)), _Fail8("e_prime"))
    g8.register(VoiceCapability("nero_luna", "e_luna", ("en",)), _Ok8("e_luna"))
    h8 = EngineHealthCache()
    mgr8 = VoiceManager(g8, h8, emergency_voice="nero_prime",
                        fallback_map={"nero_prime": ("nero_luna",)}, telemetry=bus8b.manager_sink())
    r8 = mgr8.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    s8b = telem8b.snapshot()
    check("real Manager -> Event Bus -> Telemetry path works, routing unaffected",
          r8.ok and r8.voice_id == "nero_luna"
          and h8.get("e_prime").consecutive_failures == 1
          and s8b.fallback_count == 1 and s8b.engine_failures == 1)

    # ---- Stage 9: Warm Startup / Voice Runtime Initialization (composition root) ----
    import json as _json9, os as _os9, tempfile as _tf9
    from datetime import datetime as _dt9, timezone as _tz9
    _fixed9 = _dt9(2026, 7, 12, 12, 0, 0, tzinfo=_tz9.utc)

    class _Ok9(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",); self.calls = 0
        def _available(self): return True
        def _synthesize(self, request): self.calls += 1; return (b"wav", 24_000)

    class _Fail9(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)
        def _available(self): return True
        def _synthesize(self, request): return (b"", 0)

    def _cast9(data):
        fd, path = _tf9.mkstemp(suffix=".json", prefix="verify_rt_")
        with _os9.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(_json9.dumps(data))
        return path

    fb = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "e_prime", "languages": ["en"], "fallbacks": ["nero_luna"]},
        {"voice_id": "nero_luna", "engine": "e_luna", "languages": ["en"]}]}
    p9 = _cast9(fb)
    rt = build_voice_runtime(engines={"e_prime": _Fail9("e_prime"), "e_luna": _Ok9("e_luna")},
                             cast_path=p9, clock=lambda: _fixed9)
    _os9.remove(p9)
    check("build_voice_runtime composes a wired VoiceRuntime (manager/bus/telemetry/graph/health/cast)",
          isinstance(rt, VoiceRuntime) and rt.manager and rt.bus and rt.telemetry
          and set(rt.graph.voices()) == {"nero_prime", "nero_luna"})

    check("readiness reports READY (emergency voice available), asks the graph, mutates nothing",
          rt.readiness().state == ReadinessState.READY
          and rt.health.get("e_prime") is None)          # no health record created at boot

    try:
        build_voice_runtime(engines={}, cast_path="/no/such/verify_rt_missing.json")
        startup_failed_loud = False
    except StartupError:
        startup_failed_loud = True
    check("a composition failure is a loud StartupError (no partial runtime)", startup_failed_loud)

    observed9: list = []
    rt.bus.subscribe(observed9.append)
    r9 = rt.manager.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    snap9 = rt.telemetry.snapshot()
    kinds9 = [e.type for e in observed9]
    check("end-to-end: composed runtime falls back correctly; bus observes; telemetry records",
          r9.ok and r9.voice_id == "nero_luna"
          and VoiceEventType.ENGINE_FAILED in kinds9 and VoiceEventType.FALLBACK_USED in kinds9
          and snap9.fallback_count == 1 and rt.health.get("e_prime").consecutive_failures == 1)

    # ---- Stage 10: Voice Health Check (stateless read-only interpreter) ----
    # A FRESH runtime (prime fails -> luna), isolated so counts are deterministic.
    p10 = _cast9(fb)
    rt10 = build_voice_runtime(engines={"e_prime": _Fail9("e_prime"), "e_luna": _Ok9("e_luna")},
                               cast_path=p10, clock=lambda: _fixed9)
    _os9.remove(p10)
    rt10.manager.speak(VoiceRequest(text="hi", voice_id="nero_prime"))     # one fallback
    hr = report_for_runtime(rt10, clock=lambda: _fixed9)
    check("health report composes three lenses (availability + attempt-health + execution)",
          isinstance(hr, VoiceHealthReport) and isinstance(hr.available_voices, tuple)
          and hr.recent is not None)
    check("attempt-health lens surfaces the failed engine's cooldown (recorded by the Manager)",
          hr.engines["e_prime"].consecutive_failures == 1
          and hr.engines["e_prime"].should_attempt is False and "e_prime" in hr.gated_engines)
    check("execution lens reflects the Telemetry snapshot (failure + fallback)",
          hr.recent.engine_failures == 1 and hr.recent.fallback_count == 1
          and hr.overall == VoiceHealthLevel.DEGRADED)

    before10 = rt10.health.get("e_prime").consecutive_failures
    report_for_runtime(rt10, clock=lambda: _fixed9)        # re-report...
    check("the health report changes nothing (no health mutation, stateless)",
          rt10.health.get("e_prime").consecutive_failures == before10)

    # rollup determinism (pure function): OFFLINE when no voice can perform
    class _Down10(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)
        def _available(self): return False
        def _synthesize(self, request): return (b"", 0)
    g10 = VoiceCapabilityGraph()
    g10.register(VoiceCapability("nero_prime", "d", ("en",)), _Down10("d"))
    off = build_health_report(graph=g10, engine_health=EngineHealthCache(),
                              emergency_voice="nero_prime", clock=lambda: _fixed9)
    check("rollup is a pure function: no available voice -> OFFLINE",
          off.overall == VoiceHealthLevel.OFFLINE and off.available_voices == ())

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Voice Stages 1-10 (contract + Capability Graph + Health Cache + Voice "
          "Manager + Voice Profiles + Performance Director + Event Bus + Telemetry + "
          "Warm Startup + Health Check) verified.")
    return 0


def _frozen(obj) -> bool:
    """True if `obj` is a frozen dataclass instance (attribute assignment raises)."""
    try:
        object.__getattribute__(obj, "__dataclass_fields__")
        obj.schema_version = -999
        return False
    except Exception:
        return True


def _missing_is_cast_error() -> bool:
    try:
        load_cast("/no/such/path/verify_missing_cast.json")
        return False
    except CastError:
        return True
    except Exception:
        return False


def _empty_cast_ok(tmp_cast) -> bool:
    import os as _os
    path = tmp_cast({"voices": []})
    try:
        cast = load_cast(path)
        return cast.profiles == () and cast.emergency_voice == ""
    except Exception:
        return False
    finally:
        _os.remove(path)


if __name__ == "__main__":
    sys.exit(main())
