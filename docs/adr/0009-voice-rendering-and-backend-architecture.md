# ADR-0009 — Voice Rendering Profiles and Pluggable Voice Backend Architecture

**Status:** **Proposed** (2026-07-12; revised 2026-07-13) — *not* approved, introduces *no* implementation.
This document is a design proposal only. Nothing in the running system changes as a result of merging it. It exists to be argued with, revised, or rejected before any code is written. The 2026-07-13 revision addresses eight review findings while preserving the ADR's original philosophy: measurement first, Migration Stage 1 remains the correct current state, no premature abstraction, no implementation commitment.

**Scope reality check:** the components named below (`voice/manager/*`, `RenderingProfile`, `VoiceCasting`, `TTSEngine` contract, `RealKokoroBackend`, cast/profile JSON, engine health, event bus, health report) **do not exist in this repository at time of writing.** Every reference to them is *future-state.* Where an idea depends on a design detail that has not been decided yet, it is marked **[Future decision]**.

---

## Context

### Current reality (measured, 2026-07-12)

- Nero's local voice is a single file: `app/tts.py`. It exposes exactly two functions to callers: `available(cfg) -> bool` and `synthesize(cfg, text) -> bytes | None`. Consumers are `GET /api/voice` (status) and `POST /api/speak` (synthesize) in `app/main.py`. `GET /api/metrics` surfaces `tts.METRICS`.
- The engine is a module-level `Kokoro` instance behind a `_lock`, lazily constructed on first synth, cached for the process lifetime (`app/tts.py:38–89`). One instance per process, serialized under a re-entrant lock.
- Configuration is flat in `Config` (`app/config.py`): `tts_enabled`, `tts_engine` (default `"kokoro"`), `tts_voice` (default `"af_heart"`), `tts_speed`, `tts_model_dir`. **`tts_voice` is an engine-specific Kokoro voice ID stored in the top-level app config** — this is the concrete coupling ADR-0009 addresses.
- Stage 13.5 Phase 1 measurements on the RTX 4070:
  - Kokoro synthesizes real audio, RTF ≈ 0.25, warm avg 0.98 s for a 3.9 s clip, cold post-download 2.4 s.
  - **VRAM impact = 0 MiB**: the installed `onnxruntime` (1.27.0) is the CPU wheel; Kokoro executes entirely on CPU, consistent with ADR-0002 ("Speech stays off the GPU: Kokoro TTS on ONNX/CPU").
  - All six planned NERO voice IDs (`af_heart`, `af_bella`, `af_nicole`, `af_sarah`, `am_adam`, `am_michael`) are present in `voices-v1.0.bin` alongside 48 others across 10 languages.

### The forces driving this ADR

- **Primary driver — language and engine diversity that is roadmap-committed.** Croatian via **Meta MMS-TTS** is committed in `docs/PROJECT_BRIEF.md` (§4 Voice, §5 Roadmap) and Phase 4 real-time voice work in `docs/ROADMAP.md`. That is the *first* concrete second engine on the map, and it will collide with the current single-file, single-cache, engine-baked-into-config design.
- **Persona and engine are conflated in config today.** `tts_voice: "af_heart"` is simultaneously "Nero's identity" *and* a Kokoro shard address. Changing engines would either invalidate the config or force the same value to mean different things — a class of bug ADR-0007 already avoided for tools ("capabilities, not hard-coded implementations").
- **Secondary hypothetical — multiple personas.** No committed roadmap item introduces a second persona. If it ever arrives, the abstraction proposed below happens to accommodate it; this is a *possible* benefit, not a driver. Justifying the refactor on multi-persona alone would be premature.
- **Nothing in the roadmap yet forces this refactor to start today.** Extending `app/tts.py` in place remains a legitimate stance until Croatian MMS-TTS is scheduled on a phase plan. This ADR must not become a justification for premature abstraction — the trigger for Stage 2 is a *scheduled* second engine, not the mere aspiration of one.

