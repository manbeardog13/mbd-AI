---
id: canon.migration-report-2026-07-17
title: Migration Report — Phase 0 + Phase A Checkpoint
layer: operational
type: report
status: active
owner: shared
created: 2026-07-17
updated: 2026-07-17
sources:
  - docs/canon/MIGRATION_PLAN.md
  - repo-wide link check (316 links) and ADR consistency check, 2026-07-17
related:
  - docs/canon/AUDIT_REPORT.md
---

# Migration Report — Phase 0 + Phase A Checkpoint

The checkpoint Toni requested before any deeper migration. Question this
report answers: **is the canon now the single source of truth?**

## What was executed

| Commit | Content |
|---|---|
| 4a6d224 + 5e4960c | Rescue branch: dirty worktree preserved and committed (Toni) |
| efd1a9b | Iskra v2 artifact swap: 81 legacy files replaced by final/ + qa/ (QA: ok, visual pass; package shipped to .codex/pets/iskra) |
| fb4a729 | Phase 0: canon layer — docs/canon/, docs/specs/, ADRs 0017–0019, index generator (14 files) |
| 3a09fcc | School DEBATE CC log: DHEF review START/FINISH entries |
| 9cdb2b8 | Phase A: supersession banners, complete ADR log, canon pointers, charters, off-repo link fixes |

Branch `claude/rescue-dirty-worktree-20260715` pushed to origin with tracking.
Only intentionally-uncommitted state remains: Toni's two `.claude` hook edits.

## Verification results

- **Links:** 316 relative links checked repo-wide → **0 broken**. (4 were broken
  before Phase A — malformed relative links to the iCloud folder in
  `docs/visual/phase_a_execution_guide.md`; converted to marked off-repo paths.)
- **ADR numbering:** files 0001–0019 ↔ log table 0001–0019, no gaps, no
  orphans, no rows without files. ADR-0009 annotated (in force via 0010/0011;
  formal status review pending).
- **Index:** `scripts/build_canon_index.py --check` deterministic and green;
  218 knowledge files indexed, 11 carrying canon frontmatter.
- **Deterministic verifiers:** `verify_nero_school` 4/4 ok; hybrid/learning
  unit tests 9/9. `verify_nero_learning_hybrid` remains **red on its Claude
  capsule check** — expected until Phase C (it pins V1 markers; deployed
  user-global file carries V2). This is the tracked drift, not a regression.

## Files superseded (banner + frontmatter, retained as history)

- `docs/DIRECTIVE.md` — governing claims and 7-priority order superseded by
  CONSTITUTION.md v1.1; verification standards remain in daily use.
- `docs/VISION.md` — philosophy sections superseded; roadmap table marked
  historical (ROADMAP.md governs).
- `docs/MODELS.md` — already marked historical in-file (pre-existing).
- `NERO_HANDOFF.md` — superseded by docs/visual/*; **zero inbound references**;
  scheduled to archive in Phase B1.

## Files still referencing legacy docs (healthy references; Phase B fix list)

- DIRECTIVE: PROGRESS.md, README.md, app/db.py, CONSTITUTION.md (the
  supersession statement itself), PROJECT_BRIEF.md, verify/README.md.
- VISION.md: PROGRESS.md, README.md, CONSTITUTION.md, PROJECT_BRIEF.md, three
  voice reviews (archive candidates themselves).
- MODELS.md: README.md, bootstrap.py, config.example.yaml (+ untracked
  config.yaml), docs/SETUP.md, verify_nero_global_presence.py — **the B4
  repoint list**; code references are user-facing strings, update with care.
- NERO_HANDOFF.md: none.

All such references now land on documents that declare their own status, so
they mislead no one. They are relocation work, not truth hazards.

## Remaining migration work

- **Phase B** (structural moves): B1 NERO_HANDOFF → archive; B2 visual roadmap
  → docs/visual/; B3 voice reviews → archive; B4 guides/ + MODELS repoints;
  B5 host/ moves (Codex-lane coordination required); B6 visual + familiar
  READMEs; B7 skill lifecycle frontmatter; B8 frontmatter adoption; B9 design
  docs stay until "The Hands" completes.
- **Phase C** (identity-critical): adopt V2 single-voice as repo canonical
  capsule (Toni decided 2026-07-16); reconcile the memory.db teach-exception
  wording; add Claude-lane deploy verifier; fix the hybrid verifier's marker
  pin — this also clears DHEF packet fa2367b4 (changes-requested).
- **Phase D** (School-governed, both hosts) and **Phase E** (Proxima
  retirement, ADR-0019, Toni executes).

## Confidence assessment

**The canon is now authoritative: HIGH confidence.** Every governing question
has exactly one current answer reachable from `docs/canon/README.md`; every
superseded document says so on its first screen; the ADR record is complete
and consistent; the index is machine-verified. Two caveats keep this honest:
Phase C is where identity truth (capsule V2) becomes repo truth — until then
the deployed capsule leads the repo source, tracked and decided but not yet
reconciled; and 207 files still lack frontmatter (flagged `unmigrated` in the
index), which affects metadata coverage, not authority.

## Update — Phase C executed (2026-07-17)

Repo capsule source now carries the deployed V2 block verbatim (single voice);
the hybrid verifier derives its marker version from the canonical source
instead of a hardcoded V1 pin; `verify_nero_claude_presence.py` gives the
Claude lane the same deploy verification the Codex lane had. Deployed
artifacts untouched. Standing rule adopted: **reconciliation before
evolution** (KNOWLEDGE_STANDARD §6). Tracked residue: the Cowork project
'NERO' instructions carry a NERO_GLOBAL_CAPSULE_V2 surface with no repo
canonical source yet (needs an exact export from project settings); the
memory.db teach-exception wording is queued as a V3 capsule proposal; DHEF
packet fa2367b4's builder lane can now resubmit against green verifiers.

## Changelog

- 2026-07-17 — Phase C update appended (Fable, Claude lane).
- 2026-07-17 — Initial checkpoint report (Fable, Claude lane).
