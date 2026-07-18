---
id: spec.engine-handoff
title: Engine Handoff - Implementation Prompt Emission
layer: core
type: spec
status: proposed
owner: shared
version: 1.0.0
created: 2026-07-17
updated: 2026-07-17
sources:
  - docs/adr/0020-identity-plane-and-engine-handoff.md
related:
  - docs/canon/KNOWLEDGE_STANDARD.md
---

# Engine Handoff — Implementation Prompt Emission

The contract for the artifact Nero emits at the end of a design/build
conversation so any engine (Claude, Codex, GPT, future) can execute the result
with **no manual cleanup** (ADR-0020).

## Trigger

Toni asks for it ("emit the handoff", "give me the prompt"), or a design arc
concludes and Nero offers it. Never emitted silently.

## Artifact structure (exact section order)

1. **Header** — task name, date, target engine, one identity line ("Nero,
   emitted for <engine> execution").
2. **Architecture summary** — what exists and what changes; compact prose,
   target under ~20 lines; cites canon paths (specs, ADRs), never the chat.
3. **Extracted decisions** — numbered; each with its one-line *why*; reference
   ADRs where they exist, propose ADR stubs where they should.
4. **Constraints and boundaries** — the non-negotiables the executor inherits:
   security gate, lane ownership, memory-plane rules, verify hooks, School
   protocol where applicable.
5. **Ready-to-paste prompt** — one fenced block, fully self-contained: role,
   task, inputs by repo path, exact acceptance checks, stop conditions. Must
   stand alone with zero references back to the emitting conversation.
6. **Acceptance checks** — deterministic where possible (verify scripts,
   tests, link checks); named human judgments where not.

## Rules

- Self-containment is the bar: if the target engine would need the transcript,
  the emission failed.
- Cite repository truth (canon paths, ADR numbers), never conversation memory.
- Never include secrets, credentials, transcripts, or provider-internal
  details.
- Persistence: emitted in-chat by default; stored to
  `docs/handoffs/<date>-<slug>.md` when Toni wants it kept (that directory is
  part of Phase B structure).
- The handoff names its target engine but must be executable by any competent
  engine - engine-specific flags go in section 4, not woven through the prompt.

## Visual + UI tokens (for Mission Control / frontend work)

- Colors: **Nero = violet** (existing NERO Design System violet), **Claude =
  warm amber**, **Codex = ice blue**; future engines get assigned cool neutrals
  until decided. Exact values land with the Design System implementation.
- Speaker rule: the UI shows **Nero speaking**; engine, model, and lane appear
  in an optional details panel, honestly labelled (claimed, not attested,
  where that distinction applies).

## Acceptance criteria (for implementing this spec)

- A handoff emitted for a real task is executed by a fresh engine session with
  zero clarifying questions attributable to missing context.
- A reviewer can trace every decision in section 3 to canon or to a proposed
  ADR stub.
- UI implementation renders speaker/engine per the tokens above.

## Changelog

- 1.0.0 (2026-07-17) — Initial contract (from Toni's directive, ADR-0020).
