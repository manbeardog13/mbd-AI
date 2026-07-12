# Nero Voice Platform (Track B)

Voice is an **output interface** — it presents responses produced by the Brain,
and nothing more. Governed by [`docs/VOICE.md`](../docs/VOICE.md) (the adopted
"Bible") and Toni's V1.2.1 architecture locks. Built **API-first**: every
component's public contract is defined here before its body is implemented, and
future components depend on interfaces, not implementations.

## Hard boundaries (non-negotiable)

- **Never on the executive path.** Voice must never call `Registry.dispatch()` or
  `Gate.authorize()`, write **Action Journal** entries, execute capabilities,
  store memory, hold cognition, form intentions, make decisions, or bypass the
  Trust Engine. Its only input is finalized Brain output (text + delivery
  metadata).
- **Telemetry ≠ Journal.** Voice health, engine status, latency, fallbacks and
  runtime metrics live in **Voice Telemetry**. The Action Journal records
  *executive actions* only. The two systems are completely independent.
- **Wrap, never rewrite.** The shipped `app/tts.py` (Kokoro) is proven. A later
  `kokoro_engine` *wraps* it; `VoiceManager` orchestrates; `/api/speak` and
  `/api/voice` stay backward-compatible (strangler-fig). No frontend changes.
- **Its own track.** Track B (Voice) and Track A (Registry · Trust Engine ·
  Journal · Terminal) never depend on each other's internals.
- **Naming.** The voice component that answers "can THIS voice perform right now?"
  is the **Voice Capability Graph** — never a "Capability Registry" (that name
  belongs to the executive Capability Registry, ADR-0007).
- **Hardware ownership.** Everything needing a GPU/CUDA/VRAM/latency/real audio —
  the engine bodies and benchmarks — runs only in the local RTX-4070 environment.
  Measured results always take precedence over assumptions; cloud never fabricates
  hardware validation.

## The pipeline (docs/VOICE.md)

```
Brain → Voice Director → Voice Personality → TTS Engine → Audio Output
        (delivery metadata)                  (replaceable)
```

## Model-independent foundation — build order (one stage at a time)

Each stage stops with a verification report before the next begins.

| # | Component | Contract file | Status |
|---|-----------|---------------|--------|
| 1 | **TTSEngine Interface** | `local_tts/base.py` | ✅ done |
| 2 | **Voice Capability Graph** | `local_tts/voice_capability_graph.py` | ✅ this stage |
| 3 | Engine Health (cache) | `local_tts/engine_health.py` | ⏭ next |
| 4 | Voice Manager | `manager/voice_manager.py` | planned |
| 5 | Voice Profiles (`cast.json`) | `profiles/cast.json` | planned |
| 6 | Performance Director | `personalities/performance_director.py` | planned |
| 7 | Event Bus | `manager/events.py` | planned |
| 8 | Voice Telemetry | `manager/telemetry.py` | planned |
| 9 | Warm Startup | `manager/startup.py` | planned |
| 10 | Voice Health Check | `manager/health.py` | planned |

**Deferred (not this foundation):** engine bodies (`kokoro_engine`, `mms_hr_engine`),
XTTS integration, advanced effects, the voice-selection UI, and the ElevenLabs
adapter (stub only, disabled) — all after every Phase-1 abstraction is verified.

## Stage 1 — the TTSEngine contract (`local_tts/base.py`)

An engine turns a `VoiceRequest` (finalized text + delivery metadata) into an
`AudioResult`, and reports `EngineHealth`. The interface carries **no
engine-specific logic**:

- `TTSEngine` (Protocol) — `available()`, `languages()`, `voices()`,
  `synthesize(request) -> AudioResult`, `health() -> EngineHealth`.
- `BaseTTSEngine` (ABC) — shared health-bookkeeping + timing envelope; a real
  engine implements only `_available()` and `_synthesize()`.
- `NullEngine` — always-unavailable reference + fallback sentinel.
- Data contracts — `VoiceRequest`, `AudioResult`, `EngineHealth`, `EngineStatus`.

All best-effort: synthesis never raises to the caller (a failure returns
`AudioResult(ok=False, …)` so a higher layer can fall back).
