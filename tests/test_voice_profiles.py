"""Voice Platform tests — Stage 5: Voice Profiles (cast.json + loader).

Proves the loader is a thin, fail-loud translation layer: it turns a declarative
manifest into immutable Stage 2 / Stage 4 inputs, rejects every malformed manifest
as a single CastError (never a leaked JSONDecodeError / FileNotFoundError / KeyError),
and catches the Stage 4 finding (a language a bound engine cannot produce) at load
time instead of letting a voice silently disappear at runtime.

Model-independent: pure test-double engines, no engine bodies, no models, no GPU.

Run directly:  python tests/test_voice_profiles.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import BaseTTSEngine
from voice.local_tts.engine_health import EngineHealthCache
from voice.local_tts.voice_capability_graph import VoiceCapabilityGraph
from voice.manager.voice_manager import OUTCOME_FALLBACK, VoiceManager
from voice.profiles.loader import (
    DEFAULT_CAST_PATH, Cast, CastError, load_cast,
)


# ---- test-double engines (no bodies / models / GPU) ----
class OkEngine(BaseTTSEngine):
    def __init__(self, name, langs=("en",)):
        super().__init__(); self.name = name; self._languages = tuple(langs); self.calls = 0

    def _available(self): return True

    def _synthesize(self, request):
        self.calls += 1
        return (b"wav-" + self.name.encode(), 24_000)


class FailEngine(BaseTTSEngine):
    def __init__(self, name, langs=("en",)):
        super().__init__(); self.name = name; self._languages = tuple(langs)

    def _available(self): return True

    def _synthesize(self, request):
        return (b"", 0)                         # clean failure (no audio)


# ---- fixtures / helpers ----
_MINI = {
    "emergency": "nero_prime",
    "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"],
         "quality": "premium"},
        {"voice_id": "nero_commander", "engine": "kokoro", "languages": ["en"],
         "fallbacks": ["nero_prime"]},
        {"voice_id": "nero_luna", "engine": "mms_hr", "languages": ["hr"],
         "fallbacks": ["nero_prime"]},
    ],
}


def _cast_file(data) -> str:
    """Write a manifest (dict -> JSON, or a raw string verbatim) to a temp file."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="nero_cast_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))
    return path


def _load(data) -> Cast:
    path = _cast_file(data)
    try:
        return load_cast(path)
    finally:
        os.remove(path)


def _expect_cast_error(data) -> str:
    """Load `data`, assert it raises CastError, return the message (and nothing but
    a CastError — never a leaked lower-level exception)."""
    try:
        _load(data)
    except CastError as exc:
        return str(exc)
    raise AssertionError("expected CastError, but the manifest loaded")


def _wire(cast: Cast, engines: dict):
    graph = VoiceCapabilityGraph()
    cast.populate(graph, engines)
    health = EngineHealthCache(base_cooldown_s=5.0)
    mgr = VoiceManager(graph, health, emergency_voice=cast.emergency_voice,
                       fallback_map=cast.fallback_map)
    return graph, health, mgr


# ---- 1. valid load ----
def test_valid_cast_loads():
    cast = _load(_MINI)
    assert [p.voice_id for p in cast.profiles] == ["nero_prime", "nero_commander", "nero_luna"]
    assert cast.emergency_voice == "nero_prime"
    assert cast.fallback_map["nero_commander"] == ("nero_prime",)
    assert len(cast.capabilities()) == 3


# ---- 2. duplicate IDs ----
def test_duplicate_voice_id_raises():
    data = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro"},
        {"voice_id": "nero_prime", "engine": "kokoro"},
    ]}
    assert "duplicate voice_id" in _expect_cast_error(data)
    assert "nero_prime" in _expect_cast_error(data)


# ---- 3. missing fallback targets ----
def test_missing_fallback_target_raises():
    data = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro"},
        {"voice_id": "nero_shadow", "engine": "kokoro", "fallbacks": ["ghost"]},
    ]}
    msg = _expect_cast_error(data)
    assert "nero_shadow" in msg and "ghost" in msg and "fallbacks" in msg


# ---- 4. missing engine bindings (populate-time) ----
def test_missing_engine_binding_raises():
    cast = _load(_MINI)                                  # loads fine (structure ok)
    try:
        cast.populate(VoiceCapabilityGraph(), {"kokoro": OkEngine("kokoro")})
    except CastError as exc:
        assert "nero_luna" in str(exc) and "mms_hr" in str(exc)
    else:
        raise AssertionError("expected CastError for the missing mms_hr engine")


# ---- 5. language mismatch detection (the Stage 4 finding, at load time) ----
def test_language_mismatch_raises():
    data = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"]},
        {"voice_id": "nero_luna", "engine": "kokoro", "languages": ["hr"]},  # kokoro: en only
    ]}
    cast = _load(data)                                   # structural load ok
    try:
        cast.populate(VoiceCapabilityGraph(), {"kokoro": OkEngine("kokoro", ("en",))})
    except CastError as exc:
        assert "nero_luna" in str(exc) and "hr" in str(exc) and "languages" in str(exc)
    else:
        raise AssertionError("expected CastError for the mis-declared 'hr' language")


