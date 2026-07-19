# ADR-0024: The Identity Evolution Charter — Seven Pillars, Identity Review, North Star

**Status:** Accepted (charter authored by Toni, 2026-07-17; adoption structure by Claude lane)
**Date:** 2026-07-17

## Context

One day after the Presence & Continuity Directive, Toni extended it with the
Identity Evolution Charter (docs/IDENTITY_EVOLUTION_CHARTER.md, verbatim):
presence is a symptom; the objective is stable identity emerging from
mutually reinforcing long-term systems. The charter defines Seven Pillars as
permanent research programs, a monthly Identity Review, a four-question
Design Rule, and a North Star — "a user should never have to wonder which
Nero they're speaking to."

## Decision

1. **The charter is core canon**, Toni-owned, senior to the directive it
   extends (the directive's research lists remain operative, nested chiefly
   under Pillar IV).
2. **The program restructures under the Seven Pillars.**
   `docs/persona/PRESENCE_PROGRAM.md` v2 carries per-pillar assets,
   initiatives, and gaps — empty pillars stay visibly empty rather than
   padded.
3. **The Identity Review is a monthly ritual** with dated reports in
   `docs/persona/identity-reviews/`; scores are labeled judgment, trends
   require a written *why*, and Review #0 (baseline) runs on adoption day.
4. **The Design Rule gates initiative graduation:** an experiment is kept
   only if its record answers the four questions.
5. **Character emerges, never invented:** Pillar VII answers are derived
   from accumulated decisions with citations (first derivation in Review
   #0) and remain stable unless intentionally revised by Toni.
6. **The North Star joins the onboarding surface** (canon README) and is
   staged as a Constitution amendment for Toni's PR:

   > Proposed addition to CONSTITUTION.md §1: *"A user should never have to
   > wonder which Nero they're speaking to — across time, surface, engine,
   > or embodiment, the same underlying intelligence must be recognizable.
   > Architectural decisions are evaluated against this."*

## Consequences

- Identity work becomes reviewable on a cadence, with drift caught by
  ritual rather than by accident; the pillars stop feature sprawl by
  forcing every addition to name what it strengthens.
- Cost: monthly reviews take real effort; a skipped month is itself a
  signal and gets recorded, not hidden.
- Character derivation constrains improvisation: what she admires or
  refuses must trace to the record, which is slower and far more durable
  than invention.

## Alternatives considered

- **Fold the charter into ADR-0023 silently:** rejected — Toni's escalation
  from presence to identity is itself a decision worth its own record.
- **Numeric-only reviews:** rejected — the charter names the why as more
  important than the score.
- **Invent Character answers now for completeness:** rejected explicitly by
  the charter; emergence with citations or nothing.
