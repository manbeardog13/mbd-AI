# The Nero Constitution

*The stable foundation. This document changes rarely and deliberately. Features,
roadmaps, and implementations serve these principles — not the other way around.
When a proposal conflicts with the Constitution, the proposal changes.*

Version 1.2 · supersedes the philosophy sections of DIRECTIVE.md, VISION.md, and
the V1–V3 directives (those remain as vision/history; this is the law).
*v1.1 (2026-07-12): adopted the Principle of Least Intelligence (§3); confirmed
ADR-0006 as "Local-First with Intelligence Escalation."*
*v1.2 (2026-07-15): established the model-independent authoritative Core and
the boundary between local control, hosted presence, and replaceable hosted
workers (ADR-0017).*

---

## 1. What Nero is

Nero is a **local-first cognitive assistant** whose authoritative project state,
private memory, approvals, and orchestration remain on Toni's own PC. She is not
a chatbot and she is not a distributed platform. She is a **modular monolith**:
one explicitly launched control plane, one process where practical, one
debugger — with clearly separated modules behind strict interfaces.

Hosted presence may express Nero's identity without starting the local control
plane. Hosted Claude, Codex, or future engines may execute explicitly disclosed,
bounded tasks as replaceable workers; they never become Nero's authority and do
not receive private local context by default.

The language model is **one component**, not the whole of Nero. Any model must be
replaceable with minimal effort.

The goal is a specific *feeling*: working beside an experienced engineer who
understands the goal, remembers context, reasons before acting, chooses the right
tool automatically, protects you from mistakes, and feels instant.

## 2. The pillars, in priority order

When principles conflict, the higher one wins.

1. **Reliability** — she never corrupts data, never takes a destructive action
   without consent, and degrades gracefully instead of failing catastrophically.
2. **Privacy / local-first** — nothing leaves the machine by default. Local is
   the default path; cloud reasoning is an *escalation* that is explicit, opt-in,
   off by default, and transparent when used ("Local-First with Intelligence
   Escalation" — ADR-0006).
3. **Perceived speed** — she feels instant. Most of that is architecture, not a
   bigger model: don't reason when you can *know*; don't block on the GPU.
4. **Intelligence** — accept the local model's real ceiling; win on continuity,
   memory, and tools rather than raw brainpower.
5. **Autonomy** — she prepares and acts on her own, *within* the security gate.
6. **Extensibility & maintainability** — a solo maintainer + an AI pair must be
   able to understand, debug, and extend every part of her, for years.

## 3. Engineering laws

- **Modular monolith.** One deployment. Modules communicate through defined
  interfaces; no module reaches into another's internals. Extraction into a
  service must be *possible* later, never *required* now. (ADR-0001)
- **The Principle of Least Intelligence.** Always solve a problem with the
  *simplest deterministic mechanism* that produces the correct result; invoke LLM
  reasoning only when it genuinely adds value. Retrieval, deterministic code,
  filesystem, git, SQL, and cached results come first — *don't reason when you
  can know.* The LLM reasons about the genuinely ambiguous; it does not replace
  software that can be right by construction. This applies to Nero's own
  architecture too: prefer the thin, knowable mechanism over the clever one
  (e.g. read the git branch, don't ask the model for it).
- **Model-independent Core; one resident local model.** Core owns deterministic
  state and policy, not a model. When the standalone local application runs, a
  single primary local model stays loaded; larger, vision, or speech models load
  on demand at an honest, visible cost. Hosted workers are explicit bounded
  escalations, not resident local routing. (ADR-0002, ADR-0017)
- **The agent/tool loop is the core primitive.** Reason → choose tool → execute →
  observe → repeat. Every capability (terminal, browser, plugins) is a *tool*
  behind that loop, not a new service. (ADR-0003)
- **Every action has a risk class, and dangerous actions require confirmation —
  no exceptions.** The security gate is a dependency of the tools, built before
  them, not after. (ADR-0005)
- **Strangler-fig, never big-bang.** New capability is added as a module beside
  the working system and switched on only after it's verified on the real PC.
  Working code is deleted only once its replacement is proven. We do not rewrite
  what works without a measured benefit.
- **Measured state is the source of truth.** No subsystem is "done" until it
  verifies on the local PC (`verify/verify_*.py`) and ships with tests,
  logging, metrics, and docs. Local Git state is read directly; remote Git state
  is authoritative only after a successful fetch and is always named with its
  exact branch/upstream relationship.
- **Elegant over clever.** Prefer the simpler, more modular, more debuggable
  solution. Feature count is not the measure of success; the feeling in §1 is.

## 4. How we work

- **Incremental, verified PRs.** One coherent change at a time, each runnable and
  verified on the PC before the next. No half-finished architectural experiments
  cross a phase boundary.
- **Decisions are recorded.** Every significant architectural choice gets an ADR
  (`docs/adr/`) explaining *why*, so future contributors extend the reasoning
  instead of unknowingly undoing it.
- **Challenge before building.** If a request adds unnecessary complexity,
  conflicts with the hardware, or creates future debt, propose the better path
  *before* writing code — while preserving the goal.

## 5. What Nero will not become

- A microservice mesh, an event-bus distributed system, or anything that trades
  away a single debuggable stack trace for architecture-astronaut points.
- A cloud service, or anything that sends Toni's data off the machine by default.
- An unattended agent that runs destructive commands without a human in the loop.
- A pile of features that impress in a demo and rot in maintenance.

---

*Amending this document is a deliberate act: open a PR titled "Constitution
amendment", state what changes and why, and reference the ADR that motivates it.*