### What this ADR is *not* trying to solve

- Not a spec for the real-time voice loop (VAD, wake word, streaming barge-in — Phase 4).
- Not a redesign of `POST /api/speak` (the outer HTTP contract is unaffected).
- Not a commitment to introduce cast/profile JSON files — see **[Future decision]** notes below.

---

## Proposed architecture

A **thin seam**, mirroring the Capability Registry pattern of ADR-0007: one narrow contract between "who is speaking" and "how audio is produced," and one guarded dispatch. Every engine plugs into the same seam and inherits the same observability and health surface, unbypassably. No plugin framework, no dependency-injection container, no dynamic loading — just a registry and an interface, matching the Least-Intelligence discipline the Constitution and ADR-0007 already apply to our own architecture.

```
Chat turn / /api/speak text
         │
         ▼
   RenderingProfile      ← who is speaking, in what language, in what mood
         │                (abstract persona intent — no engine IDs)
         ▼
    VoiceCasting         ← "for this profile + this engine, use these params"
         │                (the single place engine-specific knowledge lives)
         ▼
    TTSEngine contract   ← the neutral interface every backend satisfies
         │
    ┌────┴────┬─────────────┐
    ▼         ▼             ▼
  Real     Real          Future
  Kokoro   MMS-TTS       backends
  Backend  Backend
```

### 1. `RenderingProfile` — persona intent, not implementation

A **RenderingProfile** describes *how a persona should sound* in engine-neutral terms. It represents rendering intent, nothing more.

**Committed fields (map to real engine parameters today):**
- `persona_id` — stable identity, e.g. `"nero"`, `"guest"`.
- `language` — BCP-47 code, e.g. `"en-US"`, `"hr-HR"`. See the language-routing rule below.
- `speed` — relative playback rate around 1.0 (portable across engines).

**Reserved — not shipped, no consumer today:**
- Expressive style dimensions (`style`, `warmth`, `arousal`, `formality`, etc.). Kokoro has no style knobs; these fields would be inert. They are *defined only* when a backend that consumes them is added — e.g., an expressive/cloning engine under a future ADR. Do not ship reserved fields on `RenderingProfile` in advance of a real consumer.

**Language-routing ownership (decided).** The **application layer** determines the language of the utterance (using the existing bilingual detection in `app/prompt.py` / `app/main.py`) and passes it into the `RenderingProfile`. The voice layer **never** runs its own language detection — that would duplicate logic, add an LLM call to the synthesis path, and violate the Principle of Least Intelligence (Constitution §3).

**Invariant:** a `RenderingProfile` MUST NOT reference an engine-specific voice ID, model file, or backend name. If a proposed field would only be meaningful to one engine, it belongs in `VoiceCasting`, not here. This is the single load-bearing invariant of the abstraction: a persona must be describable without knowing which engine will render it.

**[Future decision]** whether profiles live in code, in a `profiles.json` under `data/`, or hydrate from `config.yaml`. This ADR does not commit to a storage medium — that call belongs to whichever migration stage first introduces a second persona.

### 2. `VoiceCasting` — the persona-to-engine translator

**VoiceCasting** is the *only* place that knows how to translate a `RenderingProfile` into concrete engine parameters. If Nero's `RenderingProfile` says `persona_id="nero", language="en-US", speed=1.0`, `VoiceCasting` is where the mapping `(nero, en-US) → (kokoro, voice_id="af_heart", speed=1.0)` lives — and, when the second engine arrives, where `(nero, hr-HR) → (mms_tts, speaker_id=…, ...)` lives too.

**Rule:** engine-specific knowledge belongs here and nowhere else. `RenderingProfile` upstream must not know engine names; `TTSEngine` implementations downstream must not know personas.

**[Future decision]** whether the cast table lives in a `cast.json`, a code-level mapping, or is derived programmatically from engine capabilities. Storage medium is again deferred; the invariant is *where the responsibility lives.*

