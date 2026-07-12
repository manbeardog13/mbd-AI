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
| 2 | **Voice Capability Graph** | `local_tts/voice_capability_graph.py` | ✅ done |
| 3 | **Engine Health (cache)** | `local_tts/engine_health.py` | ✅ done |
| 4 | **Voice Manager** | `manager/voice_manager.py` | ✅ done |
| 5 | **Voice Profiles** (`cast.json`) | `profiles/cast.json` + `profiles/loader.py` | ✅ done |
| 6 | **Performance Director** | `personalities/performance_director.py` | ✅ this stage |
| 7 | Event Bus | `manager/events.py` | ⏭ next |
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

## Stage 3 — the Engine Health Cache (`local_tts/engine_health.py`)

A **lightweight state tracker** answering one question: *"Given an engine's recent
runtime outcomes, should the Voice Manager attempt this engine now?"* Backoff is a
**protection mechanism, not intelligence** — predictable, capped, no learning.

- `EngineHealthCache` — `record_success()` / `record_failure(reason)` /
  `should_attempt()` / `status()` / `get()` / `snapshot()`. Injectable clock
  (`now=`) for deterministic time behaviour. One record per engine.
- `EngineHealthRecord` — `engine_name`, `status`, `last_check`, `last_success`,
  `last_failure`, `failure_reason`, `consecutive_failures`, `retry_after`.
- Lifecycle: `UNKNOWN → AVAILABLE → FAILING → COOLDOWN → RECOVERING → AVAILABLE`.
  A failure starts a capped exponential cooldown (`base·2ⁿ⁻¹`); a success clears
  the failure history.

**Owns:** engine operational state + attempt-gating + telemetry.
**Does NOT own:** routing (the Voice Manager combines this with the Capability
Graph), VRAM management (a future VRAM Guard subsystem), any executive concern.

### Decision — Health vs. Capability, and no VRAM here *(documented, not yet an ADR)*

Two separate questions, two separate systems, composed only by the future Voice
Manager — never by each other:

| System | Question |
|---|---|
| **Voice Capability Graph** | *Can this voice **theoretically** perform with the currently available engine configuration?* |
| **Engine Health Cache** | *Should we **attempt** this engine right now, based on recent runtime history?* |
| **Voice Manager** *(future)* | Combines both answers and **makes the routing decision.** |

Cooldown/backoff is **time-based protection only** — VRAM awareness belongs to a
future, separate **VRAM Guard**, not here. This separation is recorded here first;
if it proves important across multiple future subsystems, promote it to a formal
ADR then (no ADR overhead yet).

## Stage 4 — the Voice Manager (`manager/voice_manager.py`)

The **single routing authority** in the presentation layer. *"Given a voice
request, select the best available presentation path and attempt audio delivery."*
It composes the Capability Graph (*can it perform?*) and the Health Cache (*should
we attempt it?*), walks an **injected** fallback chain, attempts synthesis, records
health outcomes, and emits telemetry. Small surface: `VoiceManager(graph, health,
*, emergency_voice, fallback_map, telemetry)` + `speak(request) → AudioResult`.

- **Routing chain:** preferred voice → injected personality fallbacks → emergency
  voice (NERO PRIME) → text-only. `AudioResult.outcome` distinguishes
  `primary` / `fallback` / `text_only` (for future diagnostics). Never raises,
  never returns `None`, never silently fails.
- **Engine exceptions become health failures**, not app crashes; the next
  candidate is still evaluated.
- **Fallback ordering is injected data only** — the manager knows the *order*,
  never the *reason* two voices are related (`fallback_map`; wired to `cast.json`
  in Stage 5).
- **Telemetry is observational only** — it never influences routing, never
  modifies health, never triggers recovery, never touches executive systems.

> **Principle (documented, not yet an ADR):** *The Voice Manager is the only
> component allowed to select presentation routing. It does not decide
> intelligence, intent, capability, or permissions.* No other component chooses
> voices, engines, or fallback paths. Promote to a formal ADR only if the same
> rule later expands beyond the Voice subsystem.

## Stage 5 — Voice Profiles (`profiles/cast.json` + `profiles/loader.py`)

> **The system knows how to *load* voices. It does not know *what a voice is*.**

