"""Voice Platform tests — Stage 13: Voice Rendering Profile (casting + engine honoring).

13a — the casting layer: RenderingProfile + loader + the pure VoiceCasting mapper
(deterministic feeling→rendering, foundation and engines untouched).
13b — engine honoring: engines read the RenderingProfile and map the abstract
voice_character to a native voice (fake backends record the params to prove the
plumbing). Real audible distinctness is measured on the RTX-4070.

Model-independent, deterministic, no GPU.  Run:  python tests/test_voice_rendering.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.engines.kokoro import FakeKokoroBackend, KokoroEngine
from voice.engines.mms import FakeMMSBackend, MMSEngine
from voice.local_tts.base import VoiceRequest
from voice.local_tts.engine_health import EngineHealthCache
from voice.local_tts.voice_capability_graph import VoiceCapability, VoiceCapabilityGraph
from voice.manager.voice_manager import VoiceManager
from voice.personalities.performance_director import PerformanceDirector
from voice.rendering.casting import VoiceCasting
from voice.rendering.profile import (
    DEFAULT_PROFILES_PATH, RenderingError, RenderingProfile, RenderingProfiles,
)


def _rendering_src() -> str:
    base = Path(__file__).resolve().parent.parent / "voice" / "rendering"
    return (base / "casting.py").read_text(encoding="utf-8") + (base / "profile.py").read_text(encoding="utf-8")


def _profiles_file(data) -> str:
    fd, path = tempfile.mkstemp(suffix=".json", prefix="nero_rp_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))
    return path


def _casting(profiles_dict=None):
    if profiles_dict is None:
        return VoiceCasting(RenderingProfiles.load())
    path = _profiles_file({"profiles": profiles_dict})
    try:
        return VoiceCasting(RenderingProfiles.load(path))
    finally:
        os.remove(path)


# =============================== 13a: casting layer ===============================

def test_rendering_profile_defaults_and_serialization():
    p = RenderingProfile()
    d = p.as_dict()
    assert set(d) == {"voice_character", "speed", "pitch", "energy", "pause_style", "schema_version"}
    assert d["voice_character"] == "neutral" and d["speed"] == 1.0 and d["pause_style"] == "natural"


def test_shipped_profiles_load_all_personas():
    profs = RenderingProfiles.load(DEFAULT_PROFILES_PATH)
    assert len(profs.voices()) == 10 and "nero_commander" in profs.voices()
    assert profs.get("nero_commander").voice_character == "authoritative"


def test_unknown_voice_id_returns_default_no_crash():
    assert RenderingProfiles.load().get("ghost").voice_character == "neutral"


def test_mapper_is_deterministic():
    c = _casting()
    a = c.cast("nero_prime", {"pace": 0.85, "intensity": 0.8})
    b = c.cast("nero_prime", {"pace": 0.85, "intensity": 0.8})
    assert a.as_dict() == b.as_dict()


def test_personas_are_distinct():
    c = _casting()
    cmd, luna = c.cast("nero_commander"), c.cast("nero_luna")
    assert cmd.voice_character != luna.voice_character and cmd.speed != luna.speed


def test_delivery_plan_modulates_speed_and_energy():
    c = _casting()
    slow = c.cast("nero_prime", {"pace": 0.85})
    fast = c.cast("nero_prime", {"pace": 1.0})
    assert slow.speed < fast.speed                       # pace scales the baseline
    hot = c.cast("nero_prime", {"intensity": 1.0})
    cool = c.cast("nero_prime", {"intensity": 0.0})
    assert hot.energy > cool.energy                      # intensity blends into energy


def test_malformed_profiles_fail_loud():
    bad_json = _profiles_file("{ not json ")
    try:
        RenderingProfiles.load(bad_json)
    except RenderingError as exc:
        assert "not valid JSON" in str(exc)
    else:
        raise AssertionError("expected RenderingError")
    finally:
        os.remove(bad_json)
    # bad field types / values
    for bad in ({"nero_x": {"speed": "fast"}}, {"nero_x": {"pause_style": "weird"}},
                {"nero_x": {"voice_character": ""}}):
        p = _profiles_file({"profiles": bad})
        try:
            RenderingProfiles.load(p)
            raised = False
        except RenderingError:
            raised = True
        finally:
            os.remove(p)
        assert raised, f"expected RenderingError for {bad!r}"
    # missing file
    try:
        RenderingProfiles.load("/no/such/nero_rp.json")
    except RenderingError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("expected RenderingError for a missing file")


def test_no_engine_native_leak_in_rendering():
    src = _rendering_src()
    shipped = DEFAULT_PROFILES_PATH.read_text(encoding="utf-8")
    for native in ("af_", "am_", "kokoro", "mms", "hrv"):
        assert native not in shipped, f"profiles.json must not name an engine voice ({native!r})"
        assert native not in src, f"rendering layer must not name an engine voice ({native!r})"


def test_no_semantic_leak_after_casting():
    c = _casting()
    req = VoiceRequest(text="hi", voice_id="nero_commander",
                       delivery={"emotion": "serious", "authority": 0.9, "intensity": 0.8, "pace": 1.0})
    out = c.cast_request(req)
    assert "voice_character" in out.delivery and "speed" in out.delivery
    for semantic in ("emotion", "authority", "warmth", "humor"):
        assert semantic not in out.delivery              # DeliveryPlan consumed, not forwarded


def test_casting_is_pure_and_uncoupled():
    src = _rendering_src()
    for forbidden in ("voice_manager", "VoiceManager", "voice_capability_graph", "engine_health",
                      "manager.startup", "manager.telemetry", "manager.health", "manager.events",
                      "import random", "random.", "ollama", "open(", "app.security"):
        assert forbidden not in src, f"rendering layer must not use {forbidden!r}"


def test_cast_request_preserves_identity_fields_and_input():
    c = _casting()
    req = VoiceRequest(text="Dobra vecer", voice_id="nero_luna", language="hr", speed=1.2, delivery={})
    out = c.cast_request(req)
    assert out.text == "Dobra vecer" and out.voice_id == "nero_luna" and out.language == "hr" and out.speed == 1.2
    assert out is not req and req.delivery == {}          # input untouched


# =============================== 13b: engine honoring ===============================

def test_kokoro_maps_character_to_native_voice_and_speed():
    backend = FakeKokoroBackend(ready=True, audio=b"WAV")
    eng = KokoroEngine(backend)
    profile = _casting().cast("nero_commander")           # authoritative
    req = VoiceRequest(text="hi", voice_id="nero_commander", delivery=profile.as_dict())
    r = eng.synthesize(req)
    assert r.ok and backend.last_voice == "am_michael"    # abstract 'authoritative' -> native voice
    assert backend.last_speed == profile.speed            # rendering speed reached the backend


def test_mms_maps_and_records_rendering():
    backend = FakeMMSBackend(ready=True, audio=b"HR")
    eng = MMSEngine(backend)
    profile = _casting().cast("nero_luna")
    r = eng.synthesize(VoiceRequest(text="bok", voice_id="nero_luna", delivery=profile.as_dict()))
    assert r.ok and backend.last_voice == "hrv"           # MMS single-speaker default
    assert backend.last_speed == profile.speed


def test_unknown_character_falls_back_to_default_voice():
    backend = FakeKokoroBackend(ready=True, audio=b"WAV")
    KokoroEngine(backend).synthesize(
        VoiceRequest(text="hi", delivery={"voice_character": "made_up", "speed": 1.0}))
    assert backend.last_voice == "af_heart"               # honest default, never a crash


def test_backward_compatible_without_rendering():
    backend = FakeKokoroBackend(ready=True, audio=b"WAV")
    r = KokoroEngine(backend).synthesize(VoiceRequest(text="hi"))   # no delivery / no casting
    assert r.ok and backend.last_voice == "af_heart" and backend.last_speed == 1.0


def test_end_to_end_director_casting_manager_engine():
    # Brain -> Director (DeliveryPlan) -> Casting (RenderingProfile) -> Manager -> engine.
    backend = FakeKokoroBackend(ready=True, audio=b"WAV")
    graph = VoiceCapabilityGraph()
    graph.register(VoiceCapability("nero_commander", "kokoro", ("en",)), KokoroEngine(backend))
    mgr = VoiceManager(graph, EngineHealthCache(), emergency_voice="nero_commander")

    req = VoiceRequest(text="The build has failed.", voice_id="nero_commander",
                       delivery={"emotion": "serious", "authority": 0.9, "intensity": 0.9, "pace": "fast"})
    directed = PerformanceDirector().direct(req)          # -> DeliveryPlan (numeric pace/intensity)
    cast = _casting().cast_request(directed)              # -> RenderingProfile
    r = mgr.speak(cast)
    assert r.ok and r.engine == "kokoro"
    assert backend.last_voice == "am_michael"             # nero_commander -> authoritative -> native
    assert backend.last_speed > 1.0                       # fast pace * authoritative baseline (>1)


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-rendering tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
