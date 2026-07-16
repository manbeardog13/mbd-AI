# Nero Roadmap

**Charter:** the authoritative, measurable plan. Increment log:
[PROGRESS.md](../PROGRESS.md) · snapshot: [PROJECT_BRIEF.md](PROJECT_BRIEF.md).
Phase *names* are canonical; numbers are era-bound.

The current phases, their dependencies, and the **measurable** bar each must
clear before the next begins. Governed by [CONSTITUTION.md](CONSTITUTION.md) and
the [ADRs](adr/README.md). Each phase ends with working software + tests +
benchmarks + a `verify_*.py` + docs. No half-finished experiment crosses a phase
boundary.

**Legend:** ✅ shipped · 🔨 building · ⏭️ next · 🗓️ planned

---

## Done / in flight (pre-V3)
- ✅ Local chat (Ollama), streaming, bilingual EN/HR, TARS humor dial, PWA.
- ✅ Layered typed **memory** + reflection; **World Model** (continuity).
- ✅ **Voice out** — local neural TTS (Kokoro/ONNX), sentence-chunked, iOS Web Audio.
- 🔨 UI redesign (NERO Design System) + two-button voice composer + conversation
  mode — **PR #9, awaiting merge**. *(Merge this before starting Phase 1 so the
  agent-loop work begins on a clean base.)*

---

## Phase 1 — The hands (foundational; nothing proactive without this)
**Build:** agent/tool loop · **Capability Registry** (capabilities, not hard-coded
tools) · **Executive Memory** (working-state register) · **security gate
(first)** · observability · human-in-the-loop persistent terminal.
**Depends on:** ADR-0003, ADR-0005, ADR-0001, ADR-0007, ADR-0008. Detailed
design: [DESIGN-phase1.md](DESIGN-phase1.md).
**Success criteria (measured):**
- Nero completes a 3-step tool task end-to-end (e.g. *"what changed in this repo?"*
  → `git.status` → `fs.read` → summarize) with **0 unconfirmed medium+ actions**.
- Every `medium`/`high`/`critical` tool call is blocked pending confirmation in a
  test suite of ≥20 adversarial prompts — **100% gated, 0 escapes**.
- **Capability Registry:** the model's tool list is generated from the registry
  (no hard-coded list); a capability registered at runtime is callable with no
  loop change; **every** dispatch passes through the gate + metrics (a capability
  cannot execute without authorization — proven by test).
- **Executive Memory:** after a multi-step task the register holds the correct
  `project`/`branch` (observed, verified against `git`), and a fresh session reads
  `goal`/`task`/`next_action` from it instead of reconstructing them.
- Terminal round-trip (propose → approve → run → observe) works for PowerShell;
  Nero reads stdout/stderr/exit/cwd/git without manual copy-paste.
- `/api/metrics` reports per-stage + per-tool timings; overhead of the loop
  scaffolding (excl. inference) **< 50 ms/step**.
- `verify_agent.py`, `verify_capabilities.py`, `verify_executive_memory.py`,
  `verify_security.py`, `verify_terminal.py` green on the PC.

## Phase 2 — Seeing, doing, and knowing where we are
**Build:** browser engine (Playwright, DOM-first, vision fallback best-effort) ·
**Workspace** — *extends Phase-1 Executive Memory (ADR-0008)* with richer live
state: dev-server ports, docker ps, active-window title, last terminal output ·
**Executive Planner** (minimal, OFF by default; reads Executive Memory) ·
**semantic cache**.
**Depends on:** Phase 1 (all are tools/consumers of the loop) · ADR-0002/0005.
**Success criteria:**
- *"Continue."* resumes with the correct project/branch/task **with no
  reconstruction**, from Executive Memory + Workspace + World Model.
- Browser tool completes a scripted navigate→extract on 5 real sites; vision
  fallback used only when DOM extraction fails, and that's logged.
- Semantic cache: 3 paraphrases of one deterministic query resolve to one result;
  freshness rules verified (stale entries invalidate).
- Executive Planner runs **only** idle, only cheap deterministic prep, is
  **instantly preemptible**, and is **disableable with one toggle** — proven by a
  test that foreground latency is unaffected while it runs.

## Phase 3 — Getting personal and staying fast
**Build:** Experience Engine + **Skills** (reusable, editable, composable
workflows that run *through* the agent loop + security gate) · Resource
Orchestrator (psutil + NVML; pause bg on foreground) · Task Scheduler
(priorities; user preempts bg) · incremental indexing.
**Depends on:** Phase 1–2 · ADR-0002.
**Success criteria:**
- A Skill ("Fix React project") runs its steps via the loop with every `medium`+
  step confirmed; editable and re-runnable.
- Under synthetic GPU/CPU load, background jobs pause and **foreground turn
  latency stays within 10% of idle** (measured).
- Re-indexing touches only changed files (verified by a timing test: unchanged
  corpus → near-zero work).

## Phase 4 — Voice, vision, ecosystem, proactivity
**Build:** real-time voice loop (VAD, wake word, faster-whisper STT, streaming
barge-in) · on-demand vision (VLM by eviction) · advanced planning · MCP
ecosystem (2–3 daily connectors) · proven speculative prep.
**Depends on:** Phase 1–3 · ADR-0002/0004.
**Success criteria:**
- Hands-free conversation on desktop with **<1.2 s** to first spoken token and
  working barge-in.
- MCP: 2 real servers mounted; their tools flow through the same security gate.
- Any speculative prep ships **only** with a measured hit-rate that beats its
  cost; misses never degrade foreground latency.

---

## Explicitly deferred / non-committal (do not pay for these with abstraction now)
Multi-PC orchestration · distributed inference · cloud sync · mobile/wearable
apps · smart-home-as-driver. These are a *horizon*, not architecture inputs — no
Phase 1–4 decision may be justified by them (Constitution §5).

## Research-flagged (label as experiments, never as reliable features)
Speech **emotion detection** · fine **prosody** control · screenshot→click
**vision grounding** on small local VLMs · fully **autonomous** (unconfirmed)
terminal. Ship these only if a benchmark proves them; otherwise they stay opt-in
experiments.
