---
id: canon.audit-report-2026-07-16
title: Knowledge Base Audit — 2026-07-16
layer: operational
type: report
status: active
owner: shared
created: 2026-07-16
updated: 2026-07-16
sources:
  - full-repo inventory (206 md files, hashed + heading-clustered)
  - inbound-reference map (grep, all file types)
  - git worktree state on branch claude/rescue-dirty-worktree-20260715
related:
  - docs/canon/MIGRATION_PLAN.md
  - docs/canon/ARCHITECTURE_REVIEW.md
---

# Knowledge Base Audit — 2026-07-16

Phase 1 of the canonical knowledge base mission: every markdown, prompt, spec,
roadmap, and workflow inventoried; duplicates detected; merges proposed; gaps
identified. Auditor: Claude lane (Fable). Method: full-file md5 for exact
duplicates, heading/title clustering for overlap, `grep -rl` inbound-reference
mapping for every merge/move candidate, primary-source deep reads for all core
documents.

**Worktree caveat:** the audit ran on branch
`claude/rescue-dirty-worktree-20260715` with ~176 modified/untracked entries
and a stale `.git/index.lock`. Findings reflect on-disk state, which is ahead
of the last commit. No modified file was altered by this audit.

## Inventory summary

| Area | md files | Character |
|---|---|---|
| `School/` | 111 | Self-governed training environment (85 of them templated task packs) |
| `docs/` | 67 | Governance, host mode, subsystem docs, reviews, visual system |
| `skills/` + `.claude/skills/` | 15 | Four skills with references |
| root | 5 | README, CLAUDE, AGENTS, PROGRESS, NERO_HANDOFF |
| other (`voice/ presence/ audit/ verify/ continuity/`) | 8 | Subsystem READMEs + audit bundle |
| **Total** | **206** | plus prompts in `app/prompt.py`, School task contexts, and `docs/visual/manbeardog_prompt_system.md` |

## Exact duplicates

One set, wholly inside School: 14 × 3 identical template READMEs
(`Task_001/README.md`, `Sub_Tasks/README.md`, `NEXT_TASK_TEMPLATE/README.md`
per department — 42 files, md5-identical per kind). **Verdict: by design**
(each task pack ships its guide). *Proposal, School-governed:* generate packs
from one template source so a wording fix is one edit, not fourteen. Requires
the shared-work protocol; not executed by this audit.

## Overlap clusters and verdicts

