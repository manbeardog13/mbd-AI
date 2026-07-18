# Nero — Project Status Brief

*A living, honest snapshot of where Nero stands — kept current as she evolves.
It doubles as a self-contained handoff you can give to an external advisor
(e.g. ChatGPT) to get sharper guidance: what actually exists today, the known
gaps, the roadmap, and pointed open questions. Blunt, specific feedback is
welcome — what to cut as readily as what to add.*

*Latest (2026-07-15): the **cross-host continuity ledger** is integrated on a
clean branch from the current remote tip. It is a cold, standard-library-only
SQLite transport for deliberately selected Claude/Codex handoffs with
hash-chained receipts, deterministic recall, sensitive-input refusal, and no
resident process. A real Codex→Claude equation challenge passed blind, and the
Claude→Codex transport returned the matching event and hash. Status is
**partial live verification**: the disabled-adapter `UNAVAILABLE` control and
the complete correction protocol remain before `LIVE_BIDIRECTIONAL_VERIFIED`.
The ledger is separate from the standalone app's `data/memory.db`; provenance
labels remain claimed rather than provider-attested. See
[ADR-0016](adr/0016-cross-host-continuity-ledger.md) and
[the Codex live update](../audit/nero-continuity/CODEX_LIVE_UPDATE.md).*

