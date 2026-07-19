---
id: canon.structure
title: Canonical Repository Structure
layer: core
type: standard
status: proposed
owner: shared
version: 1.2.0
created: 2026-07-16
updated: 2026-07-18
sources:
  - docs/CONSTITUTION.md
  - docs/canon/AUDIT_REPORT.md
related:
  - docs/adr/0028-canonical-knowledge-base.md
  - docs/canon/KNOWLEDGE_STANDARD.md
  - docs/canon/MIGRATION_PLAN.md
---

# Canonical Repository Structure

Where every kind of knowledge lives in `D:\mbd AI`, and the rules that keep it
that way. Structure serves the guiding principle: **a new model must be able to
understand Nero entirely from this repo.**

## The three layers

| Layer | Definition | Change discipline |
|---|---|---|
| **core** | Identity, law, decisions, and boundary specs. What a fresh model must trust. | Rare, deliberate; ADR or amendment PR; status banners on supersession |
| **operational** | Current plans, state, guides, subsystem docs, skills, School. What's true *now*. | Freely updated; `updated` field current; owner respected |
| **archival** | Superseded or completed-dated material kept for the record. | Immutable except tombstone frontmatter |

Every markdown file belongs to exactly one layer, declared in frontmatter
(`layer:`). Archival never silently disappears — it moves to `docs/archive/`
with `status: archived` and, where applicable, `superseded_by`.

## Target tree

```
D:\mbd AI\
├─ README.md                  front door; points into docs/canon/
├─ CLAUDE.md · AGENTS.md      host contracts (lane-owned; small; point to canon)
├─ PROGRESS.md                operational increment log
│
├─ docs/
│  ├─ CONSTITUTION.md         core · the law
│  ├─ VISION.md               core · vision (historical roadmap table marked)
│  ├─ DIRECTIVE.md            core-historical · superseded philosophy (banner)
│  ├─ ROADMAP.md              operational · the authoritative plan
│  ├─ PROJECT_BRIEF.md        operational · living snapshot / handoff
│  │
│  ├─ canon/                  the knowledge system itself
│  │   README.md              onboarding entry point (read-order contract)
│  │   INDEX.md               generated master index (script, not by hand)
│  │   KNOWLEDGE_STANDARD.md  metadata · index · changelog policy
│  │   CANONICAL_STRUCTURE.md this file
│  │   AUDIT_REPORT.md        dated audits of the knowledge base
│  │   ARCHITECTURE_REVIEW.md dated architecture reviews
│  │   PROXIMA_DEPENDENCY_REPORT.md  dependency reports
│  │   MIGRATION_PLAN.md      the executable path from here to target
│  │
│  ├─ adr/                    decisions — the WHY (existing; unchanged format)
│  ├─ specs/                  implementation contracts — the WHAT
│  │   memory-architecture.spec.md
│  │   skill-lifecycle.spec.md
│  │   <subsystem>.spec.md    (grow as subsystems get contracts)
│  │
│  ├─ host/                   capsules + host-mode docs, lane-paired
│  │   (GLOBAL_CAPSULE, CLAUDE_GLOBAL_CAPSULE, CODEX_MEMORY, CODEX_RUNTIME,
│  │    HOST_VOICE, TAUGHT_KNOWLEDGE, INTEGRATIONS, COUNCIL…)
│  ├─ guides/                 user-facing how-to (SETUP, ALWAYS_ON,
│  │                          REMOTE_ACCESS, VOICE_AND_SIRI, MODELS†)
│  ├─ persona/                textual voice law (Voice Bible, mined patterns,
│  │                          golden corpus - ADR-0022)
│  ├─ handoffs/               engine-handoff artifacts Toni keeps (ADR-0020)
│  ├─ visual/                 Manbeardog system (internally layered: bible=law,
│  │                          derived profiles, ops docs; absorbs docs/roadmap/)
│  ├─ mobile/                 mobile presence experience
│  ├─ reviews/                dated evaluations (archival once their decision
│  │                          is extracted into an ADR)
│  └─ archive/                superseded docs, dated handoffs, retired skills
│      design/ · handoffs/ · skills/
│
├─ continuity/                continuity ledger subsystem (code + README)
├─ skills/                    Nero skills (lifecycle per skill-lifecycle.spec)
├─ .claude/ · .codex/         lane-owned host config + lane skills
├─ School/                    self-governed (SCHOOL_RULES; two-host protocol)
├─ audit/<initiative>/        evidence bundles (pattern is canon — keep)
├─ verify/                    the verification spine (verify_*.py)
├─ app/ presence/ familiar/ voice/ scripts/ tests/   code
└─ data/ models/ output/ _nero_preview/              runtime, gitignored
```

† `MODELS.md` is already marked historical in-file; it archives once its
inbound links (bootstrap, configs, SETUP, VISION, README) are repointed.

### Repository-governance extension (v1.2)

The target tree also includes `.github/` for remote review/CI assets,
`.githooks/` for local mechanical safety, `governance/` for machine-readable
policy, `docs/repository/` for Git/reconciliation rules, and
`docs/orchestration/` for the orchestrator program. These boundaries are added
without moving the working application tree in one big-bang rewrite.

## Placement rules

1. **Decisions → `docs/adr/`.** One page, why-shaped, superseded by successor
   ADRs, indexed in `docs/adr/README.md`. Never edit an accepted decision.
2. **Contracts → `docs/specs/`.** `<subject>.spec.md`, what-shaped: interfaces,
   data models, invariants, acceptance criteria. A spec cites its ADRs.
3. **The knowledge system → `docs/canon/`.** Standards, generated index,
   dated reports, migration plans.
4. **Anything superseded → `docs/archive/`** with tombstone frontmatter. Root
   and `docs/` root never accumulate dead documents.
5. **Lane ownership is structural.** `.codex/**` and `docs/*CODEX*` are
   Codex-lane; `.claude/**` and the Claude capsule are Claude-lane; `School/`
   is shared under its own protocol. Cross-lane edits are handoffs, not edits.
6. **Runtime dirs stay out of knowledge.** `data/`, `models/`, `output/`,
   `_nero_preview/` are gitignored artifacts; docs may reference, never live in
   them.
7. **Binary documents don't carry canon.** Knowledge is markdown + plain text
   (School's `.docx` brief is grandfathered until School migrates it under its
   own protocol).
8. **New names are kebab-case.** Existing names survive until their planned
   migration step; renames always travel with inbound-link fixes in the same
   change.
9. **Repository policy is code.** Human rules live in `docs/repository/`;
   machine policy lives in `governance/`; GitHub enforcement assets live in
   `.github/`; local mechanical hooks live in `.githooks/`. None of them grants
   publication authority.

## The documentation hierarchy (traceability chain)

```
Vision        docs/VISION.md — what Nero is trying to become
Principles    docs/CONSTITUTION.md — non-negotiable law
Decisions     docs/adr/ — why we chose what we chose
Contracts     docs/specs/ — what exactly must hold
Implementation app/ · continuity/ · presence/ · voice/ · familiar/ · scripts/
Tests         tests/ · verify/ — proof on the real PC
Skills        skills/ · .claude/skills/ — validated, promoted capabilities
```

Every level cites the level above it; nothing below contradicts anything above
it. When it does, the lower document is wrong — or an amendment is proposed.

## Changelog

- 1.2.0 (2026-07-18) - Add repository governance and orchestration program
  boundaries without moving the working application tree.

- 1.1.0 (2026-07-17) — Tree gains docs/persona/ and docs/handoffs/.
- 1.0.0 (2026-07-16) — Initial standard, from the Phase 1 audit.
