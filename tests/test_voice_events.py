"""Voice Platform tests — Stage 7: the Voice Event Bus (observational only).

Proves the bus is a small, synchronous, deterministic observation pipe that wraps
the Voice Manager's existing telemetry seam WITHOUT changing routing: events are
immutable facts, subscribers are isolated and cannot influence routing, unknown
telemetry is ignored, and a real VoiceManager drives real lifecycle events through
`bus.manager_sink()`. Injected clock -> no real-time dependency.

Run directly:  python tests/test_voice_events.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import BaseTTSEngine, VoiceRequest
from voice.local_tts.engine_health import EngineHealthCache
from voice.local_tts.voice_capability_graph import VoiceCapability, VoiceCapabilityGraph
from voice.manager.events import (
    SCHEMA_VERSION, VoiceEvent, VoiceEventBus, VoiceEventType, from_manager_event,
)
from voice.manager.voice_manager import VoiceManager

_FIXED = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


def _bus():
    return VoiceEventBus(clock=lambda: _FIXED)      # deterministic timestamps


def _src() -> str:
    return (Path(__file__).resolve().parent.parent / "voice" / "manager"
            / "events.py").read_text(encoding="utf-8")


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


# ---- 1. single subscriber receives events ----
def test_single_subscriber_receives_event():
    bus = _bus()
    got = []
    bus.subscribe(got.append)
    bus.emit(VoiceEvent(type=VoiceEventType.VOICE_SELECTED, payload={"voice": "nero_prime"}))
    assert len(got) == 1 and got[0].type == VoiceEventType.VOICE_SELECTED
    assert got[0].payload["voice"] == "nero_prime" and got[0].timestamp == _FIXED.isoformat()


# ---- 2. multiple subscribers receive events in subscription order ----
def test_multiple_subscribers_in_order():
    bus = _bus()
    order = []
    bus.subscribe(lambda e: order.append("a"))
    bus.subscribe(lambda e: order.append("b"))
    bus.subscribe(lambda e: order.append("c"))
    bus.emit(VoiceEvent(type=VoiceEventType.ENGINE_FAILED))
    assert order == ["a", "b", "c"]             # subscription order preserved


# ---- 3. subscriber failure isolation ----
def test_subscriber_failure_is_isolated():
    bus = _bus()
    seen = []
    def boom(_): raise RuntimeError("bad subscriber")
    bus.subscribe(boom)
    bus.subscribe(seen.append)
    bus.emit(VoiceEvent(type=VoiceEventType.TEXT_ONLY_RESULT))     # must not raise
    assert len(seen) == 1                       # the healthy subscriber still got it


# ---- 4. payload immutability ----
def test_payload_is_read_only():
    bus = _bus()
    got = []
    bus.subscribe(got.append)
    bus.emit(VoiceEvent(type=VoiceEventType.VOICE_SELECTED, payload={"engine": "kokoro"}))
    assert isinstance(got[0].payload, MappingProxyType)
    try:
        got[0].payload["engine"] = "hacked"     # read-only -> must raise
        raised = False
    except TypeError:
        raised = True
    assert raised


# ---- 5. event immutability ----
def test_event_is_immutable():
    ev = VoiceEvent(type=VoiceEventType.ENGINE_COOLDOWN)
    try:
        ev.type = VoiceEventType.VOICE_SELECTED  # frozen -> must raise
        raised = False
    except Exception:
        raised = True
    assert raised and ev.schema_version == SCHEMA_VERSION


# ---- 6. sequence ordering ----
def test_sequence_is_monotonic_and_ordered():
    bus = _bus()
    got = []
    bus.subscribe(got.append)
    for _ in range(3):
        bus.emit(VoiceEvent(type=VoiceEventType.ENGINE_FAILED))
    assert [e.sequence for e in got] == [0, 1, 2]


# ---- 7. injectable timestamps (no real-time dependency) ----
def test_injectable_clock():
    stamp = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    bus = VoiceEventBus(clock=lambda: stamp)
    got = []
    bus.subscribe(got.append)
    bus.emit(VoiceEvent(type=VoiceEventType.VOICE_SELECTED))
    assert got[0].timestamp == stamp.isoformat()


# ---- 8. unsubscribe works ----
def test_unsubscribe_stops_delivery():
    bus = _bus()
    got = []
    handle = bus.subscribe(got.append)
    bus.emit(VoiceEvent(type=VoiceEventType.VOICE_SELECTED))
    handle()                                     # detach via returned handle
    bus.emit(VoiceEvent(type=VoiceEventType.VOICE_SELECTED))
    assert len(got) == 1
    bus.unsubscribe(got.append)                  # idempotent: removing absent cb is safe


# ---- 9. mapping: known telemetry -> correct types; unknown -> ignored ----
def test_from_manager_event_mapping():
    m = from_manager_event
    assert m({"event": "selected", "outcome": "primary"}).type == VoiceEventType.VOICE_SELECTED
    assert m({"event": "selected", "outcome": "fallback"}).type == VoiceEventType.FALLBACK_USED
    assert m({"event": "engine_failed", "error": "boom"}).type == VoiceEventType.ENGINE_FAILED
    assert m({"event": "skip", "reason": "cooldown"}).type == VoiceEventType.ENGINE_COOLDOWN
    assert m({"event": "skip", "reason": "language"}).type == VoiceEventType.VOICE_SKIPPED
    assert m({"event": "skip", "reason": "unavailable"}).type == VoiceEventType.VOICE_SKIPPED
    assert m({"event": "text_only", "requested": "nero_prime"}).type == VoiceEventType.TEXT_ONLY_RESULT
    # unknowns are ignored, never crash
    assert m({"event": "mystery"}) is None
    assert m({"event": "skip", "reason": "unknown"}) is None
    assert m("not a dict") is None and m({}) is None
    # the 'event' key is stripped from the payload
    assert "event" not in m({"event": "engine_failed", "error": "x"}).payload


# ---- 10. zero subscribers behave identically (no-op, near-zero overhead) ----
def test_zero_subscribers_is_safe_noop():
    bus = _bus()
    bus.emit(VoiceEvent(type=VoiceEventType.VOICE_SELECTED))     # must not raise
    # a Manager wired to a subscriber-less bus behaves exactly like no telemetry
    mgr, _, _ = _fallback_manager(telemetry=bus.manager_sink())
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna"    # identical routing outcome


# ---- 11. no forbidden app imports ----
def test_no_forbidden_imports():
    src = _src()
    for forbidden in ("app.security", "app.capabilities", "app.agent",
                      "app.memory", "from app", "import app"):
        assert forbidden not in src, f"events.py must not reference {forbidden!r}"


# ---- 12. no dependency into Manager / Graph / Health / Director (one-way) ----
def test_no_circular_dependency():
    src = _src()
    for forbidden in ("VoiceManager", "VoiceCapabilityGraph", "EngineHealthCache",
                      "PerformanceDirector", "voice_manager", "voice_capability_graph",
                      "engine_health", "performance_director"):
        assert forbidden not in src, f"events.py must not depend on {forbidden!r} (one-way)"


# ---- 13. end-to-end: real Manager fallback drives real events, in order ----
def test_end_to_end_real_manager_fallback():
    bus = _bus()
    events = []
    bus.subscribe(events.append)
    mgr, health, (prime, luna) = _fallback_manager(telemetry=bus.manager_sink())
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna" and luna.calls == 1     # fallback still works
    types = [e.type for e in events]
    assert VoiceEventType.ENGINE_FAILED in types
    # order: prime's engine failed BEFORE the fallback voice was selected
    assert types.index(VoiceEventType.ENGINE_FAILED) < types.index(VoiceEventType.FALLBACK_USED)


# ---- 14. observers cannot influence routing ----
def test_observers_cannot_influence_routing():
    bus = _bus()
    def saboteur(event):
        try:
            event.payload["engine"] = "hijacked"    # read-only -> raises, isolated
        except TypeError:
            pass
        raise RuntimeError("observer tries to break things")
    bus.subscribe(saboteur)
    mgr, health, (prime, luna) = _fallback_manager(telemetry=bus.manager_sink())
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna"        # routing unaffected by the observer
    assert health.get("e_prime").consecutive_failures == 1   # real health, not "hijacked"
    assert health.get("e_luna").state.value == "available"   # luna's engine recorded success


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-events tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
