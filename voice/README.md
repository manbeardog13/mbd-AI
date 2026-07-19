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

## Frozen architecture principles (do not violate)

These are permanent, cross-cutting rules — recorded here so future work cannot
quietly erode the boundaries the staged build spent twelve stages protecting.

- **The architecture never learns that Croatia exists.** Routing is by *capability*
  (`language = "hr"`), never by country/culture/name. This keeps the system
  extensible to dozens of languages with **zero** special cases.

- **No smart fallback.** If a requested language/capability cannot be produced, the
  system fails **honestly** (`text_only`) — it never silently substitutes another
  language. Substitution is a future *conversational-layer* decision, never a Voice
  one. A capability system that substitutes becomes a heuristic system.

- **Rendering profiles never carry engine-specific detail** *(the frozen rule)*:
  > **A Voice Profile describes how speech should be rendered. It never contains
  > engine-specific implementation details. Engine bodies translate rendering
  > profiles into engine-native parameters.**

  This forbids leaks like `profile.speed = kokoro_speed` or
  `profile.voice = mms_voice_name`. Rendering profiles stay engine-agnostic; only the
  engine body maps them to native knobs.

- **Three concepts, never merged** — reserve this vocabulary; each can be swapped
  without touching the others:

  | Concept | Says | Owned by |
  |---|---|---|
  | **Identity** | *"I'm Nero Commander."* | the cast (`cast.json`) — data |
  | **Rendering** | *"I speak quickly with short pauses."* | a Voice Rendering Profile (Stage 13) |
  | **Engine** | *"Kokoro generated this waveform."* | an engine body (`voice/engines/`) |

  The evolving flow keeps them separate and engine-agnostic until the very last step:
  ```
  Intent → DeliveryPlan (semantic) → RenderingProfile (parametric) → Engine (native) → Audio
  ```
  The Manager, Capability Graph, Startup, Telemetry, and Health Report know **none**
  of the rendering detail — only the engine body interprets it.

- **Leave duplication; do not build a common engine base.** Two (or three) engines
  looking similar is not evidence for inheritance. Future engines have wildly
  different semantics — **streaming** (XTTS) wants a chunk generator not a monolithic
  `bytes`; **voice cloning** needs a reference-audio lifecycle the contract has no slot
  for; **Whisper** is speech-to-*text* (an *input* contract, not a TTSEngine at all).
  A base drawn around today's synchronous `(bytes, int)` engines would have to be
  demolished the moment a streaming engine arrives. *Good duplication is cheap; a
  wrong abstraction is expensive.* Extraction is considered only if a third engine
  shares a **byte-identical** method **and** no near-term engine is streaming — a
  condition that may never hold.

## Model-independent foundation — build order (one stage at a time)

Each stage stops with a verification report before the next begins.

| # | Component | Contract file | Status |
|---|-----------|---------------|--------|
| 1 | **TTSEngine Interface** | `local_tts/base.py` | ✅ done |
| 2 | **Voice Capability Graph** | `local_tts/voice_capability_graph.py` | ✅ done |
| 3 | **Engine Health (cache)** | `local_tts/engine_health.py` | ✅ done |
| 4 | **Voice Manager** | `manager/voice_manager.py` | ✅ done |
| 5 | **Voice Profiles** (`cast.json`) | `profiles/cast.json` + `profiles/loader.py` | ✅ done |
| 6 | **Performance Director** | `personalities/performance_director.py` | ✅ done |
| 7 | **Event Bus** | `manager/events.py` | ✅ done |
| 8 | **Voice Telemetry** | `manager/telemetry.py` | ✅ done |
| 9 | **Warm Startup** | `manager/startup.py` | ✅ done |
| 10 | **Voice Health Check** | `manager/health.py` | ✅ done — foundation complete |

**Engine bodies (post-foundation, `voice/engines/`):**

