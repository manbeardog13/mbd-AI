"""Voice Platform tests — Stage 8: Voice Telemetry (observe + aggregate).

Proves telemetry is a pure observer: it subscribes to the Stage 7 Event Bus,
aggregates lifecycle facts into in-memory counters, exposes immutable snapshots,
and can never influence routing or health. Model-independent (test-double engines
only), deterministic, no GPU, no external services.

Run directly:  python tests/test_voice_telemetry.py
"""
import sys
from pathlib import Path
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import BaseTTSEngine, VoiceRequest
from voice.local_tts.engine_health import EngineHealthCache
from voice.local_tts.voice_capability_graph import VoiceCapability, VoiceCapabilityGraph
from voice.manager.events import VoiceEvent, VoiceEventBus, VoiceEventType
from voice.manager.telemetry import VoiceTelemetry, VoiceTelemetrySnapshot
from voice.manager.voice_manager import VoiceManager


def _src() -> str:
    return (Path(__file__).resolve().parent.parent / "voice" / "manager"
            / "telemetry.py").read_text(encoding="utf-8")


def _ev(etype, **payload) -> VoiceEvent:
    return VoiceEvent(type=etype, payload=payload)


# ---- test-double engines ----
class OkEngine(BaseTTSEngine):
    def __init__(self, name, langs=("en",)):
        super().__init__(); self.name = name; self._languages = tuple(langs); self.calls = 0

    def _available(self): return True

    def _synthesize(self, request):
        self.calls += 1
        return (b"wav-" + self.name.encode(), 24_000)


class FailEngine(BaseTTSEngine):
    def __init__(self, name):
        super().__init__(); self.name = name; self._languages = ("en",)

    def _available(self): return True

    def _synthesize(self, request):
        return (b"", 0)


def _fallback_manager(telemetry=None):
    """prime (fails) -> luna (ok); emergency prime. Returns (manager, health, engines)."""
    prime, luna = FailEngine("e_prime"), OkEngine("e_luna")
    graph = VoiceCapabilityGraph()
    graph.register(VoiceCapability("nero_prime", "e_prime", ("en",)), prime)
    graph.register(VoiceCapability("nero_luna", "e_luna", ("en",)), luna)
    health = EngineHealthCache(base_cooldown_s=5.0)
    mgr = VoiceManager(graph, health, emergency_voice="nero_prime",
                       fallback_map={"nero_prime": ("nero_luna",)}, telemetry=telemetry)
    return mgr, health, (prime, luna)


