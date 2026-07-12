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

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Voice Stages 1-2 (TTSEngine contract + Capability Graph) verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
