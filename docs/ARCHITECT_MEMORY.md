# Nero — Architect Memory

**This is the project's long-term architectural memory and the single entry point
for repository-specific context.** Read it before architectural work on Nero;
ordinary hosted conversation does not preload it.

> **Documentation is the project's memory. Conversations are only discussions
> about that memory.** No part of Nero depends on any AI conversation. If a new
> session starts weeks or months from now, it must rebuild an accurate
> understanding of the project *from this repository alone*.

Toni's current instruction and the Constitution take precedence. After those,
current repository evidence outranks stale conversational history or dated
summaries; update this document deliberately when the architecture changes.

This document changes **rarely and deliberately** (it holds the *stable* memory).
Volatile status — what's shipped, in flight, or next — lives in the living docs it
points to, so this file does not drift.

---

## 0. Task-scoped procedure — rebuild project context from the repo

Before a repository-specific architectural decision or implementation, review
only the relevant items below (when present), in this order:

1. **`docs/ARCHITECT_MEMORY.md`** — this file (vision, principles, rules, standards, the map).
2. **`docs/PROJECT_BRIEF.md`** — the current honest snapshot (what exists today, gaps).
3. **`PROGRESS.md`** — what's shipped / in review / next.
4. **`docs/CONSTITUTION.md`** — the law (philosophy + pillars + engineering laws).
5. **The ADRs** — `docs/adr/` — *why* each significant choice was made.
6. **The `DESIGN-*` doc** for the subsystem in play — `docs/DESIGN-phase1.md`,
   `docs/DESIGN-action-journal.md`, `docs/VOICE.md`, etc.
7. **The current implementation** of that subsystem (the actual code).
8. **The existing tests** for it (`tests/`, `verify/`).
9. **The latest commits** touching it (`git log --oneline` on the relevant paths).

Only after this scoped evidence review should implementation begin. Host
Presence must not execute a SessionStart hook or preload repository context just
because a hosted task opened (ADR-0014).

---

## 1. Project vision & North Star

**Nero** is a **local-first cognitive companion** (she/her). Her standalone
application runs on Toni's own PC (Windows 11 · RTX 4070 12 GB · 64 GB RAM),
private and offline, reachable over Tailscale. Hosted Claude/Codex interfaces
are explicit execution or presentation adapters; they do not silently receive
the standalone application's private databases. She is bilingual (English +
Croatian), has a TARS-style humor dial, and a voice.

**North Star: continuity.** She should wake up already knowing what Toni was doing
and quietly help without being asked — growing from "a chatbot" into an assistant
that *feels like an experienced engineer beside you* who remembers, reasons before
acting, chooses the right tool automatically, protects you from mistakes, and
feels instant.

*Depth:* [`VISION.md`](VISION.md).

## 2. Engineering philosophy

- **Trustworthy before powerful.** Capability and accountability grow *together*;
  Nero does not become autonomous before she becomes accountable
  (Knowledge → Understanding → Capabilities → Trust → Accountability → Action →
  Autonomy). Do not skip rungs.
- **No feature aquarium.** Impressive features that collapse the ecosystem are the
  enemy. Prefer the smallest correct foundation; challenge scope before building.
- **The Principle of Least Intelligence.** Solve with the simplest deterministic
  mechanism that's correct; invoke the LLM only when it genuinely adds value.
  *Don't reason when you can know* — read the git branch, don't ask the model.
- **The local PC is the source of truth.** Nothing is "done" until it verifies
  there (`verify/verify_*.py`) with tests, benchmarks, logging, metrics, docs.
- **Measure, don't assume.** Especially performance and hardware — measured
  results always take precedence; cloud never fabricates hardware validation.
- **Strangler-fig, never big-bang.** Add beside the working system; switch on only
  after it's verified. Delete working code only once its replacement is proven.
- **Elegant over clever.** The simpler, more debuggable, more modular solution.

*Law:* [`CONSTITUTION.md`](CONSTITUTION.md).