| # | Engine body | File | Status |
|---|-------------|------|--------|
| 11 | **Kokoro** (English) | `engines/kokoro.py` | ✅ done (contract adapter; real audio pending on RTX-4070) |
| 12 | **MMS** (Croatian) | `engines/mms.py` | ✅ this stage — first true multi-engine / bilingual proof (real audio pending on RTX-4070) |

**Rendering (`voice/rendering/`):**

| # | Component | File | Status |
|---|-----------|------|--------|
| 13 | **Voice Rendering Profile** | `rendering/profile.py` · `rendering/casting.py` · `rendering/profiles.json` | ✅ this stage — casting layer + engine honoring (real audio pending on RTX-4070) |

**Still deferred (additive, later):** XTTS/streaming integration, advanced effects,
the voice-selection UI, the ElevenLabs adapter (stub only, disabled), and — once a
*third* engine genuinely justifies it — the first-class `EngineIdentity` object.

## Stage 13 — Voice Rendering Profile (`voice/rendering/`)

> **The first feature a human will *hear*.** It makes the cast's identities *audible*
> — each persona rendered consistently across engines — without teaching orchestration
> anything about engines.

The one design question — *who owns `DeliveryPlan → RenderingProfile`?* — is answered
**Candidate C: a new pure "Voice Casting" mapper** (not the Director, which stays
semantic; not the engine, which must not see semantic intent; not the Manager, which
routes). The realized flow (no sealed-contract change — the `delivery: dict` seam
carries each step):

```
Intent → DeliveryPlan (semantic, Stage 6) → RenderingProfile (parametric, Stage 13)
       → engine-native parameters (inside the engine body) → Audio
```

- **`RenderingProfile`** (`rendering/profile.py`) — engine-agnostic + **identity-blind**:
  `voice_character` (an *abstract* descriptor like `"authoritative"`, never an engine
  voice id or persona name), `speed`, `pitch`, `energy`, `pause_style`. Loaded from
  **`rendering/profiles.json`** (kept **separate** from `cast.json` — the four concepts
  are never merged); a malformed manifest fails loud, an unknown `voice_id` resolves to
  a default (a persona without a declared rendering still speaks).