### 3. `TTSEngine` contract — the neutral interface

The `TTSEngine` contract is the surface every backend implements. Described in prose only; no code:

- **Identity** — a stable engine name (e.g. `"kokoro"`, `"mms"`).
- **Availability** — a cheap boolean (no model load) reporting whether the engine's dependencies and models are present. Analogous to `tts.available(cfg)` today.
- **Health** — a richer status (`ok` / `degraded` / `unavailable`) with a reason string, suitable for surfacing in a health report. Cheap to compute; must not synthesize.
- **Synthesis request** — inputs are `(text, engine_params)`. `engine_params` is the already-cast, engine-specific payload from `VoiceCasting`; the engine does not touch `RenderingProfile` directly.
- **Audio result** — WAV bytes plus metadata (`sample_rate`, `channels`, `duration_s`, `synthesis_ms`, `engine`, `voice_or_speaker_id`). The metadata is what feeds telemetry.
- **Lifecycle** — engines are constructed once (per process, not per request), may fail to initialize (surfaced via Availability/Health), and expose an explicit release/dispose for tests and shutdown.

**Why replaceable engines matter:** the roadmap commits Nero to Croatian (MMS-TTS). Adopting a neutral contract now means that engine *plugs in* when scheduled, rather than forcing a rewrite of `app/main.py` or `Config`. This is the same argument ADR-0007 made for the Capability Registry. Additional future engines (expressive/cloning, etc.) would benefit from the same seam but are not the driver.

**Scope — batch synthesis only (decided).** The current contract is a **batch synthesis** contract: text in, complete WAV bytes out, one utterance at a time. Phase 4's real-time voice loop (VAD, wake word, streaming barge-in, <1.2 s to first spoken token — see `docs/ROADMAP.md` Phase 4) will either **extend** this contract with a streaming surface or be governed by a **superseding Phase-4 voice-loop ADR**. Streaming is not designed here; treat the batch contract as the correct v1 for the migration stages this ADR governs, and expect a follow-on ADR to define the streaming surface when Phase 4 begins.

**Concurrency (decided).** The contract guarantees **serialized synthesis per engine instance**: one `synthesize()` call runs at a time per instance, matching the `_lock` behavior of `app/tts.py` today. Concurrent callers are serialized by the engine (or by a caller-side lock the engine documents). This preserves the current FastAPI + `asyncio.to_thread` invocation pattern unchanged. Parallel synthesis across *multiple* engine instances is permitted; parallel synthesis on the *same* instance is not part of the v1 contract and requires a superseding ADR if a future engine needs it.

