"""Voice Platform tests — Stage 4: the Voice Manager (single routing authority).

Composition of the Capability Graph + Engine Health Cache + engines, with an
injected fallback chain. Pure test doubles (no engine bodies, models, or GPU).
Proves the routing correctness / isolation / reliability invariants Toni required.

Run directly:  python tests/test_voice_manager.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import AudioResult, BaseTTSEngine, NullEngine, VoiceRequest
from voice.local_tts.engine_health import EngineHealthCache
from voice.local_tts.voice_capability_graph import VoiceCapability, VoiceCapabilityGraph
from voice.manager.voice_manager import (
    OUTCOME_FALLBACK, OUTCOME_PRIMARY, OUTCOME_TEXT_ONLY, VoiceManager,
)


class OkEngine(BaseTTSEngine):
    def __init__(self, name, langs=("en",)):
        super().__init__(); self.name = name; self._languages = langs; self.calls = 0

    def _available(self): return True

    def _synthesize(self, request):
        self.calls += 1
        return (b"wav-" + self.name.encode(), 24_000)


class FailEngine(BaseTTSEngine):
    def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)

    def _available(self): return True

    def _synthesize(self, request):
        return (b"", 0)                      # clean failure (no audio)


class RaiseEngine(BaseTTSEngine):
    def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)

    def _available(self): return True

    def _synthesize(self, request):
        raise RuntimeError("engine exploded")


# fallback: commander -> aurelia -> (emergency) prime
FALLBACK = {"nero_commander": ("nero_aurelia",)}


def _setup(engines):
    """engines: dict voice_id -> engine. Returns (graph, health, manager, telem)."""
    graph = VoiceCapabilityGraph()
    for voice_id, engine in engines.items():
        graph.register(VoiceCapability(voice_id, engine.name, tuple(engine.languages())), engine)
    health = EngineHealthCache(base_cooldown_s=5.0)
    telem = []
    mgr = VoiceManager(graph, health, emergency_voice="nero_prime",
                       fallback_map=FALLBACK, telemetry=telem.append)
    return graph, health, mgr, telem


def test_preferred_voice_wins_when_available_healthy_and_succeeds():
    prime = OkEngine("kokoro")
    _, _, mgr, telem = _setup({"nero_prime": prime})
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.outcome == OUTCOME_PRIMARY and r.voice_id == "nero_prime"
    assert prime.calls == 1
    assert any(e["event"] == "selected" for e in telem)


def test_fallback_not_used_when_preferred_succeeds():
    prime, luna = OkEngine("e_prime"), OkEngine("e_luna")
    _, _, mgr, _ = _setup({"nero_prime": prime, "nero_luna": luna})
    mgr._fallback = {"nero_prime": ("nero_luna",)}
    mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert prime.calls == 1 and luna.calls == 0     # fallback never attempted


def test_emergency_only_after_preferred_and_personality_fallbacks_fail():
    cmd, aur, prime = FailEngine("e_cmd"), RaiseEngine("e_aur"), OkEngine("e_prime")
    _, _, mgr, telem = _setup({"nero_commander": cmd, "nero_aurelia": aur, "nero_prime": prime})
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_commander"))
    assert r.ok and r.outcome == OUTCOME_FALLBACK and r.voice_id == "nero_prime"
    order = [e["voice"] for e in telem if e["event"] in ("engine_failed", "selected")]
    assert order == ["nero_commander", "nero_aurelia", "nero_prime"]  # order respected


def test_routing_is_deterministic_with_identical_inputs():
    def once():
        _, _, mgr, _ = _setup({"nero_commander": FailEngine("c"), "nero_aurelia": OkEngine("a"),
                               "nero_prime": OkEngine("p")})
        return mgr.speak(VoiceRequest(text="x", voice_id="nero_commander")).voice_id
    assert once() == once() == "nero_aurelia"       # same inputs -> same route


def test_unhealthy_engine_is_skipped():
    prime, luna = OkEngine("e_prime"), OkEngine("e_luna")
    _, health, mgr, _ = _setup({"nero_prime": prime, "nero_luna": luna})
    mgr._fallback = {"nero_prime": ("nero_luna",)}
    health.record_failure("e_prime", "down")        # prime's engine now in cooldown
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna" and prime.calls == 0


def test_language_requirement_is_resolved():
    en_only, hr = OkEngine("e_en", ("en",)), OkEngine("e_hr", ("hr",))
    _, _, mgr, _ = _setup({"nero_prime": en_only, "nero_luna": hr})
    mgr._fallback = {"nero_prime": ("nero_luna",)}
    r = mgr.speak(VoiceRequest(text="bok", voice_id="nero_prime", language="hr"))
    assert r.ok and r.voice_id == "nero_luna"       # en-only prime skipped for hr


def test_engine_exception_becomes_health_failure_not_crash():
    _, health, mgr, _ = _setup({"nero_commander": RaiseEngine("boom"), "nero_prime": OkEngine("p")})
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_commander"))
    assert r.ok and r.voice_id == "nero_prime"                  # fell back, no crash
    assert health.get("boom").consecutive_failures == 1          # recorded as a failure


def test_partial_failure_still_produces_best_result():
    _, _, mgr, _ = _setup({"nero_commander": FailEngine("c"), "nero_aurelia": OkEngine("a"),
                           "nero_prime": OkEngine("p")})
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_commander"))
    assert r.ok and r.outcome == OUTCOME_FALLBACK and r.voice_id == "nero_aurelia"


def test_complete_failure_returns_text_only_never_crash():
    # every voice on a NullEngine (unavailable) — the zero-installed-packages case.
    _, _, mgr, _ = _setup({"nero_prime": NullEngine(), "nero_commander": NullEngine()})
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_commander"))
    assert r.ok is False and r.outcome == OUTCOME_TEXT_ONLY and isinstance(r, AudioResult)


def test_two_managers_do_not_share_state():
    _, h1, m1, _ = _setup({"nero_prime": OkEngine("e1")})
    _, h2, m2, _ = _setup({"nero_prime": OkEngine("e2")})
    h1.record_failure("e1", "down")
    assert m2.speak(VoiceRequest(text="x", voice_id="nero_prime")).ok is True  # m2 unaffected
    assert h2.get("e1") is None                     # separate health caches


def test_no_forbidden_imports():
    src = (Path(__file__).resolve().parent.parent
           / "voice" / "manager" / "voice_manager.py").read_text(encoding="utf-8")
    for forbidden in ("app.security", "app.capabilities", "app.agent",
                      "app.memory", "from app", "import app"):
        assert forbidden not in src, f"voice_manager.py must not reference {forbidden!r}"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-manager tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
