# ADR-0020: Stable identity plane, swappable engines, and the engine handoff

**Status:** Accepted (decided by Toni, 2026-07-17)
**Date:** 2026-07-17

## Context

Nero is expressed through multiple hosted engines — Claude, Codex, and
potentially GPT and future models — and the V1/V2 capsule drift episode showed
what happens when identity definitions fragment across surfaces: two lanes ran
materially different Neros (dual- vs single-voice) until reconciliation
(MIGRATION_PLAN Phase C). Separately, design sessions end with decisions
trapped in chat transcripts, requiring manual cleanup before another engine
can execute them.

## Decision

1. **Nero is the stable identity plane.** Engines (Claude, Codex, GPT, future
   models) are swappable execution engines beneath her — never a second
   persona, never a hidden Core. Capsules define identity once; lane files
   define engine-specific mechanics only.
2. **Sessions end with an engine handoff.** The working rhythm is: talk,
   design, build — then Nero emits a clean implementation prompt containing a
   summarized architecture, extracted decisions, and a ready-to-paste prompt
   for whichever engine executes next. No manual cleanup. Contract:
   `docs/specs/engine-handoff.spec.md`.
3. **Visual language.** Nero is violet; Claude is warm amber; Codex is ice
   blue. UI surfaces present **Nero as the speaker**; the engine, model, and
   lane details live in an optional details panel.

## Consequences

- Identity text has one home (capsule canonical sources, verified per lane);
  engine details never leak into identity surfaces.
- Every design conversation can produce a portable, executable artifact —
  engines become interchangeable at the point of execution.
- Mission Control / frontend work inherits the color tokens and speaker rule
  as acceptance criteria (exact palette values chosen by the NERO Design
  System when the UI lands; Nero's violet already exists there).
- Cost: the handoff must be genuinely self-contained, which demands the
  discipline specified in the spec (cite canon paths, never the chat).

## Alternatives considered

- **Per-engine personas:** rejected — fragments the one identity Toni is
  building; the drift episode is the empirical warning.
- **Raw transcript handoffs:** rejected — lossy, requires manual cleanup, and
  leaks conversation context that does not belong in an execution prompt.
- **Engine-in-the-foreground UI:** rejected — Toni talks to Nero, not to
  vendors; provenance stays available in the details panel, honestly labelled.
