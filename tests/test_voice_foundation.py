"""Voice Platform tests — Stage 1: the TTSEngine contract (model-independent).

Verifies the interface in voice/local_tts/base.py with pure test doubles (no
engine bodies, no models, no GPU): the health-reporting envelope, the best-effort
failure paths, and that the Protocol is satisfiable. Later stages grow this file.

Run directly:  python tests/test_voice_foundation.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import (
    AudioResult, BaseTTSEngine, EngineHealth, EngineStatus,
    NullEngine, TTSEngine, VoiceRequest,
)


class StubEngine(BaseTTSEngine):
    """An available engine that returns fake audio — a model-free double."""
    name = "stub"
    _languages = ("en", "hr")
    _voices = ("nero_prime", "nero_luna")

    def _available(self) -> bool:
        return True

    def _synthesize(self, request: VoiceRequest):
        return (b"RIFF....fake-wav-bytes", 24_000)


class BrokenEngine(BaseTTSEngine):
    """Available, but its body raises — proves DEGRADED + contained failure."""
    name = "broken"

    def _available(self) -> bool:
        return True

    def _synthesize(self, request: VoiceRequest):
        raise RuntimeError("boom")


def test_null_engine_is_unavailable_and_fails_cleanly():
    e = NullEngine()
    assert e.available() is False
    assert e.health().status == EngineStatus.UNAVAILABLE
    r = e.synthesize(VoiceRequest(text="hello"))
    assert r.ok is False and r.audio == b"" and r.engine == "null"


def test_stub_engine_synthesizes_and_reports_ready():
    e = StubEngine()
    r = e.synthesize(VoiceRequest(text="Good evening, Toni.", voice_id="nero_prime"))
    assert r.ok and r.audio and r.sample_rate == 24_000
    assert r.engine == "stub" and r.voice_id == "nero_prime"
    assert r.duration_ms >= 0.0
    assert e.health().status == EngineStatus.READY
    assert e.languages() == ["en", "hr"] and "nero_luna" in e.voices()


def test_broken_engine_is_degraded_not_raising():
    e = BrokenEngine()
    r = e.synthesize(VoiceRequest(text="hi"))
    assert r.ok is False and "boom" in r.error       # contained, not raised
    assert e.health().status == EngineStatus.DEGRADED  # available but failing


def test_empty_request_is_a_clean_failure():
    e = StubEngine()
    assert e.synthesize(VoiceRequest(text="   ")).ok is False
    assert e.synthesize(VoiceRequest(text="")).ok is False


def test_protocol_is_satisfied_structurally():
    # Future code depends on the Protocol, not the concrete class (API-first).
    assert isinstance(StubEngine(), TTSEngine)
    assert isinstance(NullEngine(), TTSEngine)


def test_data_contracts_construct():
    req = VoiceRequest(text="x", voice_id="nero_prime", language="hr",
                       delivery={"authority": 0.9, "warmth": 0.2})
    assert req.delivery["authority"] == 0.9 and req.language == "hr"
    fail = AudioResult.failure("stub", "nope")
    assert fail.ok is False and fail.error == "nope"
    h = EngineHealth(status=EngineStatus.READY).as_dict()
    assert h["status"] == "ready"


def test_health_tracks_success_then_failure():
    e = StubEngine()
    e.synthesize(VoiceRequest(text="ok"))
    assert e.health().last_success and e.health().status == EngineStatus.READY


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-foundation tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