## 3. Non-negotiable principles

- **Pillars, in priority order** (higher wins on conflict): **Reliability →
  Privacy/local-first → Perceived speed → Intelligence → Autonomy →
  Extensibility/maintainability.**
- **Privacy:** nothing leaves the machine by default. Cloud reasoning is
  *escalation* — explicit, opt-in, off by default, announced when used (ADR-0006).
- **Safety is a dependency, built first:** every action has a risk class;
  `MEDIUM`+ requires human confirmation — no exceptions; destructive actions are
  never silent (ADR-0005).
- **Accountability is immutable:** meaningful actions are recorded on an
  append-only chain of custody; Nero cannot rewrite her own history, edit her own
  gate, or disable her own safety systems (self-governing paths).
- **No unattended destructive loops.** Human-in-the-loop for anything with teeth.

## 4. Architectural rules

- **Modular monolith** — one process, strict interfaces; extraction into a service
  is *possible* later, never *required* now (ADR-0001).
- **Three explicit surfaces:** zero-start hosted identity (ADR-0014), the dormant
  standalone local application, and the manually launched authoritative Core /
  Mission Control (ADR-0017). None silently starts another.
- **Nero Core owns orchestration:** measured Git state, tasks, repository-global
  leases, approvals, and events are deterministic Core records. Claude and Codex
  are replaceable workers returning bounded, normalized results; neither owns
  identity, memory, scheduling, Git truth, or push authority.
- **The executive control layer (Track A)** is one trust boundary, met at the
  single dispatch choke point, in this order, unbypassably:
  **Capability Registry** (*what can I do?* — ADR-0007) → **Trust Engine / security
  gate** (*am I allowed?* — ADR-0005) → **Action Journal** (*what did I do, and can
  I prove it?* — `docs/DESIGN-action-journal.md`). New capability = a registration,
  not a loop change. Nothing bypasses all three.
- **The agent/tool loop** is the core execution primitive (reason → tool → observe
  → repeat, bounded, never hangs — ADR-0003). Every capability is a *tool* behind
  it, not a new service.
- **Model-independent Core; one resident local model** when the standalone app
  runs. Larger/vision/speech models swap in on demand at an honest, visible
  cost; hosted workers are explicit bounded escalations (ADR-0002, ADR-0017).
  MCP is the plugin standard (ADR-0004).
- **Voice (Track B) is an output interface only.** It presents responses produced
  by the Brain and **never** touches the executive path — no dispatch, no
  authorize, no Journal entries, no execution, no cognition. Voice telemetry ≠ the
  Journal. The engine is replaceable; the personality is not. (`docs/VOICE.md`.)
- **Two independent tracks** (A: Executive Intelligence; B: Voice Platform) never
  depend on each other's internals. *The Brain produces a response; the Voice
  presents it.*
- **API-first:** every major subsystem defines and documents its public contract
  *before* implementation; future components depend on interfaces, not
  implementations.

## 5. Design standards (house style — match the existing code)

- `from __future__ import annotations`; type hints; small, focused modules.
- Best-effort boundaries that **never break the user's work**:
  `except Exception:  # noqa: BLE001 - contained; …` — degrade gracefully.
- Storage layer (`app/db.py`) is pure SQLite primitives; cognition sits above it
  (`memory.py`, `world_model.py`, `journal.py`). Self-contained per file (duplicate
  a tiny helper rather than over-abstract).
- `METRICS` dicts + `/api/metrics` for observability (the registry counts capability
  metrics centrally; a subsystem owning backend state may keep its own).
- Every subsystem ships **tests** (`tests/test_*.py`, self-running via `_run()`)
  **and** a `verify/verify_*.py` on the **exit-code contract: 0 = pass · 2 = skip
  (dep/hardware absent) · other = fail**, auto-discovered by
  `verify/verify_everything.py`. Fully offline where possible; skip (2) when a dep
  (Ollama, git, a model, a GPU) is absent.

## 6. Review & verification standards

