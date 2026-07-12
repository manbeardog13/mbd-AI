# ADR-0003 — The agent/tool loop is the core execution primitive

**Status:** Accepted

## Context
Today Nero is **single-shot text**: `/api/chat` streams one model reply and stops.
She cannot take a single action. Every "hands" capability the vision wants —
terminal, browser, filesystem, parallel fan-out, plugins, skills — is blocked on
the *same* missing primitive: the ability to call a tool, observe the result, and
continue reasoning. None of those capabilities needs an event bus or a service
split; they need a loop.

## Decision
Implement an in-process **agent loop** behind the chat path:

```
reason → decide (tool call?) → execute tool → observe result → reason again → … → answer
```

- A **tool registry**: each tool is a typed interface (name, JSON-schema args,
  a risk class per ADR-0005, and an `execute()` that returns structured output).
- The model is offered the tools (via native tool-calling / a structured
  protocol); the loop runs the chosen tool, feeds the observation back, and
  repeats until the model produces a final answer or a step limit is hit.
- Bounded: max steps, max wall-clock, and cancellable — the loop can always be
  stopped, and background/foreground preemption applies (ADR-0002 / Scheduler).
- Tools requiring confirmation pause the loop for human approval (ADR-0005).

## Consequences
- ✅ One primitive unlocks terminal, browser, fan-out, skills, and plugins.
- ✅ Stays in-process and synchronous-to-reason-about; fully observable
  (every step is a metric + a trace).
- ⚠️ A small local model can loop poorly (wrong tool, no stop). Mitigations: tight
  tool schemas, step/time budgets, deterministic tools that "know" instead of
  guess, and starting with 1–2 safe read-only tools before adding power.

## Alternatives considered
- **Per-capability bespoke endpoints** (a terminal API, a browser API, …) —
  rejected: duplicates orchestration, doesn't compose, can't do multi-step tasks.
- **External agent framework** — deferred: adds a heavy dependency and hides
  control flow; a small, owned loop is more debuggable and fits the monolith.
