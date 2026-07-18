"""Voice Platform tests — Stage 12: the MMS Croatian engine body + FIRST multi-engine
proof.

Cloud-safe / model-independent (fake backends): exercises the MMS body through the
sealed contract, then proves the whole point of the architecture — two engines
(Kokoro/en + MMS/hr) route purely by capability, fail honestly (never substitute a
language), and are observed distinctly by Telemetry and the Health Report — using the
UNCHANGED foundation. Real MMS/Croatian audio, model, VRAM, and latency are reserved
for the RTX-4070.

Run directly:  python tests/test_mms_engine.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.engines.kokoro import FakeKokoroBackend, KokoroEngine
from voice.engines.mms import (
    FakeMMSBackend, MMSBackend, MMSEngine, RealMMSBackend,
)
from voice.local_tts.base import AudioResult, EngineStatus, TTSEngine, VoiceRequest
from voice.local_tts.engine_health import EngineHealthCache, HealthStatus
from voice.local_tts.voice_capability_graph import VoiceCapability, VoiceCapabilityGraph
from voice.manager.events import VoiceEventBus, VoiceEventType
from voice.manager.health import build_health_report
from voice.manager.startup import build_voice_runtime
from voice.manager.telemetry import VoiceTelemetry
from voice.manager.voice_manager import OUTCOME_TEXT_ONLY, VoiceManager


def _src() -> str:
    return (Path(__file__).resolve().parent.parent / "voice" / "engines"
            / "mms.py").read_text(encoding="utf-8")


# ============================ MMS body (parallel to Kokoro) ============================

def test_available_and_synthesizes():
    eng = MMSEngine(FakeMMSBackend(ready=True, audio=b"HR-WAV", sample_rate=16_000))
    assert eng.available() is True
    r = eng.synthesize(VoiceRequest(text="Dobro jutro, Nero.", voice_id="nero_hr", language="hr"))
    assert r.ok and r.audio == b"HR-WAV" and r.sample_rate == 16_000 and r.engine == "mms_hr"
    assert eng.health().status == EngineStatus.READY


def test_unavailable_is_clean_failure():
    eng = MMSEngine(FakeMMSBackend(ready=False))
    assert eng.available() is False
    assert eng.synthesize(VoiceRequest(text="bok", language="hr")).ok is False


def test_none_and_exception_are_clean_failures():
    assert MMSEngine(FakeMMSBackend(ready=True, audio=None)).synthesize(
        VoiceRequest(text="x")).ok is False
    r = MMSEngine(FakeMMSBackend(ready=True, raises=True)).synthesize(VoiceRequest(text="x"))
    assert isinstance(r, AudioResult) and r.ok is False        # exception contained, never raised


def test_protocol_and_metadata():
    eng = MMSEngine(FakeMMSBackend(), voices=("hrv_speaker",))
    assert isinstance(eng, TTSEngine) and isinstance(FakeMMSBackend(), MMSBackend)
    assert eng.name == "mms_hr" and eng.languages() == ["hr"] and eng.voices() == ["hrv_speaker"]


def test_availability_cheap_and_synth_once():
    backend = FakeMMSBackend(ready=True, audio=b"x")
    eng = MMSEngine(backend)
    for _ in range(4):
        eng.available()
    assert backend.calls == 0                                  # availability never synthesizes
    eng.synthesize(VoiceRequest(text="x"))
    assert backend.calls == 1                                  # exactly once — no hidden retries


def test_real_backend_import_safe_and_degrades():
    backend = RealMMSBackend(cfg=None)                         # app.mms_tts absent in the cloud
    assert backend.is_ready() is False and backend.synthesize("bok") is None
    assert MMSEngine(backend).synthesize(VoiceRequest(text="bok", language="hr")).ok is False


def test_contract_isolation_and_no_language_branching():
    # Scan IMPORT/usage forms (not prose) — the docstring names the layers it must not
    # touch, which is good documentation, so we assert no actual coupling instead.
    src = _src()
    for forbidden in ("voice.manager", "from ..manager", "voice_manager", "engine_health",
                      "voice_capability_graph", "manager_sink", ".subscribe(",
                      "record_success", "record_failure",
                      "app.security", "app.capabilities", "app.agent", "app.memory"):
        assert forbidden not in src, f"mms.py must not couple to {forbidden!r}"
    # capability-only: the engine declares languages as data, it does not branch on them
    for branch in ('== "hr"', "if request.language", "if language ==", 'lang == "hr"'):
        assert branch not in src, f"mms.py must not branch on language ({branch!r})"


# ============================ FIRST multi-engine validation ============================

def _bilingual_graph(kokoro_up=True, mms_up=True):
    """nero_prime -> kokoro(en) ; nero_hr -> mms(hr). Returns (graph, health)."""
    g = VoiceCapabilityGraph()
    g.register(VoiceCapability("nero_prime", "kokoro", ("en",)),
               KokoroEngine(FakeKokoroBackend(ready=kokoro_up, audio=b"EN-WAV")))
    g.register(VoiceCapability("nero_hr", "mms_hr", ("hr",)),
               MMSEngine(FakeMMSBackend(ready=mms_up, audio=b"HR-WAV")))
    return g, EngineHealthCache()


# ---- routing by capability: hr -> mms, en -> kokoro (no special Croatian logic) ----
def test_capability_routing_selects_by_language():
    g, h = _bilingual_graph()
    mgr = VoiceManager(g, h, emergency_voice="nero_prime")
    en = mgr.speak(VoiceRequest(text="Good evening.", voice_id="nero_prime", language="en"))
    hr = mgr.speak(VoiceRequest(text="Dobra vecer.", voice_id="nero_hr", language="hr"))
    assert en.ok and en.engine == "kokoro" and en.audio == b"EN-WAV"
    assert hr.ok and hr.engine == "mms_hr" and hr.audio == b"HR-WAV"


# ---- honest failure: hr request, MMS down -> text_only, NEVER English (no smart fallback) ----
def test_hr_fails_honestly_when_mms_unavailable():
    g, h = _bilingual_graph(mms_up=False)
    mgr = VoiceManager(g, h, emergency_voice="nero_prime")
    r = mgr.speak(VoiceRequest(text="Dobro jutro", voice_id="nero_hr", language="hr"))
    assert r.ok is False and r.outcome == OUTCOME_TEXT_ONLY     # kokoro (en) is NOT substituted
    assert r.audio == b""


# ---- cross-engine fallback (same language, two engine bodies) ----
def test_cross_engine_fallback_same_language():
    # two en engine bodies: primary fails at synthesis -> fallback voice on the OTHER engine.
    g = VoiceCapabilityGraph()
    g.register(VoiceCapability("nero_prime", "kokoro", ("en",)),
               KokoroEngine(FakeKokoroBackend(ready=True, audio=None)))       # available but no audio
    g.register(VoiceCapability("nero_aux", "kokoro_aux", ("en",)),
               KokoroEngine(FakeKokoroBackend(ready=True, audio=b"AUX"), name="kokoro_aux"))
    mgr = VoiceManager(g, EngineHealthCache(), emergency_voice="nero_prime",
                       fallback_map={"nero_prime": ("nero_aux",)})
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime", language="en"))
    assert r.ok and r.engine == "kokoro_aux" and r.outcome == "fallback"      # fell across engine bodies


# ---- two-engine telemetry distinguishes engines ----
def test_two_engine_telemetry():
    g, h = _bilingual_graph(mms_up=False)
    bus = VoiceEventBus(); telem = VoiceTelemetry(); telem.attach(bus)
    mgr = VoiceManager(g, h, emergency_voice="nero_prime", telemetry=bus.manager_sink())
    mgr.speak(VoiceRequest(text="Good evening.", voice_id="nero_prime", language="en"))  # kokoro ok
    mgr.speak(VoiceRequest(text="Dobro jutro", voice_id="nero_hr", language="hr"))        # hr -> text_only
    snap = telem.snapshot()
    assert snap.primary_count == 1 and snap.text_only_count == 1
    assert snap.per_voice_counts.get("nero_prime") == 1


# ---- two-engine health report shows engine-specific state ----
def test_two_engine_health_report():
    g, h = _bilingual_graph(kokoro_up=True, mms_up=False)
    report = build_health_report(graph=g, engine_health=h, emergency_voice="nero_prime")
    assert report.engines["kokoro"].should_attempt is True
    assert "nero_prime" in report.available_voices and "nero_hr" not in report.available_voices
    assert report.emergency_available is True                  # kokoro/en emergency is up


# ---- end-to-end bilingual via a composed Stage-9 runtime ----
def test_end_to_end_bilingual_runtime():
    cast = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"]},
        {"voice_id": "nero_hr", "engine": "mms_hr", "languages": ["hr"]}]}
    fd, path = tempfile.mkstemp(suffix=".json", prefix="nero_bi_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(cast))
    try:
        rt = build_voice_runtime(engines={
            "kokoro": KokoroEngine(FakeKokoroBackend(ready=True, audio=b"EN")),
            "mms_hr": MMSEngine(FakeMMSBackend(ready=True, audio=b"HR")),
        }, cast_path=path)
    finally:
        os.remove(path)
    en = rt.manager.speak(VoiceRequest(text="Good evening.", voice_id="nero_prime", language="en"))
    hr = rt.manager.speak(VoiceRequest(text="Dobra vecer.", voice_id="nero_hr", language="hr"))
    assert en.ok and en.engine == "kokoro" and hr.ok and hr.engine == "mms_hr"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} mms-engine + multi-engine tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
