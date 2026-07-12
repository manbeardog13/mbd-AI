# The Nero Constitution

*The stable foundation. This document changes rarely and deliberately. Features,
roadmaps, and implementations serve these principles — not the other way around.
When a proposal conflicts with the Constitution, the proposal changes.*

Version 1.0 · supersedes the philosophy sections of DIRECTIVE.md, VISION.md, and
the V1–V3 directives (those remain as vision/history; this is the law).

---

## 1. What Nero is

Nero is a **local-first cognitive assistant** that runs entirely on Toni's own
PC. She is not a chatbot and she is not a distributed platform. She is a
**modular monolith**: one application, one process where practical, one
debugger — with clearly separated modules behind strict interfaces.

The language model is **one component**, not the whole of Nero. Any model must be
replaceable with minimal effort.

The goal is a specific *feeling*: working beside an experienced engineer who
understands the goal, remembers context, reasons before acting, chooses the right
tool automatically, protects you from mistakes, and feels instant.

## 2. The pillars, in priority order

When principles conflict, the higher one wins.

1. **Reliability** — she never corrupts data, never takes a destructive action
   without consent, and degrades gracefully instead of failing catastrophically.
2. **Privacy / local-first** — nothing leaves the machine by default. Cloud is
   opt-in, off by default, and consciously chosen (see ADR-0006).
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
- **Don't reason when you can know.** Retrieval, deterministic code, filesystem,
  git, SQL, and cached results come before invoking the LLM. The LLM reasons; it
  does not replace software.
- **One resident model.** A single primary model stays loaded; everything else
  (vision, a larger model, speech) is loaded on demand at an honest, visible
  latency cost. Never promise hot, concurrent, multi-model routing on 12 GB.
  (ADR-0002)
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
- **The local PC is the source of truth.** No subsystem is "done" until it
  verifies itself there (`verify/verify_*.py`) and ships with tests, benchmarks,
  logging, metrics, and docs.
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