- **`VoiceCasting`** (`rendering/casting.py`) — the **pure, deterministic** mapper:
  `cast(voice_id, delivery) = base(voice_id) ⊕ modulate(delivery)` (identity baseline
  modulated by the DeliveryPlan's `pace`/`intensity`). No state, routing, health,
  telemetry, learning, I/O, or randomness; it imports nothing about the Manager, Graph,
  Health, Telemetry, or Startup. `cast_request()` returns a new `VoiceRequest` whose
  `delivery` now holds the RenderingProfile — **the semantic DeliveryPlan is consumed
  here and never reaches the engine** (closing the pre-Stage-13 leak).
- **Engine honoring** (`engines/kokoro.py`, `engines/mms.py`) — the engine body, and
  **only** it, maps the abstract `voice_character` → a native voice (Kokoro's and MMS's
  tables are **parallel, not shared** — no engine base class) and passes `speed`. The
  `*Backend.synthesize` seam gained optional `voice`/`speed` (additive, backward-
  compatible: text-only / pre-casting requests still work, falling back to the engine's
  default voice). **`app/tts.py` is untouched** — real parameterized Kokoro/MMS
  synthesis (audibly distinct personas) is a new backend path measured on the RTX-4070;
  the cloud proves the plumbing with fake backends that *record* the params.

*Only the engine bodies changed for Stage 13 (their designated job); the foundation and
`app/tts.py` are untouched.*

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

## Stage 7 — the Voice Event Bus (`manager/events.py`)

> **Report what happened. Never influence what happens.**

A tiny, synchronous, in-process observation pipe. Its purpose is **visibility, not
control**. It **wraps** the Voice Manager's *existing* `telemetry` callback
(Option B) — so the entire bus ships **without modifying the routing authority**,
which is the strongest property of the design:

```
Voice Manager → telemetry callback (existing contract) → VoiceEventBus → subscribers
```

**Facts, not commands.** Events describe what happened in the past tense
(`ENGINE_FAILED` because an engine returned no audio) — never what should happen
(there is no `TRY_FALLBACK`). Commands disguised as events are forbidden. The
minimal vocabulary: `VOICE_SELECTED`, `FALLBACK_USED`, `ENGINE_FAILED`,
`ENGINE_COOLDOWN`, `VOICE_SKIPPED`, `TEXT_ONLY_RESULT`, and `DELIVERY_APPLIED`
(*defined for a stable schema but not emitted* — the future Brain→Director→Manager
orchestrator is its correct emitter; the Director stays pure and the Manager stays
unchanged).

**Subscriber isolation.** `VoiceEvent` is a frozen, schema-versioned,
timestamped, sequence-numbered fact; its `payload` is a **read-only** mapping of
value-copied scalars — never a reference to a live Manager/Graph/Health/Engine
object. Subscribers are notified synchronously in subscription order, each inside
its own guard, so **one bad observer cannot affect another — or voice execution**.
Timestamps come from an **injected clock** (the Engine-Health pattern) for
deterministic tests. Zero subscribers is a near-zero-overhead no-op. Wiring is a
one-liner: `VoiceManager(graph, health, telemetry=bus.manager_sink())`.

**Wrap the existing seam.** `manager_sink()` translates the Manager's telemetry
dicts into typed events; unknown telemetry is safely ignored (never crashes,
never affects execution). The Manager depends on a callback; the bus is one
implementation of it — the dependency is strictly one-way (`events.py` imports
nothing about the Manager, Graph, Health, Director, or any executive system).

**MAY:** notify observers · carry lifecycle metadata · aid debugging · enable
future dashboards/metrics.
**MAY NOT:** select voices · mark engines healthy/unhealthy · alter a
`DeliveryPlan` · write memory · trigger tools · call security · dispatch actions ·
persist data · use async/threads/queues · become a second brain — or a second
**Action Journal** (that owns durable executive chain-of-custody + replay; this
bus is ephemeral, in-process, executive-blind visibility).

## Stage 8 — Voice Telemetry (`manager/telemetry.py`)

> **The Event Bus reports facts. Voice Telemetry summarizes facts. The Action
> Journal records executive history.**

Voice Telemetry is a **bus subscriber** — the first real consumer of Stage 7's
observation seam, and the proof the seam was drawn correctly. It receives immutable
`VoiceEvent` facts, aggregates them into small in-memory counters, and exposes an
immutable `VoiceTelemetrySnapshot`. It **observes what happened; it never decides
what happens.** Wiring adds **no** Manager dependency:

```
Voice Manager → telemetry callback → Event Bus → VoiceTelemetry.handle() → snapshot()
```
```python
bus = VoiceEventBus(); telemetry = VoiceTelemetry(); telemetry.attach(bus)
mgr = VoiceManager(graph, health, telemetry=bus.manager_sink())   # Manager untouched
```

**Snapshot (minimal):** `total_events`, `selected_count`, `primary_count`,
`fallback_count`, `engine_failures`, `cooldown_skips`, `unavailable_skips`,
`language_skips`, `text_only_count`, `per_voice_counts`, `per_engine_failures`,
`average_latency_ms`, `last_event_timestamp`, `schema_version`. The snapshot is a
frozen dataclass whose map fields are read-only (`MappingProxyType`) copies — fully
**detached** from the live collector, so later events never change an old snapshot.

**Properties (by charter):**
- **Ephemeral** — in-memory only; it resets with the process. *No persistence.*
- **Synchronous** — `handle()` runs in-process on the emit path, doing only O(1)
  counter work (no sorting, I/O, network, model calls, or background processing).
- **No learning** — no scoring, trends, prediction, percentile analytics, or
  adaptation. Boring by design.
- **No decision authority** — it can never select voices, influence fallbacks,
  mutate Engine Health, alter a `DeliveryPlan`, call engines, or trigger actions.

**Dependency direction** is one-way: telemetry imports only the event *vocabulary*
(`VoiceEvent`, `VoiceEventType`); it imports nothing about the Voice Manager, the
Capability Graph, the Engine Health cache, the Performance Director, or any
executive system. It is **not** an Action Journal — that remains the sole authority
for durable executive history; telemetry is ephemeral voice visibility only.

## Stage 9 — Warm Startup / Voice Runtime Initialization (`manager/startup.py`)

> **The composition root — a composer, not a commander.** The workshop table where
> the machine is assembled, never the mechanic deciding which gear should turn.

`build_voice_runtime(...)` wires the sealed Stages 1–8 bricks together in a fixed,
deterministic order and returns a `VoiceRuntime`:

```
build_voice_runtime(engines, cast_path, clock, …)
  load_cast → VoiceCapabilityGraph → cast.populate(graph, engines)
           → EngineHealthCache → VoiceEventBus → VoiceTelemetry.attach(bus)
           → VoiceManager(graph, health, emergency_voice, fallback_map,
                          telemetry=bus.manager_sink())
```
```python
rt = build_voice_runtime(engines={"kokoro": kokoro_engine})   # engines are INJECTED
rt.manager.speak(VoiceRequest(text="…", voice_id="nero_prime"))
rt.readiness()   # -> VoiceReadiness(state=READY|DEGRADED|OFFLINE, …)
```

`VoiceRuntime` contains `manager`, `bus`, `telemetry`, `graph`, `health`, `cast`.
Callers speak through `runtime.manager.speak(...)` — the runtime is a container, not
a second interface hiding the routing authority (no `runtime.speak()`).

**Owns:** object construction · dependency wiring · composition ordering · readiness
*reporting*.
**Does NOT own:** routing · fallback logic · voice ranking · engine selection · health
*decisions* · retries · recovery · memory · personality · LLM calls · Action Journal.

**Engines are injected, never created here.** The RTX-4070's real engines — and their
GPU warm-up — live behind the `TTSEngine` abstraction; startup sees *a plug, not the
electricity behind the wall*, keeping it model-independent and cloud-testable.

**Composition failure vs. operational readiness.** An unreadable/invalid manifest, a
missing engine binding, or a language a bound engine cannot produce is a
*configuration* failure → `StartupError`, **no partial runtime**. Engines merely being
*unavailable* is **not** a failure — it is *reported*, never raised:
- **READY** — the emergency voice can perform now (a guaranteed audio path).
- **DEGRADED** — some voice can perform, but the emergency voice cannot.
- **OFFLINE** — no voice can perform now (the Manager returns `text_only`).

**Not a health authority.** Readiness is derived by *asking* the Capability Graph
("can this voice perform now?", live) — startup **never** calls `record_success`/
`record_failure`/`record_repair`; engine health history begins only when runtime
execution begins. `readiness()` re-probes live state on every call.

**The one sanctioned composition root.** `startup.py` is the only module allowed to
import the Manager, Graph, Health, Bus, and Telemetry together — construction requires
it. Direction stays one-way: startup depends on the components; nothing depends on
startup. `voice_manager.py` is **constructed, never modified**.

## Stage 10 — Voice Health Check (`manager/health.py`)

> **Engine Health remembers. Telemetry observes. Startup assembles. The Health
> Report interprets the current picture — and nobody decides for the Manager.**

A **stateless, read-only interpreter** answering *"what is the current observable
health picture of the voice subsystem?"* — never *"what should the system do next?"*
A crystal-clear glass window, not a mysterious oracle. It composes **three lenses**
from three sovereign authorities, on demand, owning nothing:

| Lens | Source (authority) | Question |
|---|---|---|
| **Availability** — `available_voices`, `total_voices`, `emergency_available` | Capability Graph | *can voices perform now?* |
| **Attempt-health** — `engines{status, should_attempt, consecutive_failures}`, `gated_engines` | Engine Health | *would this engine be allowed an attempt?* |
| **Execution** — `recent{engine_failures, fallback_count, text_only_count, selected_count, average_latency_ms, per_engine_failures}` | Telemetry snapshot | *what has happened?* |

Plus an **advisory rollup** `overall ∈ {HEALTHY, DEGRADED, OFFLINE}` — a **pure
function**, *descriptive only, never consumed by the Manager*:
- **OFFLINE** — no voice can perform now.
- **DEGRADED** — the emergency voice is unavailable, **or** any engine is gated by
  cooldown, **or** recent `engine_failures > 0`, **or** `text_only_count > 0`.
- **HEALTHY** — otherwise. No weighting, no scoring, no confidence, no prediction.

```python
from voice.manager.health import build_health_report, report_for_runtime
report = report_for_runtime(runtime)          # or build_health_report(graph=…, engine_health=…, telemetry=…)
report.overall                                 # HEALTHY | DEGRADED | OFFLINE  (advisory)
```

**Owns:** interpretation / presentation of one immutable report.
**Refuses to own:** routing · fallback · voice selection · recovery/restart/reload ·
retries · health mutation (never `record_*`) · its own state · persistence ·
learning/scoring/prediction · Event Bus subscription (it reads Telemetry's *snapshot*)
· any executive coupling.

**Availability overlaps Startup readiness because both read the Graph — but reading an
authority is not becoming one.** Two consumers reading one source is fine; neither owns
it. Pull-only and stateless (every call re-reads live state), the report imports **no**
voice module (duck-typed on `runtime.graph`/`health`/`telemetry`), so there is no cycle
and nothing depends on it. The three lenses stay three questions with three owners.

---

*Stages 1–10 complete the model-independent Voice Platform foundation.*

## Stage 11 — the Kokoro engine body (`engines/kokoro.py`)

> **The first ship docking into the harbor — and it does not steer the harbor.**

The first real engine body. `KokoroEngine` exposes the proven `app/tts.py` (Kokoro)
through the sealed `BaseTTSEngine` contract — a **docking adapter, not a rebuild**:
`app/tts.py` is *wrapped, never modified* (strangler-fig). Engine **bodies** now live
in `voice/engines/`, separate from orchestration (`voice/manager/`) and from the
sealed contract (`voice/local_tts/base.py`).

**The split (backend injected, testable):**
```
TTSEngine (contract, sealed) ← KokoroEngine (translates) ← KokoroBackend (does the work)
                                                             ├── FakeKokoroBackend (cloud tests)
                                                             └── RealKokoroBackend  → app/tts.py → Kokoro + RTX-4070
```
- **`KokoroEngine`** owns only contract translation · metadata · backend delegation.
  It implements `_available()`/`_synthesize()` **only** — no `speak`/`fallback`/
  `select_voice`/`recover`/`retry`. It never bypasses the Stage 1 envelope (timing,
  exception containment, `AudioResult`, health bookkeeping).
- **`RealKokoroBackend`** is the **only** place that imports `app.tts`, and it does so
  **lazily** — so `voice/engines/` stays importable where Kokoro's deps don't exist.
  It reports not-ready and never raises without the model (real behavior = RTX-4070).
- **`FakeKokoroBackend`** is the cloud-safe test double (no model, no GPU, no `app`).

**Availability is a flashlight, not a lighthouse keeper** (the Stage 10 rule):
`is_ready()` is O(1) and never loads the model, probes VRAM, or generates sample
audio. `RealKokoroBackend` caches the **dependency probe** (not a synthesis success);
reality changes (model unload / GPU fail) surface at `synthesize()` time as a clean
`AudioResult(ok=False)` that the existing fallback + Engine Health handle.

**Current limitation (accepted):** `app/tts.py.synthesize(cfg, text)` takes text only,
so Stage 11 lights up **one** Kokoro voice — every cast profile sounds the same until
a future *additive* voice-parameter mapping (`request.voice_id`/`delivery` → Kokoro
voice/speed), which extends the backend without touching `app/tts.py` and stays inside
the engine (the Manager/Director are never involved). Stage 11 does **not** sneak in
voice identity.

**Owns:** turning text into audio · reporting availability.
**Refuses:** routing · fallback · voice selection · health decisions · engine ranking
· learning · model/GPU/download concerns (those belong to `RealKokoroBackend`/the
4070).

> **RTX-4070 validation (reserved, not cloud):** model load time · VRAM · cold vs.
> warm synthesis latency · RTF · failure behavior (missing dep/model/GPU →
> `AudioResult(ok=False)` → existing fallback handles it). The cloud proves the
> contract with a fake backend; measured audio/GPU numbers come only from the 4070.

## Stage 12 — the MMS Croatian engine body + first multi-engine proof (`engines/mms.py`)

> **The architecture never learns that Croatia exists.** The Capability Graph
> understands `language = "hr"`. It never understands "Croatia", "Croatian people",
> or "Croatian rules". That separation lets NERO grow to dozens of languages without
> accumulating special cases.

The second real engine body (Meta **MMS-TTS**, Croatian), and the first **true
multi-engine** proof — the "first driver-installation test." Adding it changes **no**
upper layer: `KokoroEngine(en)` + `MMSEngine(hr)` route purely by capability through
the *unchanged* Stage-4 language gate.

```
"Dobro jutro Nero" → VoiceRequest(language="hr")
   → Capability Graph: kokoro (en) can't · mms_hr (hr) can     ← language gate, UNCHANGED
   → Voice Manager: selects mms_hr                             ← no Croatian logic; pure capability
   → MMSEngine → audio
```

**Built in parallel, not on a shared base.** Two engines are not enough evidence to
justify a shared engine base — and MMS already diverges (16 kHz vs. Kokoro's 24 kHz).
A shared `BackendEngine`/`common.py` waits for a **third** engine (or proven stable
convergence): *good duplication is cheaper than bad inheritance.*

**Not a strangler-fig wrap.** Kokoro wrapped the proven `app/tts.py`; **MMS has no
existing code**, so `RealMMSBackend` is a *new integration seam* that lazily wraps a
**future `app/mms_tts.py`** (written + validated on the 4070; expected shape
`available(cfg)` / `synthesize(cfg, text)` / `SAMPLE_RATE`). In the cloud that module
is absent → `RealMMSBackend` is import-safe and reports not-ready.

### Permanent architectural rules (established here)
- **Preprocessing stays in the backend, forever.** Croatian punctuation,
  normalization, abbreviation expansion, and phonemization live **only** inside
  `RealMMSBackend` — never in the Voice Manager, Capability Graph, Startup, or
  Telemetry. Upper layers stay blissfully ignorant of language-specific detail.
- **No smart fallback.** If Croatian can't be produced, the system fails honestly
  (`text_only`) — it **never** silently substitutes English. The moment an engine
  substitutes another language, a capability system becomes a heuristic system;
  language substitution is a future *conversational-layer* decision, never a Voice one.
- **`cast.json` stays all-`kokoro` for now.** Because Stage-9 startup is
  all-or-nothing, declaring `mms_hr` voices in the *shipped* manifest before the real
  backend exists would turn a data change into a boot failure. Croatian joins the
  shipped cast as a deliberate **4070 data step** once `RealMMSBackend` works; Stage 12
  proves multi-engine behavior with **test manifests**.

*Note (deferred): once a **third** engine exists, engine metadata (name / languages /
voices / sample_rate) should become a first-class immutable `EngineIdentity` object
rather than more constructor fields — not implemented here.*