**C1 · Governing philosophy — CONSTITUTION vs DIRECTIVE vs VISION.**
Constitution v1.1 explicitly supersedes the philosophy sections of DIRECTIVE
and VISION, yet DIRECTIVE still opens as governing ("every decision defers to
it") and carries a **different priority order** (7 items, UX last) than the
Constitution's six pillars. VISION also carries its own roadmap table that
half-duplicates ROADMAP.md. A fresh model reading DIRECTIVE or VISION first
inherits the wrong law. **Verdict: keep all three (history matters), add
supersession banners + frontmatter, and strip authority language from the
superseded sections.** (Migration Phase A.)

**C2 · Project state — PROGRESS vs PROJECT_BRIEF vs ROADMAP.**
Three documents each partially describe "where things stand." They also carry
the **phase-numbering collision**: pre-V3 numbering ("Phase 1 identity, Phase
2 world model" — both shipped) coexists with V3 numbering ("Phase 1 The Hands"
— in review), sometimes in the same file (PROJECT_BRIEF §5). **Verdict: keep
three docs with sharpened jobs — ROADMAP = the plan, PROGRESS = increment log,
PROJECT_BRIEF = current snapshot/handoff — and rename phases to names, not
numbers ("The Hands"), with a one-line legacy-numbering note.** (Phase A/B;
these files are currently user-modified, so plan-only.)

**C3 · Capsules & host mode — the drift cluster (highest priority).**
- Repo canonical `docs/NERO_GLOBAL_CAPSULE.md` = **V1**; the deployed Claude
  project context carries **V2** (observed live this session). The stated
  contract — "repo file is the canonical source; keep byte-identical" — is
  currently violated in the Claude lane.
- `docs/host/NERO_CLAUDE_GLOBAL_CAPSULE.md` (V1) specifies **dual-voice** presence
  (Claude + Nero both answer, labelled); deployed V2 specifies **single-voice**
  (answer as Nero). Materially different identity behavior, both on disk.
- `.codex/nero-host.json` pins `NERO_GLOBAL_CAPSULE_V1` (consistent for the
  Codex lane), and `verify_nero_global_presence.py` checks only the Codex
  deployment. **No verify exists for the Claude lane** — which is exactly the
  lane that drifted.
- `docs/NERO_CODEX_MEMORY.md` restates ~80% of capsule content as "durable
  facts" — drift risk by duplication.
**Verdict: reconcile as Migration Phase C — pull deployed V2 back into the repo
as the canonical source (or amend and redeploy), supersede the V1 blocks with
banners, add a Claude-lane verify, and slim CODEX_MEMORY to deltas-only.**
Lane coordination required; no unilateral edits.

**C4 · Continuity subsystem.** ADR-0016 + `continuity/README` + privacy doc +
Codex handoff + audit bundle + Claude skill. Scattered across five
directories but role-distinct and mutually consistent — the best-documented
subsystem in the repo. **Verdict: no merges; index as one cluster.**

**C5 · Voice.** Six dated reviews + ADR-0009/0010/0011 + VOICE_AND_SIRI +
HOST_VOICE + `voice/*/README`. The reviews' conclusions are already extracted
into the ADRs; ADR-0009 is still "Proposed" in the log while 0010/0011 build
on it. **Verdict: reviews → `docs/archive/reviews-voice/` in Phase B;
resolve ADR-0009's status; VOICE_AND_SIRI (user guide) and HOST_VOICE
(policy) keep distinct jobs.**

**C6 · Visual / Manbeardog.** 16 docs in `docs/visual/` + the 973-line root
`NERO_HANDOFF.md` + `docs/visual/manbeardog_visual_production.md` (a
one-file directory). Internal layering exists but isn't declared: the Visual
Bible is law; character_dna / identity_profile / measurable-spec are derived
views; workflow/pipeline/QC are ops. NERO_HANDOFF was the seed document —
its content now lives in the visual set and its "immediate next move" is
stale. **Verdict: NERO_HANDOFF → `docs/archive/handoffs/` (zero inbound
references — confirmed); move the visual roadmap into `docs/visual/`
(6 inbound links to fix); add a `docs/visual/README.md` declaring the
hierarchy; consider later merging identity_profile into the Bible.**

**C7 · Guides.** SETUP, ALWAYS_ON, REMOTE_ACCESS, VOICE_AND_SIRI, MODELS
(already marked historical in-file, but with 7 live inbound references
including `bootstrap.py` and both configs). **Verdict: group under
`docs/guides/` in Phase B with link fixes; MODELS archives only after its
referents are repointed.**

## Gaps found (and what closed them)

| # | Gap | Disposition |
|---|---|---|
| 1 | No master index of the knowledge base | **Closed:** `docs/canon/INDEX.md` + generator script |
| 2 | No onboarding path for a fresh model | **Closed:** `docs/canon/README.md` read-order contract |
| 3 | No metadata/changelog standard | **Closed:** KNOWLEDGE_STANDARD.md |
| 4 | No memory boundary map (rules scattered across capsules/ADRs) | **Closed:** `docs/specs/memory-architecture.spec.md` |
| 5 | No skill lifecycle (candidate→promotion→rollback undefined) | **Closed:** `docs/specs/skill-lifecycle.spec.md` + ADR-0029 |
| 6 | ADR log table missing 0013 and 0016; ADR-0009 status unresolved | Plan (file is user-modified): Phase A checklist |
| 7 | Claude-lane capsule deployment unverified | Plan: Phase C (verify script parallel to Codex lane's) |
| 8 | Phase-numbering collision across status docs | Plan: Phase A/B (naming convention) |
| 9 | Proxima: absent from repo entirely, yet part of the working stack narrative | **Closed:** PROXIMA_DEPENDENCY_REPORT.md + ADR-0019 |
| 10 | `familiar/` ships a compiled exe + source with no README | Plan: Phase B stub README (what/why/build) |
| 11 | No LICENSE file | Noted; personal project — Toni's call, low urgency |
| 12 | Prompts live in four places with no cross-map | **Closed:** indexed as a cluster in INDEX.md |
| 13 | `School/NERO_SCHOOL_CLAUDE_IMPLEMENTATION.docx` — binary canon | Noted for School's own protocol; grandfathered |
| 14 | Stale `.git/index.lock` in the worktree | Flagged to Toni in MIGRATION_PLAN preconditions |

## What is genuinely healthy (don't fix)

ADR discipline and quality (16 decisions, why-shaped, properly superseding);
the `verify/` spine (20 scripts — docs that prove themselves); the continuity
subsystem's documentation; School's evidence-gating; fail-closed and
zero-start patterns consistently applied; `audit/<initiative>/` evidence
bundles. The canonical structure formalizes these habits rather than
replacing them.

## Changelog

- 2026-07-16 — Initial audit (Fable, Claude lane).