# ---- 1. subscription works ----
def test_bus_subscription_works():
    bus, t = VoiceEventBus(), VoiceTelemetry()
    t.attach(bus)
    bus.emit(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro", latency_ms=12.0))
    assert t.snapshot().total_events == 1 and t.snapshot().primary_count == 1


# ---- 2. VOICE_SELECTED increments primary ----
def test_primary_selection_counted():
    t = VoiceTelemetry()
    t.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro", latency_ms=10.0))
    t.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro", latency_ms=20.0))
    s = t.snapshot()
    assert s.primary_count == 2 and s.fallback_count == 0 and s.selected_count == 2
    assert s.average_latency_ms == 15.0             # (10 + 20) / 2


# ---- 3. FALLBACK_USED increments fallback ----
def test_fallback_counted():
    t = VoiceTelemetry()
    t.handle(_ev(VoiceEventType.FALLBACK_USED, voice="nero_luna", engine="e_luna", latency_ms=8.0))
    s = t.snapshot()
    assert s.fallback_count == 1 and s.primary_count == 0 and s.selected_count == 1


# ---- 4. ENGINE_FAILED increments failures ----
def test_engine_failures_counted():
    t = VoiceTelemetry()
    t.handle(_ev(VoiceEventType.ENGINE_FAILED, voice="nero_prime", engine="e_prime", error="no audio"))
    s = t.snapshot()
    assert s.engine_failures == 1 and s.per_engine_failures["e_prime"] == 1


# ---- 5. TEXT_ONLY_RESULT increments text-only ----
def test_text_only_counted():
    t = VoiceTelemetry()
    t.handle(_ev(VoiceEventType.TEXT_ONLY_RESULT, requested="nero_prime"))
    assert t.snapshot().text_only_count == 1


# ---- 6. multiple voices aggregate ----
def test_multiple_voices_aggregate():
    t = VoiceTelemetry()
    t.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro"))
    t.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro"))
    t.handle(_ev(VoiceEventType.FALLBACK_USED, voice="nero_luna", engine="e_luna"))
    counts = t.snapshot().per_voice_counts
    assert counts["nero_prime"] == 2 and counts["nero_luna"] == 1


# ---- 7. multiple engines aggregate ----
def test_multiple_engines_aggregate():
    t = VoiceTelemetry()
    t.handle(_ev(VoiceEventType.ENGINE_FAILED, engine="e_prime"))
    t.handle(_ev(VoiceEventType.ENGINE_FAILED, engine="e_prime"))
    t.handle(_ev(VoiceEventType.ENGINE_FAILED, engine="e_luna"))
    fails = t.snapshot().per_engine_failures
    assert fails["e_prime"] == 2 and fails["e_luna"] == 1 and t.snapshot().engine_failures == 3


# ---- 8. snapshot is immutable ----
def test_snapshot_is_immutable():
    t = VoiceTelemetry()
    t.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro"))
    snap = t.snapshot()
    try:
        snap.primary_count = 99          # frozen -> must raise
        frozen = False
    except Exception:
        frozen = True
    assert frozen
    assert isinstance(snap.per_voice_counts, MappingProxyType)
    try:
        snap.per_voice_counts["x"] = 1   # read-only -> must raise
        ro = False
    except TypeError:
        ro = True
    assert ro


# ---- 9. snapshot is detached from later updates ----
def test_snapshot_detached_from_later_updates():
    t = VoiceTelemetry()
    t.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro"))
    snap = t.snapshot()
    t.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro"))
    assert snap.primary_count == 1 and snap.per_voice_counts["nero_prime"] == 1
    assert t.snapshot().primary_count == 2      # live collector advanced; old snapshot did not


# ---- 10. subscriber failure isolation still holds ----
def test_subscriber_failure_isolation():
    bus = VoiceEventBus()
    def boom(_): raise RuntimeError("bad telemetry subscriber")
    bus.subscribe(boom)
    t = VoiceTelemetry(); t.attach(bus)
    mgr, _, _ = _fallback_manager(telemetry=bus.manager_sink())
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna"           # speak() survives a bad subscriber
    assert t.snapshot().fallback_count == 1             # telemetry still aggregated its events


# ---- 11. telemetry cannot influence routing ----
def test_telemetry_cannot_influence_routing():
    bus = VoiceEventBus()
    t = VoiceTelemetry(); t.attach(bus)
    mgr, health, (prime, luna) = _fallback_manager(telemetry=bus.manager_sink())
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna"           # routing outcome unchanged
    assert health.get("e_prime").consecutive_failures == 1
    assert health.get("e_luna").state.value == "available"
    s = t.snapshot()
    assert s.fallback_count == 1 and s.engine_failures == 1 and s.per_engine_failures["e_prime"] == 1


# ---- 12. multiple instances isolated ----
def test_instances_isolated():
    a, b = VoiceTelemetry(), VoiceTelemetry()
    a.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro"))
    assert a.snapshot().primary_count == 1 and b.snapshot().primary_count == 0


# ---- 13. empty telemetry returns a safe zero snapshot ----
def test_empty_snapshot_is_safe():
    s = VoiceTelemetry().snapshot()
    assert s.total_events == 0 and s.selected_count == 0 and s.engine_failures == 0
    assert s.average_latency_ms == 0.0 and s.last_event_timestamp == ""
    assert dict(s.per_voice_counts) == {} and dict(s.per_engine_failures) == {}


# ---- 14. forbidden import scan ----
def test_no_forbidden_imports():
    src = _src()
    for forbidden in ("app.security", "app.capabilities", "app.agent", "app.memory",
                      "from app", "import app", "VoiceManager", "VoiceCapabilityGraph",
                      "EngineHealthCache", "PerformanceDirector", "voice_manager",
                      "voice_capability_graph", "engine_health", "performance_director"):
        assert forbidden not in src, f"telemetry.py must not reference {forbidden!r}"


# ---- 15. performance / high volume (functional; timing measured in the report) ----
def test_handles_high_volume():
    t = VoiceTelemetry()
    for i in range(1000):
        t.handle(_ev(VoiceEventType.VOICE_SELECTED, voice="nero_prime", engine="kokoro", latency_ms=float(i)))
    s = t.snapshot()
    assert s.primary_count == 1000 and s.total_events == 1000
    assert s.average_latency_ms == sum(range(1000)) / 1000    # exact, deterministic


# ---- end-to-end: real Manager fallback drives real telemetry ----
def test_end_to_end_real_manager_fallback():
    bus = VoiceEventBus()
    t = VoiceTelemetry(); t.attach(bus)
    mgr, _, (prime, luna) = _fallback_manager(telemetry=bus.manager_sink())
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna" and luna.calls == 1
    s = t.snapshot()
    assert s.fallback_count == 1 and s.engine_failures == 1
    assert s.per_voice_counts["nero_luna"] == 1 and s.per_engine_failures["e_prime"] == 1
    assert s.last_event_timestamp != ""              # a real bus-stamped timestamp


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-telemetry tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