*Last updated: **PR #9 merged to `main`** — the NERO Design System UI redesign,
the ChatGPT-style two-button voice composer, hands-free conversation mode, and
Nero's local neural voice (Kokoro) playing her replies with iOS Web-Audio
playback + barge-in. Bundled in the same merge: the **V3 governance layer** — a
**Constitution** (v1.1), **ADRs 0001–0008**, a phased **Roadmap**, and the
**Phase-1 technical design** (all in `docs/`, mirrored on a shareable
[architecture page](https://claude.ai/code/artifact/f12facf1-875b-46d6-bdb4-78e35d817ea8)).
Two product decisions are settled: **ADR-0006 "Local-First with Intelligence
Escalation"** (local is the default; cloud is an explicit, opt-in, transparent
escalation, off by default) and the **Principle of Least Intelligence** (use the
simplest deterministic mechanism that's correct; invoke the LLM only when it
genuinely adds value).*

*Also shipped — **PR #10 merged: Phase 1 "The Hands," first slice**, and it's
**verified end-to-end on the RTX 4070**. The primitive that lets Nero **act**,
built safety-first: the **agent loop** (reason → tool → observe → repeat,
bounded, never hangs), the **Capability Registry** (the model reasons over
capabilities discovered at runtime, not a hard-coded list; one guarded dispatch
seam every call — built-in now, MCP/Skills later — passes through), the
**security gate** (every MEDIUM+ action needs confirmation, fail-closed; project
jail), **Executive Memory** (the working-state register —
goal/project/branch/task/blocker/next_action; branch & project observed from git,
not guessed), and read-only capabilities **`git.status`** and **`fs.read`**
(jailed, bounded — a path escaping the jail is gated). Endpoints: `POST
/api/agent`, `GET /api/agent/capabilities`, `GET`/`DELETE /api/executive`; agent
+ capability metrics in `/api/metrics`. **Verified on the PC:** a real qwen3:14b
drove the loop and answered via `git.status` (`verify_agent` live), the
adversarial battery gated 32 unconfirmed dangerous attempts with **0 escapes**,
and Executive Memory observed the real git branch — alongside the pre-existing
GPU / Ollama / memory / world-model / reflection checks. Next Phase-1
capabilities, one PR each: `fs.list`, `git.log`, then the human-in-the-loop
terminal (the confirmation Approve/Deny UX lands with the first MEDIUM+
capability).*

*Mission Control Milestone 1 is implemented and verified locally on
`codex/nero-mission-control-m1`; it has not been pushed. Under
[ADR-0017](adr/0017-authoritative-core-and-host-boundaries.md), the manually
launched, model-independent Nero Core owns measured Git state, tasks, a
repository-global lease, approvals, and hash-chained events. Claude and Codex
are bounded, replaceable worker definitions; M1 does not call either provider
and never invents a reply. The dashboard exposes explicit fetch, exact
branch/upstream wording, the task queue, workers, approvals, timeline, and
health. Commit/merge/pull/rebase/reset/checkout/push have no execution route.
See [the M1 design](DESIGN-mission-control-m1.md) and
[operator guide](MISSION_CONTROL.md).*

*In progress — **the Action Journal (Nero's accountability spine)**, the third
leg of the **executive control layer**: Capability Registry (*what can I do?*) ·
Trust Engine / security gate (*am I allowed?*) · **Action Journal** (*what did I
do, and can I prove it?*). Design approved + finalized (immutable/event-sourced;
hybrid durability — strict for mutations; 3-layer retention; an integrity check
that drops Nero into read-only **safe-mode** if her records can't be trusted) plus
**Amendment V1.1** (Emergency Lockdown · Explain-Before-Execute · Action Replay
metadata). Being built as a **controlled, staged PR**: **Stage 1 — storage
foundation** is pushed (append-only `action_journal` table with DB-level
immutability triggers, event-sourcing, `add_action`/`get_action`/`get_actions`;
10 storage tests green, 0 regressions), awaiting review before Stage 2. Separately,
the **Voice System V1.2.1** implementation map has been produced (Step-0 inspection
of the adopted `docs/VOICE.md` "Bible") and awaits approval — a parallel,
interface-only track (voice acts on nothing; it never touches the Trust Engine or
the Journal), whose GPU milestones run on the local instance.*

*Development now runs as **two independent tracks** (locked by Toni), each with
its own branch/PR/rollback point: **Track A — Executive Intelligence** (Capability
Registry · Trust Engine · Action Journal · Integrity · Terminal) and **Track B —
Voice Platform** (an output interface only — it never calls dispatch/authorize,
writes no Journal, executes nothing; "the Brain produces a response, the Voice
presents it"). Voice is built **model-independent foundation first, API-first**
(the contract before any engine body); GPU/VRAM/latency work belongs to the local
4070, never cloud assumption. **Voice Stages 1–10 (foundation) + Stages 11–12 (two
engine bodies, first multi-engine proof) + Stage 13 (Voice Rendering Profile) shipped**
on their own branch/PR (**PR #14**, draft): (1) the **TTSEngine interface** —
`voice/local_tts/base.py`
(`TTSEngine` Protocol · `BaseTTSEngine` health+timing envelope · `NullEngine`
fallback sentinel · `VoiceRequest`/`AudioResult`/`EngineHealth` contracts); (2) the
**Voice Capability Graph** — `voice_capability_graph.py`, answering "can THIS
voice perform right now?" by resolving against **live** engine state (runtime
discovery, never cached), mapping voice → engine → language → features →
availability → quality. All best-effort/never-raises; 14 tests + `verify_voice.py`
(14 checks) green; overheads 2.45 µs (envelope) / 0.2 µs (live resolve); zero
regressions. (3) the **Engine Health Cache** — `engine_health.py`, a lightweight
state tracker answering "should the Voice Manager attempt this engine now?" with a
predictable, capped time-based cooldown/backoff (protection, not intelligence; no
VRAM, no routing, no `app/` imports) over the lifecycle UNKNOWN → AVAILABLE →
FAILING → COOLDOWN → RECOVERING → AVAILABLE. Capability Graph ("can it perform?")
and Health Cache ("should we attempt it now?") stay separate; the future Voice
Manager composes them and makes routing. (4) the **Voice Manager** —
`manager/voice_manager.py`, the single routing authority: `speak(request)` walks
an injected fallback chain (preferred → personality fallbacks → emergency NERO
PRIME → text-only), gating each candidate on the Capability Graph + Health Cache,
attempting synthesis, recording outcomes, emitting telemetry; engine exceptions
become health failures (never crashes); the result's `outcome` distinguishes
primary/fallback/text_only. It orchestrates, never absorbs — no intelligence,
intent, memory, security, or synthesis logic; fallback *reasons* are injected data
(`cast.json`, Stage 5), not inferred. A later `kokoro_engine` will **wrap** the
shipped `app/tts.py` (strangler-fig), never rewrite it. (5) **Voice Profiles** —
`voice/profiles/cast.json` + `loader.py`: voice identity, fallback relationships,
language support and routing metadata now live in **declarative data**, on the
principle *"the system knows how to load voices; it does not know what a voice
is."* `cast.json` is a manifest (no logic/routing/conditionals); `loader.py` is a
thin translation layer — read JSON, validate, build the immutable `Cast`
(capabilities + `fallback_map` + `emergency_voice`) that feeds Stage 2 + Stage 4,
one-way. It creates no engines, makes no decisions, imports nothing executive.
Every bad manifest is a single loud/safe `CastError` (never a leaked
`JSONDecodeError`/`FileNotFoundError`); it rejects duplicate ids, dangling or
self/circular fallbacks, a missing engine binding, and — the Stage 4 finding —
**a declared language the bound engine can't produce** (caught at load/wire time,
not as a silent runtime drop). 15 tests + 10 verify checks green; load ≈0.09 ms,
populate ≈0.013 ms (startup-only); zero regressions across Stages 1–4. Croatian
voices join the manifest — a data change, not a code change — when `mms_hr` ships.
(6) the **Performance Director** — `voice/personalities/performance_director.py`:
answers *"how should this be delivered?"* and nothing else. `docs/VOICE.md`'s
single "Voice Director" (which chose both voice and style) is **split** —
voice-selection stays with the Voice Manager (Stage 4); delivery-interpretation is
this component. A **pure, deterministic** transform (Principle of Least
Intelligence): `direct(request) → VoiceRequest` reads the Brain's raw `delivery`
intent and returns a **new** request whose `delivery` is a canonical, clamped
`DeliveryPlan` (emotion→neutral fallback; authority/warmth/intensity/humor clamped
0–1, `humor` = the TARS dial; pace slow/normal/fast→0.85/1.0/1.15; pauses
none/short/long; unknown effects dropped). `text`/`voice_id`/`language`/`speed`
pass through untouched, input never mutated. **Option A** wiring (Director upstream
of the Manager) needs **zero contract changes** — `VoiceRequest.delivery` already
exists and `_with_voice` already forwards it, so the canonical plan reaches the
engine unchanged. No LLM, no randomness, no I/O, no memory, no text/sentiment
inference, no routing, no voice/engine/health/capability awareness. 16 tests + 6
verify checks green; ≈4.2 µs/call (CPU-only, no GPU); zero regressions across
Stages 1–5. (7) the **Voice Event Bus** — `voice/manager/events.py`: an
observational-only pub/sub — *"report what happened, never influence what
happens."* It **wraps** the Manager's existing `telemetry` callback (Option B), so
the whole bus ships with **zero change to `voice_manager.py`** (the headline).
`VoiceEvent` is a frozen, schema-versioned, timestamped, sequence-numbered fact
with a read-only value-copied payload (no references to live routing objects);
`VoiceEventBus` is `subscribe`/`unsubscribe`/`emit`/`manager_sink` — synchronous,
subscription-ordered, subscriber-fault-isolated, injectable clock, no
persistence/async/threads/queues. `manager_sink()` maps telemetry dicts to a
minimal past-tense vocabulary (VOICE_SELECTED, FALLBACK_USED, ENGINE_FAILED,
ENGINE_COOLDOWN, VOICE_SKIPPED, TEXT_ONLY_RESULT; DELIVERY_APPLIED defined but not
emitted — the future orchestrator is its emitter); unknown telemetry is ignored,
never crashes. Facts, not commands (no `TRY_FALLBACK`); observers cannot influence
routing; dependency is one-way (events.py imports nothing about Manager/Graph/
Health/Director/executive). 14 tests + 5 verify checks green; emit ≈0.08 µs (0
subs) / ≈3.4 µs (1–10 subs), CPU-only; zero regressions across Stages 1–6.
(8) **Voice Telemetry** — `voice/manager/telemetry.py`: the first real bus
subscriber — *"the Event Bus reports facts; Voice Telemetry summarizes facts; the
Action Journal records executive history."* It observes immutable `VoiceEvent`s and
aggregates them into in-memory counters (`total_events`, primary/fallback/selected,
engine_failures + `per_engine_failures`, cooldown/unavailable/language skips,
text_only, `per_voice_counts`, `average_latency_ms`, `last_event_timestamp`),
exposed as an immutable `VoiceTelemetrySnapshot` (frozen; read-only map copies,
detached from the live collector). API: `handle(event)` (O(1), on the synchronous
emit path), `snapshot()` (on-demand, off the hot path), `attach(bus)` (duck-typed
`bus.subscribe`, no bus/Manager import). Ephemeral (no persistence), synchronous
(no async/queue/worker), no learning/scoring/prediction, no decision authority —
it can never select voices, influence fallbacks, mutate health, alter delivery, or
call engines. Wiring adds **zero Manager dependency** (`telemetry=bus.manager_sink()`).
Dependency is one-way (imports only the event vocabulary). 16 tests + 4 verify
checks green; handle ≈0.55 µs, snapshot ≈2.2 µs, +≈7.9 µs per speak (CPU-only);
zero regressions across Stages 1–7; voice_manager.py untouched. (9) **Warm Startup**
— `voice/manager/startup.py`, the **composition root** (a composer, not a
commander): `build_voice_runtime(*, engines, cast_path, clock, …)` wires the sealed
Stages 1–8 bricks in a deterministic order (load_cast → graph → populate → health →
bus → telemetry.attach → Manager with `telemetry=bus.manager_sink()`) and returns a
frozen `VoiceRuntime(manager, bus, telemetry, graph, health, cast)` with a
`readiness()` re-probe. **Engines are injected, never created** (the 4070's engines
+ GPU warm-up stay behind the `TTSEngine` plug — model-independent, cloud-testable).
Composition failures (unreadable/invalid manifest, missing engine binding,
unsupported declared language) raise `StartupError` with no partial runtime;
operational unavailability is *reported* not raised via `VoiceReadiness`
(READY = emergency voice available / DEGRADED = some voice, not emergency / OFFLINE
= none). Not a health authority — readiness is derived by *asking* the Capability
Graph (live); startup never calls `record_success/failure/repair`. It owns only
construction/wiring/ordering/readiness-reporting — no routing, ranking, engine
selection, health decisions, retries, recovery, memory, personality, LLM, or Journal.
The one sanctioned broad-import module (composition needs it); one-way (nothing
imports startup); `voice_manager.py` constructed, never modified. 16 tests + 4
verify checks green; build ≈0.13 ms (10-voice cast), readiness ≈22 µs (CPU-only);
zero regressions across Stages 1–8. (10) **Voice Health Check** —
`voice/manager/health.py`, a **stateless read-only interpreter**: *"what is the
current observable health picture?"* (never *"what should the system do next?"*).
`build_health_report(*, graph, engine_health, emergency_voice, telemetry, now,
clock)` and `report_for_runtime(runtime)` compose three lenses — availability
(Graph: `available_voices`/`emergency_available`), attempt-health (Engine Health:
per-engine `status`/`should_attempt`/`consecutive_failures` + `gated_engines`),
execution (Telemetry snapshot: failures/fallbacks/text-only/latency) — plus a **pure
advisory rollup** `overall ∈ {HEALTHY, DEGRADED, OFFLINE}` (OFFLINE = no voice
available; DEGRADED = emergency down OR engine gated OR recent failures>0 OR
text_only>0; else HEALTHY) that the Manager never consumes. Immutable report; owns
nothing — no routing, no health mutation (never `record_*`), no state, no
persistence, no learning, no Event Bus subscription (reads Telemetry's snapshot). It
imports **no** voice module (duck-typed on `runtime.graph/health/telemetry`); one-way,
no cycle. Engine Health remembers · Telemetry observes · Startup assembles · the
Health Report interprets — three questions, three owners, nobody decides for the
Manager. 13 tests + 5 verify checks green; ≈22 µs/report (CPU-only); zero regressions
across Stages 1–9. **Stages 1–10 complete the model-independent foundation.** (11)
**Kokoro engine body** — `voice/engines/kokoro.py`, the first real engine (bodies now
live in `voice/engines/`, separate from orchestration): a **contract adapter** that
exposes the proven `app/tts.py` (Kokoro) through the sealed `BaseTTSEngine` — wrapped,
never modified (strangler-fig). `KokoroEngine(backend, *, name="kokoro", languages,
voices)` implements `_available()`/`_synthesize()` **only** (no speak/fallback/select/
recover/retry) and never bypasses the Stage-1 envelope; it delegates to an **injected**
`KokoroBackend`. `RealKokoroBackend(cfg)` is the sole `app.tts` importer (lazy — the
package stays importable without Kokoro deps) and caches the dependency probe (not a
synthesis success); `FakeKokoroBackend` is the cloud test double. Availability is a
flashlight (O(1), never loads/probes/synthesizes). Accepted limitation: text-only for
now (one Kokoro voice; per-profile voice mapping is a future additive step that never
touches `app/tts.py`). 14 cloud tests + 5 verify checks (61 total) green; fake-backend
overhead ≈0.18 µs available / ≈3.9 µs synth (adapter+envelope only). `app/tts.py` and
the entire sealed foundation unchanged; `build_voice_runtime` unchanged (the caller
injects `KokoroEngine(RealKokoroBackend(cfg))` on the 4070). (12) **MMS Croatian
engine body + first multi-engine proof** — `voice/engines/mms.py`: the second engine
(Meta MMS-TTS, `hr`, 16 kHz) behind the same sealed contract. Adding it changes **no**
upper layer — `KokoroEngine(en)` + `MMSEngine(hr)` route purely by capability through
the *unchanged* Stage-4 language gate (en→kokoro, hr→mms), and an hr request with MMS
down fails **honestly** to `text_only` — English is never substituted (**no smart
fallback**). Built in **parallel**, not on a shared base (two engines aren't enough
evidence; MMS already diverges at 16 kHz — *good duplication beats bad inheritance*).
Unlike Kokoro (a strangler-fig wrap of `app/tts.py`), MMS has no existing code:
`RealMMSBackend` is a new seam lazily wrapping a **future `app/mms_tts.py`** (4070
work; not-ready in cloud). Permanent rules set here: **language preprocessing lives
only in the backend** (never Manager/Graph/Startup/Telemetry); the **charter
principle** *"the architecture never learns that Croatia exists"* (capability, not
country); and the shipped `cast.json` stays **all-`kokoro`** (all-or-nothing startup
would turn a premature `mms_hr` data change into a boot failure — Croatian joins the
shipped cast as a 4070 data step when the backend is real; Stage 12 proves it with
test manifests). Deferred note: a first-class `EngineIdentity` object once a *third*
engine exists. 13 cloud tests + 5 verify checks green; fake-backend overhead ≈0.12 µs
available / ≈2.9 µs synth. Foundation, Kokoro, `cast.json`, and `app/*` all unchanged.
(13) **Voice Rendering Profile** — `voice/rendering/`: makes the cast's identities
*audible*. The one design question (*who owns `DeliveryPlan → RenderingProfile`*) is
answered **Candidate C — a new pure "Voice Casting" mapper** (not the Director/semantic,
not the engine/must-not-see-intent, not the Manager/routing). `RenderingProfile`
(`profile.py`) is engine-agnostic + identity-blind (`voice_character` abstract, +
speed/pitch/energy/pause_style), loaded from `rendering/profiles.json` — **separate**
from `cast.json` (four concepts never merged); malformed → loud `RenderingError`,
unknown voice_id → default. `VoiceCasting` (`casting.py`) is a **pure deterministic**
`cast(voice_id, delivery) = base(voice_id) ⊕ modulate(pace/intensity)`; it consumes the
semantic DeliveryPlan (via the `delivery` seam) so **no emotion/authority reaches the
engine** — closing the pre-13 leak — and imports nothing about Manager/Graph/Health/
Telemetry/Startup. Engine honoring (13b): each engine body — and only it — maps the
abstract `voice_character` → a native voice (Kokoro/MMS tables **parallel, no shared
base**) and applies speed; the `*Backend.synthesize` seam gained optional voice/speed
(additive, backward-compatible). **`app/tts.py` and the whole foundation are unchanged**
— only the engine bodies were extended (their designated job); real parameterized
synthesis (audibly distinct personas) is a new backend path on the RTX-4070, proven in
cloud via fake backends recording the params. 16 tests + 5 verify checks (71 total)
green; casting ≈3.2 µs/call; zero regressions across Stages 1–12. **Real audio /
audibly-distinct persona validation is reserved for the local RTX-4070.** Stopped for
review before Stage 14.*

---

## 1. What Nero is

A **local-first personal AI companion** named **Nero** (she/her). The standalone
application and its private memory run on the owner's PC and remain reachable
over a private encrypted network (Tailscale). Hosted Claude/Codex interfaces are
explicit adapters under the cloud-escalation policy; they do not receive local
databases or private context by default.

The explicit goal is to grow from "a chatbot" into a **cognitive companion**.
**North Star: continuity** — she should wake up already knowing what the owner
was doing and quietly help without being asked. The full architecture is in
[VISION.md](VISION.md); the governing philosophy (local-first, verification-
first) is in [DIRECTIVE.md](DIRECTIVE.md). **New here? Start at
[ARCHITECT_MEMORY.md](ARCHITECT_MEMORY.md)** — the project's durable memory and the
entry point for rebuilding context from the repo (documentation is the memory;
chat is only discussion about it).

## 2. The owner & hardware

- **Owner:** Toni.
- **Wants:** feels like a real person; accessible "like Siri" (voice, hands-free);
  no login friction; **bilingual English + Croatian**; a **TARS humor dial**; a
  female voice.
- **Hardware (confirmed):** Windows 11 PC, **NVIDIA RTX 4070 (12 GB VRAM)**,
  **64 GB RAM**. Everything is tuned to this.

## 3. Current architecture (what actually exists today)

**Stack**
- **Backend:** Python **FastAPI**, async streaming via `httpx`.
- **Models (all local via Ollama):**
  - chat → **`qwen3:14b`** (~9 GB, fits fully on the 4070)
  - reflection → **`qwen3:4b`** (unloaded right after each use so it doesn't
    crowd VRAM)
  - embeddings → **`nomic-embed-text`** (768-dim)
  - "Thinking" (Qwen3 `<think>` reasoning) is **disabled by default** for direct
    replies and clean reflection output; a `thinking: true` config flag re-enables it.
- **Storage:** **SQLite** (conversations, messages, memories).
- **Frontend:** a single **vanilla HTML/CSS/JS** web app (responsive, PWA-installable),
  redesigned to the **NERO Design System** (light, violet, floating, calm) with a
  ChatGPT-style two-button voice composer and a hands-free conversation-mode screen.
- **Access:** local network + Tailscale (device-only; no app login).
- **Setup:** one-command `bootstrap.py` (venv + deps + pulls all 3 models + launch).

**Identity & behavior** (built from config into the system prompt each turn)
- Name Nero (she/her, tolerant of name variants), owner Toni, personality.
- **Goals** and **principles** she weighs decisions against.
- **Confidence-based answering** ("I know" / "I think…" / "I'm not sure").
- **Bilingual** — auto-detects English/Croatian per message and replies in kind.
- **Humor dial** (0–100, TARS-style, adjustable live in the UI).

**Memory (this is now real, not a stub)**
- **Typed memories** (semantic · episodic · preference · experience · procedural),
  each with **confidence, importance, timestamp, source, entities, embedding,
  last-reinforced**. Safe schema migration for older DBs.
- **Retrieval:** ranks by **confidence × time-decay × relevance**; relevance is
  semantic (cosine over `nomic-embed`) when embeddings are comparable, else a
  lexical/recency fallback — always on one comparable scale. Only the top-k most
  relevant memories are injected into the prompt.
- **Decay:** unreinforced memories fade (half-life); recalled/repeated ones are
  reinforced toward confidence 1.
- **Reflection:** after each exchange, a background pass (small model, `think=false`)
  extracts durable facts, **dedupes** against existing memories (text + embedding),
  and reinforces or adds. Writes are serialized (lock) to avoid duplicate races.
- **Voice:** a **local neural English voice** (Kokoro via ONNX Runtime) speaks
  her replies in the app, falling back to the browser voice for Croatian or when
  unavailable; barge-in (a new message/mic cuts her off); mobile audio unlock so
  replies play on phone/tablet. Input via browser STT (EN/HR) — needs an HTTPS
  origin off-localhost (Tailscale `serve`), so the mic works on phone/tablet;
  iPhone can also use the native **Siri Shortcut**.
- **Observability:** `GET /api/metrics` exposes retrieval latency + counts.

**World Model (continuity — Phase 2, new)**
- A small, structured, always-current picture of what Toni's working on:
  **current project · task · working context · blockers · next steps · recent
  focus**, in a SQLite `world_state` key/value table.
- **Updated in the background** after each exchange (small model, `think=false`,
  reflection model unloaded after) — the LLM returns only the fields that
  changed as JSON; parsing is hardened (tolerates prose/fences, drops truncated
  `<think>` guesses, collapses values to a single safe line).
- **Read into the system prompt** before every reply, so she resumes *knowing
  where you left off*. The read is best-effort and off the event loop — a DB
  hiccup degrades to "no continuity block", never breaks the chat.
- `GET /api/world` (inspect) · `DELETE /api/world[/{key}]` (owner reset) ·
  `world` counters in `/api/metrics` · `world_model_enabled` config switch.

**Quality process (per the Directive)**
- A **verification framework** — `python verify/verify_everything.py` runs
  `verify_{gpu,ollama,config,memory,world_model,embeddings,reflection}.py`; each
  subsystem ships its own check. Offline checks are green in CI; GPU/Ollama
  checks pass on the owner's PC.
- Hardened by **four adversarial multi-lens reviews** (foundation, memory,
  Windows setup, world model) — ~29 real issues caught and fixed before merge.
- On the RTX 4070: config, gpu, ollama, memory, embeddings, and world_model
  logic all green. `verify_reflection` stored 0 memories — live diagnostics
  revealed the real cause: **qwen3:4b ignores `think=False` and reasons in plain
  prose** (no `<think>` tags), rambling 4000+ chars and never reaching the JSON.
  Fixed by constraining output with **Ollama's structured-output `format`** (a
  JSON schema), which makes prose grammatically impossible. Applied to *both*
  reflection and the world model (same model, same latent bug — the world would
  silently never have updated on a real machine), and added a **live
  end-to-end world-model verify** (the offline-only check had masked it).
  Re-verify on the owner's PC is pending before merge.

**Repo layout**
```
bootstrap.py · start.bat/.sh · run.py · config.example.yaml
app/  main.py · config.py · db.py · memory.py · world_model.py · llm.py · prompt.py · tts.py · static/
app/  security/gate.py · capabilities/{registry,builtin/git_status}.py · agent/{loop,state}.py   # Phase 1 (PR #10)
verify/  verify_*.py           docs/  CONSTITUTION · adr/ · ROADMAP · DESIGN-phase1 · VISION · PROJECT_BRIEF · …
tests/   test_*.py             PROGRESS.md
```

## 4. Known gaps / not built yet

- **Knowledge graph** — memories store `entities`, but they aren't yet *connected*
  into a graph.
- **No Insight Engine** — she remembers, but doesn't yet synthesize patterns.
- **Tools / planner / skills — foundation shipped & verified on the PC (PR #10).**
  The **agent loop + Capability Registry + security gate + Executive Memory** are
  live, with read-only capabilities `git.status` + `fs.read` (jailed, bounded;
  adding the second needed zero agent-loop changes — the registry's whole point).
  Verified end-to-end on the 4070:
  a real qwen3:14b drove the loop via `git.status`, the security battery gated 32
  unconfirmed dangerous attempts (0 escapes), and Executive Memory observed the
  real git branch. Still to come this phase: more read-only capabilities
  (`fs.list`, `git.log`) then the human-in-the-loop terminal; the
  Approve/Deny confirmation UX lands with the first MEDIUM+ capability (until then
  MEDIUM+ actions are safely denied). No planner/skills yet (later phases).
  Computer control rides on this foundation.
- **No proactivity / desktop sensing** — purely reactive.
- **Single active conversation thread** (multi-conversation not built).
- **Retrieval is a linear scan** over SQLite (fine at current scale; no vector DB yet).
- **Observability is minimal** (`/api/metrics`); no dashboard.
- **Voice** — the *local neural English voice* (Kokoro) now speaks her replies in
  the chat UI, on desktop and phone/tablet. Still to come: **local STT**
  (faster-whisper) to replace the browser's cloud speech recognition, the
  **real-time loop** (continuous listen, voice-driven barge-in, <1s latency), and
  **Croatian** TTS (Meta MMS-TTS).

## 5. Roadmap

> The authoritative, measurable plan now lives in
> [ROADMAP.md](ROADMAP.md) (governed by [CONSTITUTION.md](CONSTITUTION.md) +
> [the ADRs](adr/README.md)). This section is the friendly summary.

- ✅ **Done:** v0.1 foundation · Phase 1 (identity: goals/principles/confidence +
  the full memory subsystem) · **Phase 2 (World Model / continuity)** · the
  cognitive loop is now wired (perceive → retrieve → update world model → reply
  → reflect → learn) · Development Directive + verification framework · Qwen3
  defaults · thinking disabled.
- 🔜 **Next (owner's chosen order):**
  1. **Real-time voice agent** (in progress). ✅ Increment 1 — local neural
     English voice (Kokoro via ONNX Runtime, no PyTorch, Python 3.13), verified
     8/8. 🔨 Increment 2 (in review, PR #9) — that voice now plays in the chat UI
     (`/api/speak`), with graceful fallback to the browser voice for Croatian or
     when unavailable (incl. iOS autoplay), plus barge-in. Next: local STT
     (faster-whisper), the real-time loop (continuous listen, <1s latency), and
     Croatian (Meta MMS-TTS).
  2. **Phase 1 — "The Hands"** (the committed foundation): agent/tool loop +
     **Capability Registry** + **Executive Memory** + **security gate (built
     first)** + human-in-the-loop terminal. This is what unlocks acting at all —
     and **computer control** (a *local "Cowork"*: see the screen, drive
     mouse/keyboard, act in real apps with hard safety rails) rides directly on
     it. Starts on a clean `main` once PR #9 merges.
  3. ✅ **Design System v1.0 applied** to the live frontend (in PR #9, pulled
     forward alongside the voice work): light/violet redesign, two-button
     composer, conversation-mode orb, responsive + iPhone safe-area.
- 🗓️ **Then:** intent router + thought budget · **Experience Engine** (workflows,
  not just facts) · knowledge-graph connections · **Insight Engine** (Second Brain)
  · observability dashboard.
- 🗓️ **Later (opt-in, local):** desktop sensing + proactivity + attention ·
  browser intelligence · multi-agent · digital twin.

## 6. Open questions where outside advice is most valuable

1. **World model tuning** — now built as a 6-field key/value picture, updated by
   a background LLM step returning changed-fields JSON. Is that the right shape,
   or should it carry structure (nested tasks, timestamps, confidence per field)?
2. **Continuity mechanics** — beyond the live world model: session summaries, a
   "since we last spoke" digest, decay of stale world fields?
3. **Knowledge graph** — how to connect memories (entities/relations) so it's
   genuinely useful; when to graduate from a linear scan to a vector DB.
4. **Insight Engine** — how often to run pattern-analysis, and how to surface
   insights without becoming noisy.
5. **Reflection tuning** — is a 4B model good enough at extraction? Dedup
   thresholds? Should importance/confidence be model-set or heuristic?
6. **Proactivity on Windows** — a safe, private way to sense context (active app,
   files, GPU) + an attention/importance model that helps without nagging.
7. **Voice** — is **Piper** the right local, low-latency, female (Croatian-capable)
   neural voice? Best way to stream it.
8. **Evaluation** — for a *personal* companion, how do we tell if a change makes
   her genuinely better / more "alive"?
9. **Over-engineering check** — the two highest-ROI next steps, and what to cut.

---

*Maintenance note: refresh this brief at the end of each phase so it always
reflects reality — it's the fastest way to onboard a human or an AI advisor.*
