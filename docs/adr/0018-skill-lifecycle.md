# ADR-0018: Skill lifecycle — evidence-gated promotion, versioning, rollback

**Status:** Proposed (Toni's acceptance promotes; drafted by Claude lane)
**Date:** 2026-07-16

## Context

Nero's capabilities increasingly live as skills (`skills/*`,
`.claude/skills/*`), but no rule said how a skill becomes trusted, what keeps
it trusted, or how it is demoted. Meanwhile School (evidence-gated XP,
deterministic grading, dual audits ≥ 8.7) and EGCSE (multi-context evaluation,
regression quarantine) already define exactly the right gating machinery — for
tasks and lessons, not for skills. Without a lifecycle, every skill is
effectively permanent the moment it's written, and capsule/AGENTS routing text
can reference unproven behavior.

## Decision

Adopt `docs/specs/skill-lifecycle.spec.md`:

1. States: **candidate → experimental → permanent**, with **quarantined** and
   **retired**; state lives in SKILL.md frontmatter.
2. Evaluation reuses existing gates: deterministic verify hook + adversarial
   boundary cases; shared skills additionally take the School-style dual-host
   audit (≥ 8.7 combined, no reviewer < 8.0, three-attempt cap).
3. **Promotion to permanent requires multi-context evidence (≥ 2 distinct real
   tasks), a green regression suite, and Toni's explicit approval** — because
   permanent skills may be routed by always-loaded context, promotion is a
   publication-class act.
4. Only permanent skills may be referenced by capsules, CLAUDE.md, AGENTS.md,
   or routing references. Experimental skills are explicit-invocation only.
5. Semver: PATCH = fix (suite passes), MINOR = extension (suite extended),
   MAJOR = contract change (full re-evaluation).
6. Any regression or boundary violation auto-quarantines: the skill stops
   being routable and the failure becomes a permanent regression case.
   Rollback = git revert + quarantine of the reverted version.

## Consequences

- Default (routable) Nero behavior is always evidenced behavior; always-loaded
  context stays small (ADR-0014) and honest.
- Skill authorship gains overhead: verify hook + regression suite are entry
  requirements, not afterthoughts.
- School XP and skill states remain separate ledgers; a School audit may serve
  as promotion evidence but never edits lifecycle state by itself.
- The four existing skills receive initial states (spec §inventory) via a
  Phase B migration edit.

## Alternatives considered

- **Directory-based states** (`skills/experimental/…`): rejected — moves break
  references and history; frontmatter is cheaper and diff-friendly.
- **Fold lifecycle into School XP:** rejected — XP measures host competence,
  not artifact trustworthiness; conflating them corrupts both ledgers.
- **No formal lifecycle (review-on-write only):** rejected — that is the
  status quo that made every skill de facto permanent at birth.