# ---- 6. fallback cycle (and self-reference) detection ----
def test_fallback_cycle_raises():
    cyclic = {"emergency": "a", "voices": [
        {"voice_id": "a", "engine": "kokoro", "fallbacks": ["b"]},
        {"voice_id": "b", "engine": "kokoro", "fallbacks": ["a"]},
    ]}
    assert "circular fallback chain" in _expect_cast_error(cyclic)

    self_ref = {"emergency": "a", "voices": [
        {"voice_id": "a", "engine": "kokoro", "fallbacks": ["a"]},
    ]}
    assert "references itself" in _expect_cast_error(self_ref)


# ---- 7. missing emergency voice ----
def test_missing_emergency_raises():
    no_emergency = {"voices": [{"voice_id": "nero_prime", "engine": "kokoro"}]}
    assert "emergency" in _expect_cast_error(no_emergency)

    undefined_emergency = {"emergency": "ghost",
                           "voices": [{"voice_id": "nero_prime", "engine": "kokoro"}]}
    msg = _expect_cast_error(undefined_emergency)
    assert "ghost" in msg and "not defined" in msg


# ---- 8. malformed JSON handling ----
def test_malformed_json_raises():
    msg = _expect_cast_error("{ this is not valid json ")
    assert "not valid JSON" in msg              # a CastError, never a raw JSONDecodeError


# ---- 9. missing file handling ----
def test_missing_file_raises():
    try:
        load_cast("/no/such/path/nero_cast_missing.json")
    except CastError as exc:
        assert "not found" in str(exc)          # a CastError, never a raw FileNotFoundError
    else:
        raise AssertionError("expected CastError for a missing manifest")


# ---- 10. empty cast handling ----
def test_empty_cast_loads():
    cast = _load({"voices": []})
    assert cast.profiles == () and cast.emergency_voice == "" and cast.fallback_map == {}
    assert cast.capabilities() == ()            # loads safely; runtime decides usefulness


# ---- 11. graph population ----
def test_profiles_populate_graph():
    data = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"]},
        {"voice_id": "nero_luna", "engine": "kokoro", "languages": ["en"]},
    ]}
    graph, _, _ = _wire(_load(data), {"kokoro": OkEngine("kokoro")})
    assert set(graph.voices()) == {"nero_prime", "nero_luna"}
    assert graph.can_perform("nero_prime") is True      # live engine -> performable


# ---- 12. manager fallback driven from cast data ----
def test_manager_fallback_driven_from_cast():
    data = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "e_prime", "languages": ["en"],
         "fallbacks": ["nero_luna"]},
        {"voice_id": "nero_luna", "engine": "e_luna", "languages": ["en"]},
    ]}
    _, _, mgr = _wire(_load(data),
                      {"e_prime": FailEngine("e_prime"), "e_luna": OkEngine("e_luna")})
    from voice.local_tts.base import VoiceRequest
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    assert r.ok and r.voice_id == "nero_luna" and r.outcome == OUTCOME_FALLBACK


# ---- 13. emergency voice resolution ----
def test_emergency_voice_resolution():
    data = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_commander", "engine": "e_cmd", "languages": ["en"],
         "fallbacks": ["nero_aurelia"]},
        {"voice_id": "nero_aurelia", "engine": "e_aur", "languages": ["en"]},
        {"voice_id": "nero_prime", "engine": "e_prime", "languages": ["en"]},
    ]}
    _, _, mgr = _wire(_load(data), {
        "e_cmd": FailEngine("e_cmd"), "e_aur": FailEngine("e_aur"),
        "e_prime": OkEngine("e_prime"),
    })
    from voice.local_tts.base import VoiceRequest
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_commander"))
    assert r.ok and r.voice_id == "nero_prime" and r.outcome == OUTCOME_FALLBACK


# ---- 14. forbidden import scan ----
def test_no_forbidden_imports():
    src = (Path(__file__).resolve().parent.parent
           / "voice" / "profiles" / "loader.py").read_text(encoding="utf-8")
    for forbidden in ("app.security", "app.capabilities", "app.agent",
                      "app.memory", "from app", "import app"):
        assert forbidden not in src, f"loader.py must not reference {forbidden!r}"


# ---- 15. shipped cast.json validation ----
def test_shipped_cast_is_valid():
    cast = load_cast(DEFAULT_CAST_PATH)                  # structure only (engines injected later)
    assert len(cast.profiles) == 10
    ids = {p.voice_id for p in cast.profiles}
    assert cast.emergency_voice in ids                  # emergency exists
    for voice_id, targets in cast.fallback_map.items():
        assert all(t in ids for t in targets)           # every fallback target exists


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} voice-profiles tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
