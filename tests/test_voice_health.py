"""Voice Platform tests — Stage 10: Voice Health Check (stateless read-only interpreter).

Proves the Health Report composes three lenses (Graph availability · Engine Health
attempt-gating · Telemetry execution) into an immutable picture, with a pure advisory
rollup — while owning nothing: it mutates no health, influences no routing, keeps no
state, and imports no voice module. The crown-jewel test builds a Stage 9 runtime,
drives a fallback, and confirms the report *sees everything and changes nothing*.

Model-independent (test-double engines), deterministic (injected clocks), no GPU.

Run directly:  python tests/test_voice_health.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import BaseTTSEngine, VoiceRequest
from voice.local_tts.engine_health import EngineHealthCache, HealthStatus
from voice.local_tts.voice_capability_graph import VoiceCapability, VoiceCapabilityGraph
from voice.manager.events import VoiceEvent, VoiceEventType
from voice.manager.health import (
    EngineHealthView, RecentExecution, VoiceHealthLevel, VoiceHealthReport,
    build_health_report, report_for_runtime,
)
from voice.manager.startup import build_voice_runtime
from voice.manager.telemetry import VoiceTelemetry

_FIXED = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


def _src() -> str:
    return (Path(__file__).resolve().parent.parent / "voice" / "manager"
            / "health.py").read_text(encoding="utf-8")


# ---- test-double engines ----
class OkEngine(BaseTTSEngine):
    def __init__(self, name, langs=("en",)):
        super().__init__(); self.name = name; self._languages = tuple(langs)

    def _available(self): return True

    def _synthesize(self, request): return (b"wav", 24_000)


class FailEngine(BaseTTSEngine):
    def __init__(self, name):
        super().__init__(); self.name = name; self._languages = ("en",)

    def _available(self): return True

    def _synthesize(self, request): return (b"", 0)


class ToggleEngine(BaseTTSEngine):
    def __init__(self, name, up=True):
        super().__init__(); self.name = name; self._languages = ("en",); self.up = up

    def _available(self): return self.up

    def _synthesize(self, request): return (b"wav", 24_000)


def _graph(voices):
    """voices: list of (voice_id, engine)."""
    g = VoiceCapabilityGraph()
    for vid, eng in voices:
        g.register(VoiceCapability(vid, eng.name, tuple(eng.languages())), eng)
    return g


def _report(voices, health=None, telemetry=None, emergency="nero_prime", now=None):
    return build_health_report(graph=_graph(voices), engine_health=health or EngineHealthCache(),
                               emergency_voice=emergency, telemetry=telemetry,
                               now=now, clock=lambda: _FIXED)


# ---- 1. three-lens composition ----
def test_three_lens_composition():
    t = VoiceTelemetry()
    r = _report([("nero_prime", OkEngine("kokoro"))], telemetry=t)
    assert isinstance(r, VoiceHealthReport)
    assert isinstance(r.available_voices, tuple)       # availability lens
    assert isinstance(r.engines, MappingProxyType)     # attempt-health lens
    assert r.recent is not None                        # execution lens present with telemetry
    assert r.overall in VoiceHealthLevel


# ---- 2. graph availability reporting ----
def test_availability_lens():
    r = _report([("nero_prime", OkEngine("kokoro")), ("nero_luna", ToggleEngine("d", up=False))])
    assert r.available_voices == ("nero_prime",) and r.total_voices == 2
    assert r.emergency_available is True


# ---- 3. engine cooldown visibility (the two-lens distinction) ----
def test_engine_cooldown_visibility():
    h = EngineHealthCache(base_cooldown_s=5.0)
    h.record_failure("kokoro", "boom", now=_FIXED)              # engine now cooling down
    r = build_health_report(graph=_graph([("nero_prime", OkEngine("kokoro"))]),
                            engine_health=h, emergency_voice="nero_prime",
                            now=_FIXED + timedelta(seconds=1), clock=lambda: _FIXED)
    view = r.engines["kokoro"]
    assert view.status == "cooldown" and view.should_attempt is False and view.consecutive_failures == 1
    assert "kokoro" in r.gated_engines
    assert r.available_voices == ("nero_prime",)               # engine is UP (can perform) ...
    assert r.overall == VoiceHealthLevel.DEGRADED              # ... but gated -> DEGRADED


# ---- 4. telemetry reflection ----
def test_telemetry_reflection():
    t = VoiceTelemetry()
    t.handle(VoiceEvent(type=VoiceEventType.ENGINE_FAILED, payload={"engine": "kokoro"}))
    t.handle(VoiceEvent(type=VoiceEventType.FALLBACK_USED,
                        payload={"voice": "nero_luna", "engine": "e_luna", "latency_ms": 10.0}))
    r = _report([("nero_prime", OkEngine("kokoro"))], telemetry=t)
    assert isinstance(r.recent, RecentExecution)
    assert r.recent.engine_failures == 1 and r.recent.fallback_count == 1
    assert r.recent.per_engine_failures["kokoro"] == 1
    assert r.overall == VoiceHealthLevel.DEGRADED             # recent failures > 0


# ---- 5. immutable report ----
def test_report_is_immutable():
    r = _report([("nero_prime", OkEngine("kokoro"))])
    for mutate in (lambda: setattr(r, "overall", None),
                   lambda: r.engines.__setitem__("x", 1),
                   lambda: setattr(r.engines["kokoro"], "should_attempt", False)):
        try:
            mutate(); raised = False
        except (Exception,):
            raised = True
        assert raised
    assert isinstance(r.engines["kokoro"], EngineHealthView)


# ---- 6. no Engine Health mutation ----
def test_no_engine_health_mutation():
    h = EngineHealthCache()
    build_health_report(graph=_graph([("nero_prime", OkEngine("kokoro"))]),
                        engine_health=h, emergency_voice="nero_prime", clock=lambda: _FIXED)
    assert h.get("kokoro") is None                            # report created no records
    assert h.status("kokoro") == HealthStatus.UNKNOWN
    src = _src()
    for m in ("record_success", "record_failure", "record_repair"):
        assert m not in src, f"health.py must not call {m}()"


# ---- 7. no routing influence ----
def test_no_routing_influence():
    src = _src()
    for forbidden in ("voice_manager", "import startup", "from .startup", "manager_sink",
                      ".speak(", ".subscribe("):
        assert forbidden not in src, f"health.py must not reference {forbidden!r}"
    r = _report([("nero_prime", OkEngine("kokoro"))])
    assert not hasattr(r, "voice_id")                        # a report, not a routing decision


# ---- 8. telemetry optional ----
def test_telemetry_optional():
    r = _report([("nero_prime", OkEngine("kokoro"))], telemetry=None)
    assert r.recent is None and r.overall == VoiceHealthLevel.HEALTHY


# ---- 9. deterministic injected clock ----
def test_deterministic_clock():
    a = _report([("nero_prime", OkEngine("kokoro"))])
    b = _report([("nero_prime", OkEngine("kokoro"))])
    assert a.checked_at == _FIXED.isoformat() and a.as_dict() == b.as_dict()


# ---- 10. live state reflection ----
def test_live_state_reflection():
    eng = ToggleEngine("kokoro", up=True)
    g = _graph([("nero_prime", eng)])
    r1 = build_health_report(graph=g, engine_health=EngineHealthCache(),
                             emergency_voice="nero_prime", clock=lambda: _FIXED)
    assert r1.available_voices == ("nero_prime",) and r1.overall == VoiceHealthLevel.HEALTHY
    eng.up = False
    r2 = build_health_report(graph=g, engine_health=EngineHealthCache(),
                             emergency_voice="nero_prime", clock=lambda: _FIXED)
    assert r2.available_voices == () and r2.overall == VoiceHealthLevel.OFFLINE


# ---- 11. rollup rules (exact) ----
def test_rollup_rules():
    assert _report([("nero_prime", OkEngine("k"))]).overall == VoiceHealthLevel.HEALTHY
    assert _report([("nero_prime", ToggleEngine("d", up=False))]).overall == VoiceHealthLevel.OFFLINE
    degraded = _report([("nero_prime", ToggleEngine("d1", up=False)), ("nero_luna", OkEngine("u1"))])
    assert degraded.overall == VoiceHealthLevel.DEGRADED and degraded.emergency_available is False


# ---- 12. forbidden imports ----
def test_forbidden_imports():
    src = _src()
    for forbidden in ("app.security", "app.capabilities", "app.agent", "app.memory",
                      "from app", "import app", "ollama", "action_journal"):
        assert forbidden not in src, f"health.py must not reference {forbidden!r}"


# ---- 13. crown jewel: Stage 9 runtime integration (sees everything, changes nothing) ----
def test_end_to_end_runtime_integration():
    fb = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "e_prime", "languages": ["en"], "fallbacks": ["nero_luna"]},
        {"voice_id": "nero_luna", "engine": "e_luna", "languages": ["en"]}]}
    fd, path = tempfile.mkstemp(suffix=".json", prefix="nero_hc_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(fb))
    try:
        rt = build_voice_runtime(engines={"e_prime": FailEngine("e_prime"), "e_luna": OkEngine("e_luna")},
                                 cast_path=path, clock=lambda: _FIXED)
    finally:
        os.remove(path)

    r = rt.manager.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna"                 # Manager fell back (its decision, not the report's)

    report = report_for_runtime(rt, clock=lambda: _FIXED)
    # availability: both engines report available() True -> both voices can perform
    assert "nero_prime" in report.available_voices and "nero_luna" in report.available_voices
    # engine health: e_prime failed during speak -> cooldown visible (recorded by the Manager)
    assert report.engines["e_prime"].consecutive_failures == 1 and report.engines["e_prime"].should_attempt is False
    assert "e_prime" in report.gated_engines
    # telemetry: the failure + fallback were observed
    assert report.recent.engine_failures == 1 and report.recent.fallback_count == 1

    # ... and the report changed nothing: re-reporting does not alter health history.
    before = rt.health.get("e_prime").consecutive_failures
    report_for_runtime(rt, clock=lambda: _FIXED)
    assert rt.health.get("e_prime").consecutive_failures == before


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-health tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