Voice identity, personality relationships (fallbacks), language support, and
routing metadata now live in **data** (`cast.json`), not code. `cast.json` is a
**declarative manifest** — no logic, no routing, no conditional behavior, no
hidden defaults that create behavior. `loader.py` is a **thin translation layer**
that reads it, validates it, and produces the exact inputs the earlier stages
already consume:

```
cast.json                       ← declarative identity (data only)
   │  load_cast(path) → Cast     ← structural validation (no engines needed)
   │  Cast.populate(graph, {engine_name: TTSEngine})   ← engine-binding validation
   ▼
VoiceCapabilityGraph (Stage 2)  +  VoiceManager(emergency_voice, fallback_map) (Stage 4)
```

Data flows **one way only** — nothing flows back. The loader **may** read JSON,
validate, and build immutable objects; it **may not** synthesize, select a voice,
make a fallback decision, manage health, create engines, touch GPU/model state, or
import any executive system. Stages 1–4 are **unchanged** — Stage 5 only adds a
data source upstream of them.

**Fail loud, fail safe.** Every malformed manifest becomes a single `CastError`
naming the *voice*, the *field*, and the *reason* — never a leaked
`JSONDecodeError` / `FileNotFoundError` / `KeyError`. The loader rejects: bad JSON,
a missing file, duplicate `voice_id`, an undefined or absent `emergency` voice,
dangling fallback targets, **self / circular** fallback chains, a missing engine
binding, and — the Stage 4 finding — **a declared language the bound engine cannot
actually produce** (which would otherwise make a voice silently vanish at runtime
via the manager's language gate). An empty-but-valid manifest loads safely with
zero voices; the *runtime* layers, not the loader, decide whether that is useful.

**Bilingual note.** The foundation binds every voice to the shipped `kokoro`
engine (English). Croatian (`hr`) voices are added to `cast.json` — a **data**
change, not a code change — once the `mms_hr` engine ships. That is the whole point
of moving identity into data.

## Stage 6 — Performance Director (`personalities/performance_director.py`)

> **Brain decides *what* is said. The Performance Director decides *how* it's
> delivered. The Voice Manager decides *who* says it. The Engine decides *how* the
> audio is produced.** Four responsibilities, four components, one-way.

**The split from the Bible.** `docs/VOICE.md` (§119) describes a single "Voice
Director" that chose *both* the voice *and* the delivery style in one blob. V1.2.1
**split** that: voice selection → the **Voice Manager** (Stage 4); delivery
interpretation → the **Performance Director** (this stage). The Director is the
*delivery-style half* of the Bible's Voice Director, with the routing half removed.

It is a **pure, deterministic transformation** — the Principle of Least
Intelligence made concrete. It reads the Brain's raw *delivery intent* (the
free-form `delivery` dict on a `VoiceRequest`) and returns a **new**
`VoiceRequest` whose `delivery` is a canonical, clamped `DeliveryPlan`:

```
Brain → VoiceRequest(raw delivery intent)
      → PerformanceDirector.direct()            ← this stage (upstream of routing)
      → VoiceRequest(canonical DeliveryPlan)
      → VoiceManager.speak() → engine.synthesize()
```

**Contract.** `direct(request) -> VoiceRequest`. Normalizes `emotion` (unknown →
`neutral`), the 0–1 dials `authority`/`warmth`/`intensity`/`humor` (clamped;
`humor` is the TARS dial), `pace` (`slow`→0.85 / `normal`→1.0 / `fast`→1.15, or a
clamped multiplier), `pauses` (`none`/`short`/`long`, unknown → `short`), and
`effects` (canonical names only; unknown dropped). `text`, `voice_id`, `language`
and `speed` pass through **untouched**, and the input request is **never mutated**.
Same intent in → identical plan out. Engines honor what they support and ignore the
rest (best-effort), so the Director stays engine-agnostic.

**MAY NOT (non-negotiable):**
- **no voice selection** — it never creates or changes `voice_id`;
- **no routing / fallback** — that authority is the Voice Manager's alone;
- **no memory**, no state, no learning, no adaptation;
- **no inference** — it never reads the *meaning* of the response text, runs no
  sentiment/emotion detection, calls no LLM;
- **no engine control** and **no engine/health/capability awareness**;
- **no capability decisions**, no executive calls, no I/O, no randomness.

> The goal is not a clever component — it is a *perfectly placed* one. If the
> Director is ever tempted toward emotional intelligence, context understanding,
> personality simulation, automatic voice choice, or adaptive behavior, that
> temptation is rejected: those are other components' jobs.