**Error surface (decided).** On failure, `synthesize()` returns **`None`** (matching today's `bytes | None` return of `tts.synthesize`) and logs a warning; it does **not** raise. This preserves the existing `POST /api/speak` behavior (`return Response(status_code=204)` on `None`) unchanged during migration. Richer diagnostic information belongs on the Health surface, not on the per-call return. Exceptions inside a backend must be caught by the backend and translated to `None` + a log line — the caller must never see a stack trace from the voice layer.

**Reference-audio / cloning engines are out of scope (decided).** Engines that require reference audio as an input (Chatterbox-class cloning) do not fit the `(text, engine_params)` shape and are **not** governed by this ADR. When such an engine is added, a **superseding ADR** must define the payload / reference-audio model (opaque bytes slot, asset-registry lookup, or another mechanism). This ADR neither prevents nor pre-designs that.

### 4. Backend implementations

#### `RealKokoroBackend`

**Owns:**
- Kokoro-specific integration (`kokoro_onnx.Kokoro` construction, model + voices paths, `create(text, voice=…, speed=…, lang=…)` calls).
- Translating pre-cast `engine_params` into Kokoro's exact call signature.
- Producing audio + populating result metadata.
- Its own availability probe (`importlib.util.find_spec("kokoro_onnx") is not None`, model files present).

**Does not own:**
- Persona identity (that's `RenderingProfile`).
- The Kokoro voice ID for a given persona (that's `VoiceCasting`).
- HTTP orchestration or `/api/speak` semantics (that stays in `app/main.py`).
- Config loading.

**Instance ownership (this ADR resolves the Phase 1 review question):** **Option B — as a temporary migration bridge, not a permanent layering rule.** `RealKokoroBackend` reuses the existing cached `Kokoro` instance in `app/tts.py` rather than constructing its own. Rationale is measurement-driven, not convenience-driven:

- Model footprint is ~340 MB resident (`kokoro-v1.0.onnx` 310 MB + `voices-v1.0.bin` 27 MB). Duplicating it buys zero isolation on a single-process app.
- VRAM contention is a non-issue (measured ΔVRAM = 0 MiB), so an "isolate the engine to protect the GPU" argument does not apply here.
- The existing `_lock` in `app/tts.py` already serializes access correctly for a shared instance (see **Concurrency** in the TTSEngine contract, above).
- The seam that matters is the **contract** (TTSEngine), not the identity of who owns the underlying `Kokoro` handle *during migration*.

**Dissolution trigger (committed).** At the earlier of **Migration Stage 5** or the **first requirement for multiple independently configured Kokoro instances** (e.g., isolated per-persona rendering, per-language voice packs, or a test harness that needs an isolated engine), the shared Kokoro lifecycle **must be extracted** from `app/tts.py` into a lower-layer engine-ownership module. Both `app/tts.py` (during any remaining migration work) and `RealKokoroBackend` then become consumers of that lower-layer module, and the layering inversion introduced by Option B is resolved. **This is a written commitment, not a `[Future decision]`.** The lower-layer module is **not created now**; nothing in this ADR authorizes it, and it appears only when the trigger fires.

Until the trigger fires, `app/tts.py` is on a deprecation path — future voice work must not deepen its role beyond what already exists.

#### `RealMMSBackend` *(future, not this proposal's job to define)*

**Would own:**
- Croatian/local-language synthesis via Meta MMS-TTS.
- MMS-specific model loading, speaker configuration, phonemization for `hr` and other non-English targets Kokoro doesn't cover well.

**Would not own:**
- Persona identity or "which speaker corresponds to Nero in Croatian" — that's `VoiceCasting`.

**[Future decision]** whether MMS-TTS also stays on CPU (consistent with ADR-0002's "speech off the GPU" rule) or is granted GPU access. Absent measurements, CPU is the default.

---

## Boundary rules — what must not be casually touched

The following systems are load-bearing for other reasons (agent loop, security, executive state, hardware discipline). Any voice work that ends up needing to modify them **stops and files a superseding ADR**, per the ADR README's rule ("don't edit an Accepted ADR's decision — write a new ADR that supersedes it"):

- **Agent loop & Capability Registry** (`app/agent/*`, `app/capabilities/*`) — voice is not a capability the agent invokes as a tool. Do not add voice-rendering as a Registry entry; that would blur the ADR-0007 seam.
- **Security gate** (`app/security/gate.py`, ADR-0005) — voice output is `safe` by construction (read-only, no filesystem/network side effects on the user's machine beyond the response body). The gate stays out of the voice path unless a future engine acquires side effects.
- **Executive Memory** (`app/agent/state.py`, ADR-0008) — voice does not read or write executive state.
- **Startup / bootstrap** (`bootstrap.py`, `run.py`) — voice backends must not add mandatory dependencies to bootstrap. The current "voice is optional; the app runs fine without it" property (`requirements-voice.txt` separate from `requirements.txt`) is preserved.
- **Model router / VRAM budget** (ADR-0002) — Speech stays off the GPU. Any future engine that wants GPU access must first make its case in its own ADR against ADR-0002's budget math.
- **`POST /api/speak` HTTP contract** — the outer request/response shape (text in, `audio/wav` bytes or `204` out) does not change. Callers on the web frontend must be unaffected by anything under this ADR.
- **`/api/metrics.voice` shape compatibility (decided).** The existing `tts.METRICS` dict (`spoken`, `chars`, `last_ms`) surfaced via `/api/metrics.voice` is **preserved unchanged across all migration stages**. Any new metrics introduced by the rendering/casting layer or a second engine appear as **additional top-level keys** under `/api/metrics.voice` (e.g., `by_engine`, `by_persona`) — never by mutating the shape of the existing keys. The frontend that reads `/api/metrics` must continue to work without modification through every migration stage.

---

## Migration strategy (staged, each stage independently reversible)

Numbered as **Migration Stages** to avoid collision with the Roadmap's **Phases 1–4**. Each stage ends with the app in a shippable state; halting mid-migration is not a failure mode.

### Migration Stage 1 — Freeze in place (status quo). **This is where we are.**
- `app/tts.py` remains the single voice path.
- No new files, no new abstractions.
- **Exit condition to proceed to Stage 2:** Croatian MMS-TTS (or another second engine) is scheduled on a phase plan with a defined implementation window. General aspiration, hypothetical multi-persona support, or future expressive engines are not sufficient triggers.

### Migration Stage 2 — Introduce contracts *beside* the current implementation
- Add `TTSEngine` contract and `RenderingProfile` / `VoiceCasting` types as new modules **without** rewriting `app/tts.py`.
- `app/tts.py` is not deleted, moved, or refactored. Its public API (`available`, `synthesize`, `METRICS`) is unchanged.
- No callers are switched over. The abstractions exist but are unused; this stage is purely additive.
- **Validation gate before proceeding:** the audio-parity test suite (below) shows Stage 2 changes are inert.

### Migration Stage 3 — Introduce `RealKokoroBackend` as a thin adapter over `app/tts.py`
- Backend implements the `TTSEngine` contract by delegating to the existing `app/tts.py` engine cache — no second `Kokoro` instance.
- Still no caller change. The backend is registered but not the default path.
- **Validation gate:** audio output identical to Stage 1 (byte-for-byte where determinism allows; RTF and warm latency within measurement noise).

### Migration Stage 4 — Route `/api/speak` through Rendering → Casting → Backend
- `POST /api/speak` builds a `RenderingProfile` from config and application-layer state (persona from config, `language` passed in from `app/prompt.py`'s bilingual detection, `speed` from config). Reserved/expressive fields on `RenderingProfile` are **not** populated — they have no consumer.
- `Config.tts_voice` is **retained as a legacy override** for the duration of migration: if set to a Kokoro voice ID it takes precedence over the cast result, so an existing user's `config.yaml` keeps working during rollout.
- **`Config.tts_voice` sunset clause (committed):** it remains only while migration is in progress and is **removed on completion of Migration Stage 5**, once all production callers route through `VoiceCasting`. Removal is a documented breaking change in the changelog for the release that completes Stage 5 (with a migration note pointing users at `RenderingProfile` / `VoiceCasting`).
- **Validation gate:** existing single-persona behavior indistinguishable from Stage 1 on the golden phrase; `/api/metrics.voice` shape unchanged; all existing callers unaffected.

### Migration Stage 5 — Add additional engines
- Introduce `RealMMSBackend` (or Chatterbox, or another) as a second `TTSEngine`.
- `VoiceCasting` gains its second engine mapping.
- Only *now* do we validate cross-engine behavior (language routing, mixed transcripts).

**Each stage requires:** (a) explicit validation pass (below), (b) no changes to frozen boundaries, (c) rollback plan tested at least once.

---

## Validation strategy

Every stage above is proven with measurements, not assumed. The bar mirrors the Stage 13.5 discipline that produced the Phase 1 report.

- **Behavioral parity** — for a fixed golden phrase, generated WAV metadata (sample rate, channel count, duration, byte length within tolerance) matches the Stage 1 baseline. Byte-exact equality is *not* required — Kokoro output has run-to-run variance below the audible threshold — but structure and duration must match.
- **Latency** — warm-loop average latency must remain within +5% of the Stage 1 measurement (baseline: **0.983 s** for the 3.9 s test phrase). Above +5% is a regression that blocks stage promotion.
- **Real-Time Factor** — RTF must remain < 0.35 (baseline: **0.25**). A regression here is a synthesis-throughput regression, not a wrapper cost — investigate before promoting.
- **VRAM** — nvidia-smi `memory.used` before, during, and after synthesis must remain within noise of the Stage 1 baseline (**1707 MiB idle, ΔVRAM = 0 MiB**). Any measurable VRAM footprint from Kokoro would indicate an unintended `onnxruntime-gpu` switch — that requires its own ADR against ADR-0002 before it lands.
- **CPU** — cold-start CPU work should remain in the same order of magnitude as the baseline (cold ≈ 2.4 s post-download). Wrapper overhead per synth call, measured as a delta over `app/tts.py` direct call, must be **< 20 ms** — anything higher indicates a thick abstraction and gets pushed back.
- **`verify/verify_tts.py` remains green** on the RTX 4070 host at every stage. If the current cp1250 print bug is fixed, the fix is a separate change with its own review; this ADR does not require it.
- **Rollback rehearsal** — before promoting any stage past 3, a rehearsed revert (a single-commit revert plus a re-run of the parity + latency measurements) must be shown to produce identical numbers to the pre-promotion baseline. If revert doesn't reproduce the baseline, the change wasn't as isolated as claimed and the stage is not promoted.

---

## Risks and mitigations

- **Unnecessary abstraction / premature seams.** *This is the primary risk.* One engine, one persona, and one caller do not justify three interfaces. **Mitigation:** Stage 1 is *the current state*; Stages 2+ don't start until a second engine or persona is actually committed to a phase. If that never happens, this ADR remains Proposed forever, which is a valid outcome.
- **Over-engineering into a framework.** The temptation to build a plugin loader, DI container, or event-driven engine registry is exactly the trap ADR-0007 warns against. **Mitigation:** contract + one dispatch function + one registry (dict) — same shape as the Capability Registry. If a stage's PR grows beyond that, it's off-scope.
- **Duplicated model loading.** A second cached `Kokoro` instance would double resident memory for zero benefit given the CPU-only VRAM finding. **Mitigation:** the ownership decision above (Option B, reuse) makes this structurally impossible.
- **Breaking current voice behavior.** Any wrapper introduces a chance to corrupt sample bytes, mis-route language, or silently drop audio. **Mitigation:** parity + latency gates at every stage; `verify_tts.py` and the audible sample WAV as the physical ground truth.
- **Dependency growth.** New abstractions can drag in new packages (schema validators, config libs). **Mitigation:** the contract and profile types must be expressible with the standard library plus `pydantic` (already in `requirements.txt`). Anything else needs a separate case.
- **Maintenance cost.** Three thin files are still three more files to keep coherent than one thick file. **Mitigation:** the cost is only worth paying at the moment a second engine lands. If it doesn't land, the maintenance cost is never incurred.

---

## Alternatives considered

### Alternative 1 — Continue expanding `app/tts.py`
Extend the current single-file design as new engines are needed (add a second `_synth_*` function, an if-tree over `cfg.tts_engine`, and put MMS-TTS-specific speaker mappings directly in `Config`).
- **Pros:** simplest. Zero new files. Consistent with "prefer the smallest thing that works" (Constitution §3, Principle of Least Intelligence).
- **Cons:** every new engine adds a branch to a growing dispatch tree; persona/engine coupling in `Config` deepens; a Croatian speaker ID living next to `tts_voice: af_heart` is exactly the confusion this ADR wants to prevent.
- **Verdict:** legitimate *until* the second engine arrives. If MMS-TTS ends up deferred indefinitely (roadmap Phase 4), this is the correct answer and ADR-0009 stays Proposed. This alternative is a live default, not a straw man.

### Alternative 2 — Adopt the rendering / casting / backend abstraction (the proposal above)
- **Pros:** persona and engine become independently changeable; the second engine plugs into an existing seam without touching `app/main.py`, `Config`, or the frontend; the same discipline that made ADR-0007 pay for itself applies here.
- **Cons:** three more concepts to hold in your head; risk of premature complexity if the second engine doesn't land soon; measurement overhead per stage.
- **Verdict:** recommended *only when Croatian MMS-TTS (or another second engine) is scheduled on a phase plan with a date* — not on general aspiration. The migration stages exist precisely so this cost is paid incrementally, matched to actual need.

### Alternative 3 — External TTS services (ElevenLabs, PlayHT, Azure, etc.)
- **Pros:** currently best-in-class quality and multilingual coverage; no local model management.
- **Cons:** violates ADR-0006 ("Local-First with Intelligence Escalation" — cloud is opt-in, transparent, off by default) and the Constitution's privacy stance ("nothing leaves the machine"); adds network latency and reliability risk to a real-time voice loop; ongoing cost; a dependency on external availability for what is meant to be a personal, offline companion.
- **Verdict:** rejected as a default. Could conceivably appear later as an *explicit, per-request opt-in* backend under ADR-0006's escalation model — but that is a separate ADR, not this one.

---

## Consequences (if this ADR is later accepted)

- ✅ **Language and engine become separately evolvable** (primary driver): adding Croatian MMS-TTS doesn't touch `Config.tts_voice` (during migration) or `POST /api/speak`. Persona separability is a **secondary hypothetical** benefit that arrives free if it is ever needed.
- ✅ Adding a future engine (MMS-TTS) is a plug-in exercise, not a `POST /api/speak` rewrite. Reference-audio / cloning engines require a **superseding ADR**.
- ✅ The measurement discipline that produced trustworthy Phase 1 numbers is baked into every promotion gate — regressions are caught by the same tool that already exists (`verify_tts.py`) plus the parity test.
- ⚠️ Three files where there was one. Justifiable only when Croatian MMS-TTS is scheduled; kept in check by the "don't leave Stage 1 until you have to" rule.
- ⚠️ A new place for a bug to hide: the `RenderingProfile → engine_params` translation. Mitigation is the parity test at every stage.
- ⚠️ Option B introduces a **temporary layering inversion** (`RealKokoroBackend → app/tts.py`) that must be dissolved per the trigger in the RealKokoroBackend section. Failing to dissolve it on schedule converts a bridge into permanent debt.

---

## What this ADR does not commit to

- Any code change.
- Any file creation beyond this document.
- Any dependency change.
- Any change to `Config`, `POST /api/speak`, `/api/metrics` (shape), `verify/verify_tts.py`, `app/tts.py`, `bootstrap.py`, or any frozen boundary.
- The internal *shape* of engine-specific payloads (each backend owns its own).
- The storage medium for `RenderingProfile` (config, JSON, code) — deferred to the Stage-2 PR that first introduces persistent profiles.
- The storage medium for the `VoiceCasting` table (JSON, code, derived) — deferred to the same Stage-2 PR.
- The **streaming / real-time synthesis surface** — governed by a future Phase-4 voice-loop ADR (see TTSEngine contract, **Scope**).
- The **reference-audio / cloning-engine payload model** — governed by a future ADR when such an engine is added (see TTSEngine contract, **Reference-audio** subsection).
- Any lower-layer engine-ownership module — not created now; appears only when the Option-B dissolution trigger fires.
- Any expressive/style field on `RenderingProfile` — reserved; defined only when an engine consumes them.

Acceptance of this ADR would move it to `Status: Accepted` and unlock **the right to plan Migration Stage 2** work — nothing more, and only when Croatian MMS-TTS (or another second engine) has entered the roadmap as *scheduled* rather than aspirational.
