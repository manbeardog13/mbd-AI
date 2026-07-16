---
id: spec.skill-lifecycle
title: Nero Skill Lifecycle
layer: core
type: spec
status: proposed
owner: shared
version: 1.0.0
created: 2026-07-16
updated: 2026-07-16
sources:
  - School/SCHOOL_RULES.md
  - School/SHARED_WORK_RULES.md
  - skills/nero-continual-learning/SKILL.md
  - skills/nero-continual-learning/references/algorithm.md
  - docs/adr/0015-evidence-gated-dual-host-cognition.md
  - docs/CONSTITUTION.md
related:
  - docs/adr/0018-skill-lifecycle.md
  - docs/canon/KNOWLEDGE_STANDARD.md
verified_by: verify/verify_nero_school.py, verify/verify_nero_learning_hybrid.py, verify/verify_nero_software_skill.py
---

# Nero Skill Lifecycle

How a capability becomes, remains, and stops being part of Nero. Applies to
repo skills (`skills/*`, `.claude/skills/*`) and to School-trained
competencies. Cowork/marketplace plugins are external and out of scope.

## Skill anatomy (required to enter the lifecycle)

Every skill is a directory with:

- `SKILL.md` — frontmatter (`name`, `description`, plus lifecycle fields below)
  and complete instructions. Boundaries stated in the skill itself.
- `references/` — supporting protocol/algorithm docs (optional but preferred
  over one giant SKILL.md).
- A **verification hook** — a `verify/verify_nero_<skill>.py` script or a named
  deterministic check the skill can be graded against.
- A **regression suite** — the minimal set of checks that must stay green for
  the skill to remain routable. May be the verify script plus recorded
  adversarial cases.

Lifecycle frontmatter (added to `SKILL.md`):

```yaml
version: 1.0.0        # semver
lifecycle: candidate | experimental | permanent | quarantined | retired
owner: shared | claude-lane | codex-lane
verified_by: verify/verify_nero_<skill>.py
```

## States

| State | Meaning | Routing |
|---|---|---|
| **candidate** | Written to standard; untested claims | Never routed; may only be exercised inside its evaluation |
| **experimental** | Passed evaluation once; evidence from limited contexts | Explicit invocation only — Toni names it, or a task explicitly selects it. Never auto-routed by capsule/AGENTS text |
| **permanent** | Multi-context evidence; regression suite green; Toni approved | Routable: capsules, AGENTS.md, and routing references may point to it |
| **quarantined** | A regression or violated boundary detected | Not routable; invocation must warn and requires Toni's override |
| **retired** | Superseded or removed | Moved to `docs/archive/skills/` with tombstone frontmatter (`superseded_by`) |

Status lives in frontmatter, not in directory moves, until retirement.

## Gates (transitions)

**→ candidate.** Entry requires: standard anatomy, no capability escalation
(inherits School safety: no permission grants, no confirmation bypass, no
credential exposure, no hidden-tool activation), and boundaries stated in the
skill text.

**candidate → experimental (Evaluation).** All of:

1. Deterministic checks pass (the verify hook, offline where possible).
2. An adversarial pass: the skill's stated refusals actually refuse
   (boundary-violation prompts recorded as cases in the regression suite).
3. Review: for **shared** skills, independent dual-host audit per School rules —
   deterministic grade and combined audit ≥ 8.7/10, no reviewer below 8.0,
   capped at three attempts. For **single-lane** skills, verify + Toni's
   acceptance substitute for the second host.

**experimental → permanent (Promotion).** All of:

1. **Multi-context evidence** (EGCSE rule): successful use in ≥ 2 genuinely
   distinct real tasks, with outcomes recorded — not one task family.
2. Regression suite green at the promoted version.
3. A decision record: entry in the skill's changelog + one line in
   `docs/adr/` **only if** the skill changes an architectural boundary;
   otherwise the changelog suffices.
4. **Toni's explicit approval** — promotion changes what routes by default,
   which is a publication-class act.

**any → quarantined (Regression).** Automatic on: a regression-suite failure, a
boundary violation in the wild, or an EGCSE regression-quarantine trigger. The
skill stays on disk, stops being routable, and the failure becomes a new
regression case before any fix is evaluated.

**quarantined → experimental.** Fix lands; the *extended* regression suite
passes; re-evaluation per the candidate→experimental gate (lighter review
allowed if the fix is narrow and the original audit stands).

**any → retired.** Superseded or obsolete: move to `docs/archive/skills/`,
set `lifecycle: retired`, `superseded_by: <id>`; routing references updated in
the same change. Rollback of a bad promotion = `git revert` of the promoting
change + quarantine of the reverted version + a regression case documenting why.

## Versioning

Semver, enforced by review:

- **PATCH** — fix; regression suite must pass unchanged.
- **MINOR** — new capability; regression suite must be *extended* to cover it.
- **MAJOR** — contract change (inputs, boundaries, refusals): full
  re-evaluation (candidate→experimental gate) before it can hold
  `permanent` again.

Every version change updates `version`, `updated`, and the changelog section.

## Permanent vs experimental — the distinction that matters

**Permanent** skills are part of Nero's identity surface: capsules and host
instructions may route to them, and a fresh model may trust them as canon.
**Experimental** skills are opt-in tools: nothing in always-loaded context may
reference them as available behavior. This keeps the always-on context small
(ADR-0014) and makes every default behavior an *evidenced* behavior.

## Relationship to School XP

School departments measure **host competence** (evidence-gated XP via
`schoolctl.py finalize`). Skills are **artifacts**. A School task may produce
or exercise a skill, and its audit may serve as the skill's evaluation
evidence — but XP ledgers and skill lifecycle states are separate records, and
neither may be edited directly (School rules govern the former; this spec the
latter).

## Current inventory and assigned states (initial classification)

| Skill | Evidence today | Assigned state |
|---|---|---|
| `skills/nero-software-engineering` | verify script; routine real-task use | **permanent** |
| `skills/nero-hybrid-cognition` | verify script; ADR-0015 accepted; live dual-host round pending | **permanent** (watch item: live proof) |
| `skills/nero-continual-learning` | verify script; ADR-0015 accepted | **permanent** |
| `.claude/skills/nero-continuity` | 36 adversarial tests + verify; ADR-0016; live Claude recall proven; Codex live cert pending | **permanent**, with ADR-0016's "pending live Codex verification" carried in its changelog |

Adding the lifecycle frontmatter to these four SKILL.md files is a
MIGRATION_PLAN Phase B item (their files are currently untouched by this audit).

## Changelog

- 1.0.0 (2026-07-16) — Initial spec, aligned with School gates and EGCSE.
