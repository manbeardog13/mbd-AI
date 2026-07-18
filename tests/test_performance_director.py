"""Voice Platform tests — Stage 6: the Performance Director (delivery interpretation).

Proves the Director is a pure, deterministic, delivery-only transformation: raw
delivery intent -> canonical DeliveryPlan, with clamping / canonical fallbacks /
effect filtering, request identity preserved, input never mutated, no routing, no
LLM, no randomness, no I/O. One end-to-end test proves the canonical delivery
reaches a (stub) engine unchanged through the real VoiceManager.

Run directly:  python tests/test_performance_director.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import BaseTTSEngine, VoiceRequest
from voice.personalities.performance_director import (
    DeliveryPlan, PerformanceDirector, direct,
)


def _src() -> str:
    return (Path(__file__).resolve().parent.parent / "voice" / "personalities"
            / "performance_director.py").read_text(encoding="utf-8")


class CapturingEngine(BaseTTSEngine):
    """A stub engine that records the delivery dict it received (no bodies/models/GPU)."""

    def __init__(self, name="cap"):
        super().__init__(); self.name = name; self._languages = ("en",); self.seen = None

    def _available(self): return True

    def _synthesize(self, request):
        self.seen = dict(request.delivery)
        return (b"wav", 24_000)


# ---- 1. deterministic output ----
def test_deterministic_output():
    req = VoiceRequest(text="x", delivery={"emotion": "serious", "authority": 0.8,
                                           "pace": "slow", "effect": "reverb", "humor": 0.4})
    a = PerformanceDirector().direct(req).delivery
    b = PerformanceDirector().direct(req).delivery
    assert a == b
    assert direct(req).delivery == a            # module-level convenience matches


# ---- 2. numeric clamping ----
def test_numeric_clamping():
    d = PerformanceDirector().direct(VoiceRequest(
        text="x", delivery={"authority": 5.0, "warmth": -2.0, "intensity": 0.3,
                            "humor": 1.5})).delivery
    assert d["authority"] == 1.0 and d["warmth"] == 0.0
    assert d["intensity"] == 0.3 and d["humor"] == 1.0


# ---- 3. unknown emotion fallback ----
def test_unknown_emotion_falls_back_to_neutral():
    D = PerformanceDirector()
    assert D.direct(VoiceRequest(text="x", delivery={"emotion": "ecstatic"})).delivery["emotion"] == "neutral"
    assert D.direct(VoiceRequest(text="x", delivery={"emotion": "serious"})).delivery["emotion"] == "serious"


# ---- 4. effect filtering ----
def test_effect_filtering():
    D = PerformanceDirector()
    d = D.direct(VoiceRequest(text="x", delivery={
        "effects": ["whisper", "made_up", "reverb", "whisper"]})).delivery
    assert d["effects"] == ["whisper", "reverb"]        # unknown dropped, known kept, deduped, order kept
    d2 = D.direct(VoiceRequest(text="x", delivery={"effect": "subtle_system_alert"})).delivery
    assert d2["effects"] == ["subtle_system_alert"]     # singular 'effect' accepted


# ---- 5. empty delivery handling ----
def test_empty_delivery_creates_neutral_plan():
    d = PerformanceDirector().direct(VoiceRequest(text="hello")).delivery
    assert d["emotion"] == "neutral" and d["pace"] == 1.0 and d["pauses"] == "short"
    assert d["effects"] == [] and d["schema_version"] == 1
    assert d["authority"] == 0.5 and d["warmth"] == 0.5


# ---- 6. pace normalization ----
def test_pace_normalization():
    D = PerformanceDirector()
    def pace(v): return D.direct(VoiceRequest(text="x", delivery={"pace": v})).delivery["pace"]
    assert pace("slow") == 0.85 and pace("normal") == 1.0 and pace("fast") == 1.15
    assert pace("SLOW ") == 0.85                # case / whitespace tolerant
    assert pace(1.5) == 1.5                     # numeric multiplier passes through, clamped
    assert pace(9.0) == 2.0                     # clamped to max
    assert pace("gibberish") == 1.0             # unknown -> default


# ---- 7. humor / TARS dial preservation ----
def test_humor_dial_preserved_and_clamped():
    D = PerformanceDirector()
    assert D.direct(VoiceRequest(text="x", delivery={"humor": 0.7})).delivery["humor"] == 0.7
    assert D.direct(VoiceRequest(text="x", delivery={"humor": 3.0})).delivery["humor"] == 1.0


# ---- 8. VoiceRequest identity fields preserved ----
def test_request_identity_fields_preserved():
    req = VoiceRequest(text="Dobar dan", voice_id="nero_luna", language="hr", speed=1.2,
                       delivery={"emotion": "warm"})
    out = PerformanceDirector().direct(req)
    assert out.text == "Dobar dan" and out.voice_id == "nero_luna"
    assert out.language == "hr" and out.speed == 1.2


# ---- 9. input immutability ----
def test_input_request_not_mutated():
    original = {"emotion": "warm", "authority": 0.9}
    req = VoiceRequest(text="hi", voice_id="nero_prime", delivery=original)
    out = PerformanceDirector().direct(req)
    assert out is not req
    assert req.delivery is original and req.delivery == {"emotion": "warm", "authority": 0.9}
    assert out.delivery is not req.delivery     # a fresh dict, input untouched


# ---- 10. complete schema validation ----
def test_plan_schema_is_complete_and_typed():
    d = PerformanceDirector().direct(VoiceRequest(text="x", delivery={})).delivery
    assert set(d) == {"emotion", "authority", "warmth", "intensity", "humor",
                      "pace", "pauses", "effects", "schema_version"}
    assert isinstance(d["emotion"], str) and isinstance(d["pauses"], str)
    assert all(isinstance(d[k], float) for k in ("authority", "warmth", "intensity", "humor", "pace"))
    assert isinstance(d["effects"], list) and isinstance(d["schema_version"], int)
    assert isinstance(DeliveryPlan(), DeliveryPlan)   # frozen dataclass with full defaults


# ---- 11. garbage input safety ----
def test_garbage_input_is_safe():
    for junk in ({"authority": "high"}, {"warmth": None}, {"pace": object()},
                 {"emotion": 123}, {"effects": [1, 2, "whisper"]}, {"humor": float("nan")},
                 {"intensity": float("inf")}, {"pauses": 5}):
        d = PerformanceDirector().direct(VoiceRequest(text="x", delivery=junk)).delivery
        assert 0.0 <= d["authority"] <= 1.0 and 0.0 <= d["warmth"] <= 1.0
        assert 0.0 <= d["intensity"] <= 1.0 and 0.0 <= d["humor"] <= 1.0
        assert d["pauses"] in ("none", "short", "long")
    # non-dict delivery must also be safe
    bad = VoiceRequest(text="x"); bad.delivery = None       # type: ignore[assignment]
    assert PerformanceDirector().direct(bad).delivery["emotion"] == "neutral"


# ---- 12. no routing behavior ----
def test_no_routing_behavior():
    D = PerformanceDirector()
    out = D.direct(VoiceRequest(text="x", delivery={"emotion": "warm"}))
    assert out.voice_id == ""                               # never invents a voice
    assert "voice" not in out.delivery and "voice_id" not in out.delivery
    kept = D.direct(VoiceRequest(text="x", voice_id="nero_luna", delivery={}))
    assert kept.voice_id == "nero_luna"                     # preserves, never routes


# ---- 13. no forbidden imports ----
def test_no_forbidden_imports():
    src = _src()
    for forbidden in ("app.security", "app.capabilities", "app.agent", "app.memory",
                      "from app", "import app"):
        assert forbidden not in src, f"performance_director.py must not reference {forbidden!r}"


# ---- 14. no Manager / Graph / Health imports (proves it cannot route or manage health) ----
def test_no_manager_graph_health_imports():
    src = _src()
    for forbidden in ("VoiceManager", "VoiceCapabilityGraph", "EngineHealthCache",
                      "voice_manager", "voice_capability_graph", "engine_health"):
        assert forbidden not in src, f"Director must not reference {forbidden!r}"


# ---- 15. no LLM / randomness / I/O (usage forms, not prose) ----
def test_no_llm_or_randomness_or_io():
    src = _src()
    for forbidden in ("ollama", "import random", "random.", "httpx", "urllib",
                      "socket", "requests.", "open(", "Path("):
        assert forbidden not in src, f"Director must not use {forbidden!r} (pure + deterministic)"


# ---- 16. end-to-end: canonical delivery reaches the engine unchanged ----
def test_end_to_end_delivery_reaches_engine_unchanged():
    from voice.local_tts.engine_health import EngineHealthCache
    from voice.local_tts.voice_capability_graph import VoiceCapability, VoiceCapabilityGraph
    from voice.manager.voice_manager import VoiceManager

    eng = CapturingEngine("cap")
    graph = VoiceCapabilityGraph()
    graph.register(VoiceCapability("nero_prime", "cap", ("en",)), eng)
    mgr = VoiceManager(graph, EngineHealthCache(), emergency_voice="nero_prime")

    req = VoiceRequest(text="The build has failed.", voice_id="nero_prime",
                       delivery={"emotion": "serious", "authority": 0.9, "pace": "slow",
                                 "effect": "subtle_system_alert", "humor": 0.7})
    directed = PerformanceDirector().direct(req)      # Brain -> Director -> Manager -> Engine
    r = mgr.speak(directed)

    assert r.ok
    assert eng.seen == directed.delivery              # exactly the canonical plan reached synthesis
    assert eng.seen["emotion"] == "serious" and eng.seen["pace"] == 0.85
    assert eng.seen["effects"] == ["subtle_system_alert"] and eng.seen["humor"] == 0.7


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} performance-director tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
