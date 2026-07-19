"""Voice Platform tests — Stage 11: the Kokoro engine body (contract adapter).

Cloud-safe and model-independent: exercises the contract through FakeKokoroBackend,
proves the body plugs into the sealed foundation, and confirms it stays a simple
worker (no routing / no retries / no authority coupling). RealKokoroBackend is
checked only for import-safety + graceful not-ready — real audio / GPU / VRAM /
latency validation is reserved for the RTX-4070 (never claimed here).

Run directly:  python tests/test_kokoro_engine.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.engines.kokoro import (
    FakeKokoroBackend, KokoroBackend, KokoroEngine, RealKokoroBackend,
)
from voice.local_tts.base import AudioResult, EngineStatus, TTSEngine, VoiceRequest
from voice.local_tts.engine_health import EngineHealthCache
from voice.local_tts.voice_capability_graph import VoiceCapability, VoiceCapabilityGraph
from voice.manager.voice_manager import VoiceManager


def _src() -> str:
    return (Path(__file__).resolve().parent.parent / "voice" / "engines"
            / "kokoro.py").read_text(encoding="utf-8")


# ---- 1. available when the backend is ready ----
def test_available_when_backend_ready():
    eng = KokoroEngine(FakeKokoroBackend(ready=True))
    assert eng.available() is True
    r = eng.synthesize(VoiceRequest(text="Good evening, Toni.", voice_id="nero_prime"))
    assert eng.health().status == EngineStatus.READY and r.ok


# ---- 2. synthesis produces audio through the envelope ----
def test_synthesis_produces_audio():
    eng = KokoroEngine(FakeKokoroBackend(ready=True, audio=b"WAVDATA", sample_rate=24_000))
    r = eng.synthesize(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.audio == b"WAVDATA" and r.sample_rate == 24_000
    assert r.engine == "kokoro" and r.voice_id == "nero_prime"


# ---- 3. an unavailable backend is a clean failure ----
def test_unavailable_backend_is_clean_failure():
    eng = KokoroEngine(FakeKokoroBackend(ready=False))
    assert eng.available() is False
    r = eng.synthesize(VoiceRequest(text="hi"))
    assert isinstance(r, AudioResult) and r.ok is False       # never raises


# ---- 4. backend returning None is a clean failure ----
def test_backend_none_is_clean_failure():
    eng = KokoroEngine(FakeKokoroBackend(ready=True, audio=None))
    r = eng.synthesize(VoiceRequest(text="hi"))
    assert r.ok is False and "no audio" in r.error


# ---- 5. a backend exception is contained by the envelope ----
def test_backend_exception_is_contained():
    eng = KokoroEngine(FakeKokoroBackend(ready=True, raises=True))
    r = eng.synthesize(VoiceRequest(text="hi"))               # must not raise
    assert r.ok is False


# ---- 6. satisfies the TTSEngine Protocol (API-first) ----
def test_satisfies_tts_protocol():
    eng = KokoroEngine(FakeKokoroBackend())
    assert isinstance(eng, TTSEngine)


# ---- 7. metadata ----
def test_metadata():
    eng = KokoroEngine(FakeKokoroBackend(), languages=("en",), voices=("af_default",))
    assert eng.name == "kokoro" and eng.languages() == ["en"] and eng.voices() == ["af_default"]


# ---- 8. availability is cheap (never synthesizes) ----
def test_availability_is_cheap():
    backend = FakeKokoroBackend(ready=True)
    eng = KokoroEngine(backend)
    for _ in range(5):
        eng.available()
    assert backend.calls == 0                                 # available() never triggers synthesis


# ---- 9. synthesize is called exactly once (no hidden retries) ----
def test_synthesize_called_exactly_once():
    backend = FakeKokoroBackend(ready=True, audio=b"x")
    KokoroEngine(backend).synthesize(VoiceRequest(text="hi"))
    assert backend.calls == 1
    # even on a clean failure, still exactly once (retries belong elsewhere, if ever)
    failing = FakeKokoroBackend(ready=True, audio=None)
    KokoroEngine(failing).synthesize(VoiceRequest(text="hi"))
    assert failing.calls == 1


# ---- 10. contract isolation — the body cannot reach orchestration/authorities ----
def test_contract_isolation():
    src = _src()
    for forbidden in ("VoiceManager", "EngineHealthCache", "VoiceEventBus",
                      "VoiceTelemetry", "Startup", "VoiceRuntime"):
        assert forbidden not in src, f"the engine body must not reference {forbidden!r}"


# ---- 11. no forbidden coupling (orchestration modules / executive) ----
def test_no_forbidden_imports():
    src = _src()
    for forbidden in ("voice.manager", "voice_manager", "manager.startup", "engine_health",
                      "manager_sink", ".subscribe(", "record_success", "record_failure",
                      "app.security", "app.capabilities", "app.agent", "app.memory"):
        assert forbidden not in src, f"kokoro.py must not reference {forbidden!r}"


# ---- 12. RealKokoroBackend is import-safe and degrades gracefully (cloud) ----
def test_real_backend_import_safe_and_degrades():
    backend = RealKokoroBackend(cfg=None)                     # no Kokoro deps / model in cloud
    assert backend.is_ready() is False                        # not ready, no crash
    assert backend.synthesize("hello") is None                # graceful, never raises
    eng = KokoroEngine(backend)
    assert eng.available() is False
    assert eng.synthesize(VoiceRequest(text="hi")).ok is False


# ---- 13. crown jewel: the body plugs into the sealed foundation unchanged ----
def test_plugs_into_sealed_foundation():
    eng = KokoroEngine(FakeKokoroBackend(ready=True, audio=b"WAVDATA"))
    graph = VoiceCapabilityGraph()
    graph.register(VoiceCapability("nero_prime", "kokoro", ("en",)), eng)
    mgr = VoiceManager(graph, EngineHealthCache(), emergency_voice="nero_prime")
    r = mgr.speak(VoiceRequest(text="Good evening, Toni.", voice_id="nero_prime"))
    assert r.ok and r.engine == "kokoro" and r.audio == b"WAVDATA"
    assert r.outcome == "primary"                             # flows through Stages 2/4 unchanged


# ---- 14. KokoroBackend Protocol is satisfied by both backends ----
def test_backends_satisfy_protocol():
    assert isinstance(FakeKokoroBackend(), KokoroBackend)
    assert isinstance(RealKokoroBackend(cfg=None), KokoroBackend)


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} kokoro-engine tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
