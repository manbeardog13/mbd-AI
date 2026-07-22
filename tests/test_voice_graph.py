"""Voice Platform tests — Stage 2: the Voice Capability Graph (model-independent).

Verifies runtime discovery: availability is always resolved against the engine's
LIVE state, never cached. Pure test doubles (no engine bodies, models, or GPU).

Run directly:  python tests/test_voice_graph.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import BaseTTSEngine, NullEngine, VoiceRequest
from voice.local_tts.voice_capability_graph import (
    QualityLevel, VoiceCapability, VoiceCapabilityGraph,
)


class StubEngine(BaseTTSEngine):
    name = "stub"
    _languages = ("en", "hr")

    def _available(self) -> bool:
        return True

    def _synthesize(self, request: VoiceRequest):
        return (b"wav", 24_000)


class FlippableEngine(BaseTTSEngine):
    """Availability toggles at runtime — proves the graph never caches it."""
    name = "flip"

    def __init__(self):
        super().__init__()
        self.up = True

    def _available(self) -> bool:
        return self.up

    def _synthesize(self, request: VoiceRequest):
        return (b"wav", 24_000)


def _graph():
    g = VoiceCapabilityGraph()
    g.register(VoiceCapability("nero_prime", "stub", ("en", "hr"),
                               ("emotion",), QualityLevel.PREMIUM), StubEngine())
    g.register(VoiceCapability("nero_demon", "null", ("en",)), NullEngine())
    return g


def test_registers_and_lists_all_voices():
    g = _graph()
    assert set(g.voices()) == {"nero_prime", "nero_demon"}
    assert g.get("nero_prime").quality == QualityLevel.PREMIUM


def test_can_perform_is_live_not_static():
    g = _graph()
    assert g.can_perform("nero_prime") is True      # engine available
    assert g.can_perform("nero_demon") is False     # engine (Null) unavailable
    assert g.can_perform("unknown") is False


def test_available_voices_filters_to_live_and_language():
    g = _graph()
    ids = [c.voice_id for c in g.available_voices()]
    assert ids == ["nero_prime"]                    # demon excluded (unavailable)
    assert [c.voice_id for c in g.available_voices(language="hr")] == ["nero_prime"]
    assert g.available_voices(language="fr") == []   # prime doesn't speak fr


def test_resolve_returns_capability_engine_and_live_status():
    g = _graph()
    r = g.resolve("nero_prime")
    assert r.capability.voice_id == "nero_prime" and r.engine.name == "stub" and r.available is True
    assert g.resolve("nero_demon").available is False
    assert g.resolve("unknown") is None


def test_runtime_discovery_reflects_engine_going_down():
    g = VoiceCapabilityGraph()
    flip = FlippableEngine()
    g.register(VoiceCapability("nero_flux", "flip", ("en",)), flip)
    assert g.can_perform("nero_flux") is True
    flip.up = False                                  # engine goes down at runtime
    assert g.can_perform("nero_flux") is False       # reflected immediately, not cached
    assert g.available_voices() == []


def test_snapshot_is_telemetry_view():
    g = _graph()
    snap = {row["voice_id"]: row for row in g.snapshot()}
    assert snap["nero_prime"]["available"] is True and snap["nero_prime"]["quality"] == "premium"
    assert snap["nero_demon"]["available"] is False


def test_register_rejects_engine_mismatch():
    g = VoiceCapabilityGraph()
    try:
        g.register(VoiceCapability("x", "wrong-name"), StubEngine())  # declares "wrong-name" != "stub"
        raised = False
    except ValueError:
        raised = True
    assert raised, "mismatched capability.engine vs engine.name must be rejected"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-capability-graph tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
