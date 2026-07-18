"""The Nero Voice Platform — an OUTPUT INTERFACE, and nothing more.

Governed by docs/VOICE.md ("the Bible") and Toni's V1.2.1 architecture locks:

  * **Decision 1 — completely independent.** Voice presents responses produced
    elsewhere. It NEVER calls Registry.dispatch() or Gate.authorize(), never
    writes Action Journal entries, never executes capabilities, stores memory,
    holds cognition, forms intentions, makes decisions, or bypasses the Trust
    Engine. Its only input is finalized Brain output (text + delivery metadata).
    Health / status / latency / fallbacks / metrics belong to **Voice Telemetry**,
    which is separate from the Action Journal (the Journal records executive
    actions only).
  * **Decision 2 — wrap, never rewrite.** The shipped `app/tts.py` (Kokoro) is
    proven; a later `kokoro_engine` wraps it, `VoiceManager` orchestrates, and the
    existing `/api/speak` + `/api/voice` stay backward-compatible (strangler-fig).
  * **Decision 3 — its own track.** Voice (Track B) and Executive Intelligence
    (Track A: Registry, Trust Engine, Journal, Terminal) do not depend on each
    other's internals. The Brain produces a response; the Voice presents it.

Model-independent foundation first (this package builds it, one stage at a time);
engine bodies and all GPU/VRAM/latency work belong to the local RTX-4070
environment, never to cloud assumption.

The package now contains both the staged Voice Platform foundation and the
presentation-layer Voice Director, engine adapters, casting logic, and effects
described by ADR-0009 through ADR-0011. Hosted presence remains independent of
this optional standalone voice path.
"""