- **Incremental, one coherent PR at a time**; each stage stops with a
  **verification report**: measurable performance results · regression report ·
  architectural summary · git-diff summary · performance metrics · hardware
  measurements (when applicable). *Verification precedes expansion.*
- **PR isolation:** one subsystem per branch/PR, each with its own verification
  report and an independent rollback point. Do not mix unrelated subsystems.
- **Adversarial security review** on the diff before merging anything with teeth
  (the pass that caught the confirmation-UX XSS and the self-governing-path gaps).
- **Challenge before building:** if a request adds unnecessary complexity,
  conflicts with the hardware, or creates future debt, propose the better path
  *first* — while preserving the goal.

## 7. Current status — *see the living docs (do not duplicate here)*

This section is intentionally a pointer, so it never goes stale:

- **What exists / what's next:** [`PROGRESS.md`](../PROGRESS.md).
- **Full honest snapshot + gaps:** [`docs/PROJECT_BRIEF.md`](PROJECT_BRIEF.md).
- **The phased plan + measurable exit gates:** [`docs/ROADMAP.md`](ROADMAP.md).
- **Decisions + reasoning:** [`docs/adr/`](adr/README.md).

At the time of writing, the shipped foundation is: local chat + layered memory +
World Model + local neural voice + the NERO Design System UI; the V3 governance
layer; and **Phase 1 "The Hands" first slice** (agent loop · Capability Registry ·
security gate · Executive Memory · `git.status` · `fs.read`), verified on the 4070.
In flight on their own branches: the **Action Journal** (Track A) and the **Voice
Platform** (Track B). *Confirm specifics against PROGRESS/PROJECT_BRIEF — those are
authoritative, not this paragraph.*

## 8. Known technical debt (kept honest)

- **No CI in the repo** — verification runs manually / on the local 4070. A
  `verify_*` GitHub Action is a candidate.
- **SQLite connection-per-operation** (`app/db.py` opens a fresh connection per
  call). Fine at current scale, but it dominates write latency (~4–5 ms/write
  measured in the cloud box, mostly connection open) — revisit before the Action
  Journal is on a hot path (background/pooled write for the SAFE best-effort path).
- **Brief divergence across isolated branches** — `PROJECT_BRIEF.md` is edited on
  each feature branch, so it needs reconciliation when branches merge to `main`.
- **Core coordination is not shipped yet.** Until Milestone 1 is verified,
  Claude/Codex work remains manually coordinated. Afterward, exactly one
  Nero-managed writer may hold the repository-global lease; this does not lock
  out unrelated manual Git clients.
- **Phase-1 gaps still open:** `fs.list` / `git.log` not built; the non-streaming
  `/api/agent` auto-denies `MEDIUM`+ until the confirmation UX (streaming Approve/
  Deny) ships; the terminal and `fs.write` are later, gated PRs.

## 9. Upcoming milestones & long-term goals

- **Near term:** Action Journal Stages 2–7 (Track A); Voice foundation Stages 2–10
  then engine bodies (Track B); then the confirmation UX and the human-in-the-loop
  terminal. Detail + measurable gates: [`docs/ROADMAP.md`](ROADMAP.md).
- **Horizon** (a *direction*, not architecture inputs — do not pay for these with
  abstraction now): richer continuity, the Experience Engine + Skills, proactivity,
  real-time voice, on-demand vision, an MCP ecosystem. See ROADMAP's deferred list.

## 10. Living documentation (a standing rule)

When a milestone completes or an architectural decision changes, **update the
docs in the same work**: `PROGRESS.md`, `docs/PROJECT_BRIEF.md`, this file (only
for *stable* changes), the relevant ADR, and the relevant `DESIGN-*`. Implementation
and documentation evolve together — that is how the repository stays the memory. A
Stop hook nudges when `PROJECT_BRIEF.md` falls behind the source.

---

*This file is the constitution's index and the project's durable memory. Amend it
deliberately; keep volatile status in the living docs it points to.*
