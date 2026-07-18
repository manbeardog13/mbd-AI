"""Voice Platform tests — Stage 9: Warm Startup / Voice Runtime Initialization.

Proves the composition root wires the sealed Stages 1–8 bricks together
deterministically and reports readiness WITHOUT owning routing, health, or recovery:
composition + wiring, loud/safe composition failures, the READY/DEGRADED/OFFLINE
readiness model (live-probed), no health mutation, runtime independence, and the
crown-jewel end-to-end fallback flow through a fully composed runtime.

Model-independent (test-double engines only), deterministic, no GPU.

Run directly:  python tests/test_voice_startup.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import BaseTTSEngine, VoiceRequest
from voice.local_tts.engine_health import HealthStatus
from voice.manager.events import VoiceEventType
from voice.manager.startup import (
    ReadinessState, StartupError, VoiceReadiness, VoiceRuntime, build_voice_runtime,
)
from voice.profiles.loader import Cast

_FIXED = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


def _src() -> str:
    return (Path(__file__).resolve().parent.parent / "voice" / "manager"
            / "startup.py").read_text(encoding="utf-8")


def _cast_file(data) -> str:
    fd, path = tempfile.mkstemp(suffix=".json", prefix="nero_rt_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))
    return path


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


class ToggleEngine(BaseTTSEngine):
    """Available flag flips at runtime — proves readiness is live, not cached."""

    def __init__(self, name, langs=("en",), up=True):
        super().__init__(); self.name = name; self._languages = tuple(langs); self.up = up

    def _available(self): return self.up

    def _synthesize(self, request): return (b"wav", 24_000)


_SIMPLE = {"emergency": "nero_prime",
           "voices": [{"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"]}]}
_FALLBACK = {"emergency": "nero_prime", "voices": [
    {"voice_id": "nero_prime", "engine": "e_prime", "languages": ["en"], "fallbacks": ["nero_luna"]},
    {"voice_id": "nero_luna", "engine": "e_luna", "languages": ["en"]},
]}


def _build(data, engines, **kw):
    path = _cast_file(data)
    try:
        return build_voice_runtime(engines=engines, cast_path=path, clock=lambda: _FIXED, **kw)
    finally:
        os.remove(path)


def _expect_startup_error(data, engines) -> str:
    path = _cast_file(data)
    try:
        build_voice_runtime(engines=engines, cast_path=path)
    except StartupError as exc:
        return str(exc)
    finally:
        os.remove(path)
    raise AssertionError("expected StartupError")


# ---- 1. composition wires everything ----
def test_composition_wires_everything():
    rt = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")})
    assert isinstance(rt, VoiceRuntime)
    assert rt.manager is not None and rt.bus is not None and rt.telemetry is not None
    assert rt.graph is not None and rt.health is not None and isinstance(rt.cast, Cast)


# ---- 2. missing cast -> StartupError, no partial runtime ----
def test_missing_cast_raises_startup_error():
    try:
        build_voice_runtime(engines={}, cast_path="/no/such/nero_rt_missing.json")
    except StartupError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("expected StartupError for a missing manifest")


# ---- 3. missing engine binding -> StartupError ----
def test_missing_engine_binding_raises():
    data = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"]},
        {"voice_id": "nero_luna", "engine": "mms_hr", "languages": ["en"]}]}
    assert "mms_hr" in _expect_startup_error(data, {"kokoro": OkEngine("kokoro")})


# ---- 4. language mismatch -> StartupError ----
def test_language_mismatch_raises():
    data = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"]},
        {"voice_id": "nero_luna", "engine": "kokoro", "languages": ["hr"]}]}
    msg = _expect_startup_error(data, {"kokoro": OkEngine("kokoro", ("en",))})
    assert "nero_luna" in msg and "hr" in msg


# ---- 5. graph populated ----
def test_graph_is_populated():
    rt = _build(_FALLBACK, {"e_prime": OkEngine("e_prime"), "e_luna": OkEngine("e_luna")})
    assert set(rt.graph.voices()) == {"nero_prime", "nero_luna"}


# ---- 6. event bus wiring ----
def test_event_bus_is_wired_through_manager():
    rt = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")})
    observed = []
    rt.bus.subscribe(observed.append)
    rt.manager.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert any(e.type == VoiceEventType.VOICE_SELECTED for e in observed)


# ---- 7. telemetry attachment ----
def test_telemetry_is_attached():
    rt = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")})
    rt.manager.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert rt.telemetry.snapshot().primary_count == 1


# ---- 8. readiness states ----
def test_readiness_states():
    ready = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")}).readiness()
    assert ready.state == ReadinessState.READY and ready.emergency_available

    degraded = _build(_FALLBACK, {"e_prime": ToggleEngine("e_prime", up=False),
                                  "e_luna": OkEngine("e_luna")}).readiness()
    assert degraded.state == ReadinessState.DEGRADED and degraded.available_voices == ("nero_luna",)

    offline = _build(_FALLBACK, {"e_prime": ToggleEngine("e_prime", up=False),
                                 "e_luna": ToggleEngine("e_luna", up=False)}).readiness()
    assert offline.state == ReadinessState.OFFLINE and offline.available_voices == ()


# ---- 9. readiness is live (re-probed, not cached) ----
def test_readiness_is_live():
    eng = ToggleEngine("kokoro", up=True)
    rt = _build(_SIMPLE, {"kokoro": eng})
    assert rt.readiness().state == ReadinessState.READY
    eng.up = False
    assert rt.readiness().state == ReadinessState.OFFLINE     # live probe reflects the change


# ---- 10. startup does not mutate health ----
def test_startup_does_not_mutate_health():
    rt = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")})
    assert rt.health.get("kokoro") is None                     # no records created at boot
    assert rt.health.status("kokoro") == HealthStatus.UNKNOWN
    src = _src()
    for mutate in ("record_success", "record_failure", "record_repair"):
        assert mutate not in src, f"startup must not call {mutate}() (no health mutation)"


# ---- 11. deterministic composition ----
def test_deterministic_composition():
    a = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")}).readiness()
    b = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")}).readiness()
    assert a.as_dict() == b.as_dict()


# ---- 12. runtimes are independent (no singleton state) ----
def test_runtimes_are_independent():
    rt1 = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")})
    rt2 = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")})
    rt1.manager.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert rt1.telemetry.snapshot().total_events >= 1
    assert rt2.telemetry.snapshot().total_events == 0          # rt2 untouched
    assert rt1.health is not rt2.health and rt1.bus is not rt2.bus


# ---- 13. no Manager modification (composer, not mutator) ----
def test_no_manager_modification():
    src = _src()
    assert "(VoiceManager)" not in src                         # startup does not subclass the Manager
    assert ".speak =" not in src and ".speak=" not in src      # no monkeypatch of routing
    assert "manager._" not in src                              # no reach into Manager internals


# ---- 14. no forbidden coupling (executive / LLM / memory) ----
def test_no_forbidden_imports():
    src = _src()
    for forbidden in ("app.security", "app.capabilities", "app.agent", "app.memory",
                      "from app", "import app", "ollama", "action_journal", "journal"):
        assert forbidden not in src, f"startup.py must not reference {forbidden!r}"


# ---- 15. telemetry is optional; the bus is always the seam ----
def test_telemetry_optional():
    rt = _build(_SIMPLE, {"kokoro": OkEngine("kokoro")}, enable_telemetry=False)
    assert rt.telemetry is None
    observed = []
    rt.bus.subscribe(observed.append)
    rt.manager.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert len(observed) >= 1                                  # bus wired even without a collector


# ---- 16. crown jewel: end-to-end fallback through a composed runtime ----
def test_end_to_end_fallback_through_runtime():
    rt = _build(_FALLBACK, {"e_prime": FailEngine("e_prime"), "e_luna": OkEngine("e_luna")})
    observed = []
    rt.bus.subscribe(observed.append)
    r = rt.manager.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna" and r.outcome == "fallback"     # routing intact
    snap = rt.telemetry.snapshot()
    assert snap.fallback_count == 1 and snap.engine_failures == 1             # telemetry recorded
    kinds = [e.type for e in observed]
    assert VoiceEventType.ENGINE_FAILED in kinds and VoiceEventType.FALLBACK_USED in kinds
    assert rt.health.get("e_prime").consecutive_failures == 1                 # real health, untouched by observers


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-startup tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
