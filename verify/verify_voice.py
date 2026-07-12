#!/usr/bin/env python3
"""Self-test for the Voice Platform — Stage 1: the TTSEngine contract.

Model-independent and fully offline (no engine bodies, no models, no GPU): proves
the interface's health-reporting envelope and best-effort failure paths on any
machine. Engine bodies + all GPU/VRAM/latency verification are the local RTX-4070
environment's job (never cloud assumption). Exit 0 = pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.base import (  # noqa: E402
    BaseTTSEngine, EngineStatus, NullEngine, TTSEngine, VoiceRequest,
)
from voice.local_tts.voice_capability_graph import (  # noqa: E402
    QualityLevel, VoiceCapability, VoiceCapabilityGraph,
)
from voice.local_tts.engine_health import (  # noqa: E402
    EngineHealthCache, HealthStatus,
)
from voice.manager.voice_manager import (  # noqa: E402
    OUTCOME_FALLBACK, OUTCOME_PRIMARY, OUTCOME_TEXT_ONLY, VoiceManager,
)
from voice.profiles.loader import (  # noqa: E402
    DEFAULT_CAST_PATH, CastError, load_cast,
)

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


class _Stub(BaseTTSEngine):
    name = "stub"
    _languages = ("en", "hr")
    _voices = ("nero_prime",)

    def _available(self) -> bool:
        return True

    def _synthesize(self, request):
        return (b"fake-wav", 24_000)


def main() -> int:
    null = NullEngine()
    check("NullEngine is unavailable", null.available() is False)
    check("NullEngine health is UNAVAILABLE", null.health().status == EngineStatus.UNAVAILABLE)
    check("NullEngine.synthesize fails cleanly (never raises)",
          null.synthesize(VoiceRequest(text="hi")).ok is False)

    stub = _Stub()
    r = stub.synthesize(VoiceRequest(text="Good evening, Toni.", voice_id="nero_prime"))
    check("a stub engine synthesizes (ok + audio + rate)",
          r.ok and bool(r.audio) and r.sample_rate == 24_000)
    check("stub health becomes READY after success", stub.health().status == EngineStatus.READY)
    check("languages/voices reported", stub.languages() == ["en", "hr"] and stub.voices() == ["nero_prime"])
    check("empty request is a clean failure", stub.synthesize(VoiceRequest(text=" ")).ok is False)

    check("both engines satisfy the TTSEngine Protocol (API-first)",
          isinstance(stub, TTSEngine) and isinstance(null, TTSEngine))

    # ---- Stage 2: Voice Capability Graph (runtime discovery) ----
    graph = VoiceCapabilityGraph()
    graph.register(VoiceCapability("nero_prime", "stub", ("en", "hr"),
                                   ("emotion",), QualityLevel.PREMIUM), stub)
    graph.register(VoiceCapability("nero_demon", "null", ("en",)), null)
    check("graph lists all registered voices",
          set(graph.voices()) == {"nero_prime", "nero_demon"})
    check("can_perform is LIVE: available engine -> True, unavailable -> False",
          graph.can_perform("nero_prime") is True and graph.can_perform("nero_demon") is False)
    check("available_voices returns only voices live right now",
          [c.voice_id for c in graph.available_voices()] == ["nero_prime"])
    check("available_voices filters by language",
          [c.voice_id for c in graph.available_voices(language="hr")] == ["nero_prime"]
          and graph.available_voices(language="fr") == [])
    check("resolve returns capability + engine + live status",
          graph.resolve("nero_prime").available is True
          and graph.resolve("nero_demon").available is False)
    check("snapshot is a telemetry view with live availability",
          {r["voice_id"]: r["available"] for r in graph.snapshot()}
          == {"nero_prime": True, "nero_demon": False})

    # ---- Stage 3: Engine Health Cache (attempt gating, deterministic clock) ----
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
    hc = EngineHealthCache(base_cooldown_s=5.0, max_cooldown_s=30.0)
    check("unknown engine is attemptable (UNKNOWN)",
          hc.should_attempt("kokoro", now=t0) and hc.status("kokoro", now=t0) == HealthStatus.UNKNOWN)
    hc.record_failure("kokoro", "no audio", now=t0)
    check("failure -> COOLDOWN, attempts blocked (cached, no re-probe)",
          hc.status("kokoro", now=t0 + timedelta(seconds=2)) == HealthStatus.COOLDOWN
          and hc.should_attempt("kokoro", now=t0 + timedelta(seconds=2)) is False)
    check("cooldown expiry -> RECOVERING, attempt allowed",
          hc.should_attempt("kokoro", now=t0 + timedelta(seconds=6)) is True
          and hc.status("kokoro", now=t0 + timedelta(seconds=6)) == HealthStatus.RECOVERING)
    hc.record_success("kokoro", now=t0 + timedelta(seconds=6))
    check("recovery clears failure history (AVAILABLE, 0 failures)",
          hc.status("kokoro", now=t0 + timedelta(seconds=6)) == HealthStatus.AVAILABLE
          and hc.get("kokoro").consecutive_failures == 0)
    hc.record_failure("kokoro", now=t0)
    hc.record_success("mms_hr", now=t0)
    check("one broken engine does not affect another",
          hc.should_attempt("kokoro", now=t0 + timedelta(seconds=1)) is False
          and hc.should_attempt("mms_hr", now=t0 + timedelta(seconds=1)) is True)

    # ---- Stage 4: Voice Manager (single routing authority, composition) ----
    class _Ok(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self.calls = 0
        def _available(self): return True
        def _synthesize(self, request): self.calls += 1; return (b"wav", 24_000)

    class _Fail(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name
        def _available(self): return True
        def _synthesize(self, request): return (b"", 0)

    g4 = VoiceCapabilityGraph()
    e_prime, e_luna = _Ok("e_prime"), _Ok("e_luna")
    g4.register(VoiceCapability("nero_prime", "e_prime", ("en",)), e_prime)
    g4.register(VoiceCapability("nero_luna", "e_luna", ("en",)), e_luna)
    h4 = EngineHealthCache(base_cooldown_s=5.0)
    mgr = VoiceManager(g4, h4, emergency_voice="nero_prime",
                       fallback_map={"nero_prime": ("nero_luna",)})
    r = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    check("preferred voice wins (outcome=primary), fallback untouched",
          r.ok and r.outcome == OUTCOME_PRIMARY and e_luna.calls == 0)
    h4.record_failure("e_prime", "down")   # prime engine now in cooldown
    r2 = mgr.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    check("unhealthy engine skipped -> fallback voice used (outcome=fallback)",
          r2.ok and r2.voice_id == "nero_luna" and r2.outcome == OUTCOME_FALLBACK)
    g5 = VoiceCapabilityGraph()
    g5.register(VoiceCapability("nero_prime", "null", ("en",)), null)
    r3 = VoiceManager(g5, EngineHealthCache()).speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    check("all engines down -> explicit text_only, never crash",
          r3.ok is False and r3.outcome == OUTCOME_TEXT_ONLY)

    # ---- Stage 5: Voice Profiles (cast.json + loader, declarative identity) ----
    class _Ok5(BaseTTSEngine):
        def __init__(self, name, langs=("en",)):
            super().__init__(); self.name = name; self._languages = tuple(langs)
        def _available(self): return True
        def _synthesize(self, request): return (b"wav", 24_000)

    class _Fail5(BaseTTSEngine):
        def __init__(self, name): super().__init__(); self.name = name; self._languages = ("en",)
        def _available(self): return True
        def _synthesize(self, request): return (b"", 0)

    shipped = load_cast(DEFAULT_CAST_PATH)
    check("shipped cast.json loads and validates (10 voices, emergency exists)",
          len(shipped.profiles) == 10
          and shipped.emergency_voice in {p.voice_id for p in shipped.profiles})

    def _tmp_cast(data) -> str:
        import json as _json
        import os as _os
        import tempfile as _tf
        fd, path = _tf.mkstemp(suffix=".json", prefix="verify_cast_")
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else _json.dumps(data))
        return path

    def _err(data) -> bool:
        import os as _os
        path = _tmp_cast(data)
        try:
            load_cast(path)
            return False
        except CastError:
            return True
        except Exception:            # any non-CastError leak is a failure of the contract
            return False
        finally:
            _os.remove(path)

    valid = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "e_prime", "languages": ["en"],
         "fallbacks": ["nero_luna"]},
        {"voice_id": "nero_luna", "engine": "e_luna", "languages": ["en"]},
    ]}
    cast5 = load_cast(_tmp_cast_cleanup := _tmp_cast(valid))
    import os as _os5
    _os5.remove(_tmp_cast_cleanup)

    g6 = VoiceCapabilityGraph()
    cast5.populate(g6, {"e_prime": _Ok5("e_prime"), "e_luna": _Ok5("e_luna")})
    check("loaded profiles populate the Capability Graph",
          set(g6.voices()) == {"nero_prime", "nero_luna"} and g6.can_perform("nero_prime"))

    g7 = VoiceCapabilityGraph()
    cast5.populate(g7, {"e_prime": _Fail5("e_prime"), "e_luna": _Ok5("e_luna")})
    mgr5 = VoiceManager(g7, EngineHealthCache(), emergency_voice=cast5.emergency_voice,
                        fallback_map=cast5.fallback_map)
    rr = mgr5.speak(VoiceRequest(text="hi", voice_id="nero_prime"))
    check("fallback is driven from cast data (prime fails -> luna delivers)",
          rr.ok and rr.voice_id == "nero_luna" and rr.outcome == OUTCOME_FALLBACK)

    lang_bad = {"emergency": "nero_prime", "voices": [
        {"voice_id": "nero_prime", "engine": "kokoro", "languages": ["en"]},
        {"voice_id": "nero_luna", "engine": "kokoro", "languages": ["hr"]},
    ]}
    cast_lang = load_cast(_p := _tmp_cast(lang_bad)); _os5.remove(_p)
    try:
        cast_lang.populate(VoiceCapabilityGraph(), {"kokoro": _Ok5("kokoro", ("en",))})
        lang_caught = False
    except CastError:
        lang_caught = True
    check("language mismatch fails loudly at load/wire time (Stage 4 finding)", lang_caught)

    try:
        cast5.populate(VoiceCapabilityGraph(), {"e_prime": _Ok5("e_prime")})  # e_luna missing
        eng_caught = False
    except CastError:
        eng_caught = True
    check("a missing engine binding is a CastError", eng_caught)

    check("malformed JSON -> CastError (never a raw JSONDecodeError)",
          _err("{ not json "))
    check("missing manifest file -> CastError (never a raw FileNotFoundError)",
          _missing_is_cast_error())
    check("duplicate voice_id -> CastError", _err(
          {"emergency": "a", "voices": [{"voice_id": "a", "engine": "e"},
                                        {"voice_id": "a", "engine": "e"}]}))
    check("circular fallback chain -> CastError", _err(
          {"emergency": "a", "voices": [{"voice_id": "a", "engine": "e", "fallbacks": ["b"]},
                                        {"voice_id": "b", "engine": "e", "fallbacks": ["a"]}]}))
    check("empty cast loads safely (0 voices, no crash)",
          _empty_cast_ok(_tmp_cast))

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Voice Stages 1-5 (contract + Capability Graph + Health Cache + "
          "Voice Manager + Voice Profiles) verified.")
    return 0


def _missing_is_cast_error() -> bool:
    try:
        load_cast("/no/such/path/verify_missing_cast.json")
        return False
    except CastError:
        return True
    except Exception:
        return False


def _empty_cast_ok(tmp_cast) -> bool:
    import os as _os
    path = tmp_cast({"voices": []})
    try:
        cast = load_cast(path)
        return cast.profiles == () and cast.emergency_voice == ""
    except Exception:
        return False
    finally:
        _os.remove(path)


if __name__ == "__main__":
    sys.exit(main())
