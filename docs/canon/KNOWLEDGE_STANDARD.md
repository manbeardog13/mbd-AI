---
id: canon.knowledge-standard
title: Knowledge Organization Standard
layer: core
type: standard
status: proposed
owner: shared
version: 1.1.0
created: 2026-07-16
updated: 2026-07-17
sources:
  - docs/CONSTITUTION.md
  - docs/adr/README.md
related:
  - docs/canon/CANONICAL_STRUCTURE.md
  - docs/adr/0017-canonical-knowledge-base.md
---

# Knowledge Organization Standard

The metadata, index, and changelog rules that make the repo self-documenting.
Mechanism over vigilance: everything here is checkable by a deterministic
script (Constitution §3 — don't reason when you can know).

## 1. Metadata standard (frontmatter)

Every knowledge markdown file carries YAML frontmatter:

```yaml
---
id: canon.knowledge-standard   # stable dotted id: <area>.<name> — never reused
title: Knowledge Organization Standard
layer: core | operational | archival
type: constitution | adr | spec | standard | report | plan | guide |
      handoff | review | reference | index | log
status: proposed | active | superseded | archived
owner: toni | shared | claude-lane | codex-lane | school
version: 1.0.0                 # semver; required for core, optional elsewhere
created: 2026-07-16
updated: 2026-07-16            # touch on every substantive edit
supersedes: []                 # optional, list of ids
superseded_by: null            # required once status: superseded|archived
verified_by: verify/verify_x.py  # optional but prized — docs that prove themselves
sources: []                    # primary sources this doc derives from
related: []                    # cross-references
---
```

Rules:

- `id` is permanent. Files may move; ids may not.
- `status: superseded` additionally requires a visible banner in the first ten
  lines ("Superseded by X — retained as history"), because models and humans
  skim. DIRECTIVE.md and the VISION roadmap table are the motivating cases.
- ADRs keep their existing format (Status/Context/Decision/Consequences/
  Alternatives); frontmatter is additive and optional for ADRs 0001–0016 until
  Phase B of the migration touches them.
- School files are exempt until School adopts the standard under its own
  shared-work protocol; the index records them as `school`-owned regardless.

## 2. Index system

`docs/canon/INDEX.md` is the master index: every knowledge file, its id, layer,
type, status, owner, and title, grouped by cluster.

- It is **generated**, never hand-edited: `python scripts/build_canon_index.py`
  walks the repo, reads frontmatter (inferring sensible defaults for
  not-yet-migrated files), and rewrites INDEX.md deterministically.
- Regenerate in the same change as any doc add/move/retire. Verification may
  run the generator and fail on drift (a future `verify_canon.py` hook —
  MIGRATION_PLAN Phase B).
- Files without frontmatter appear in the index flagged `unmigrated`, so
  migration progress is visible in the index itself.

## 3. Changelog policy

Three tiers, matched to weight:

1. **Decisions** — a new ADR in `docs/adr/`, logged in its README table.
   Accepted ADRs are never edited; they are superseded.
2. **Core docs** (constitution, standards, specs, capsules) — a `## Changelog`
   section at the bottom of the file: one line per version, newest first, with
   date and what changed. Version bumps follow semver semantics on the
   document's *contract*, not its prose.
3. **Operational docs** (PROGRESS, PROJECT_BRIEF, ROADMAP, guides) — the
   `updated` field plus the doc's own conventions. PROJECT_BRIEF freshness is
   already nudged by the `.claude` Stop hook (`brief-staleness-check.sh`);
   that mechanism stands.

Capsule blocks are special: any change to a `*_CAPSULE_*` marked block bumps
the version **inside the block marker** (V1 → V2 → …), updates the repo
canonical source first, and only then deploys — verified byte-identical by the
lane's verify script. Deployment without a repo-source bump is drift by
definition (this is the exact failure the audit found).

## 4. Linking rules

- Relative markdown links within the repo; every rename/move fixes inbound
  links in the same change (the audit's inbound-reference map shows how cheap
  this is to check: `grep -rl <name>`).
- A doc that states a checkable claim about the system should link the check
  (`verified_by`) — the repo's strongest existing habit, made explicit.
- External references (URLs, other machines' paths like `D:\NERO_Forge`,
  `C:\Users\tonij\Proxima`) are marked as **off-repo** so a fresh model knows
  it cannot verify them from here.

## 5. Onboarding read-order contract

A new model reads, in order: capsule (arrives with context) →
`docs/CONSTITUTION.md` → `docs/canon/README.md` → `docs/canon/INDEX.md` →
`docs/PROJECT_BRIEF.md` — then everything else cold, on demand. The canon
README must always keep this contract true from its first screen.

## 6. Reconciliation before evolution (standing rule)

When deployed behavior and the repository differ, first make the repository
faithfully represent deployed reality — a pure reconciliation change with no
behavioral edits — and only then introduce intentional change as a new
version (V3, V4, ...). This preserves clean history, keeps reviews simple,
and keeps audits unambiguous. Adopted as a standing rule by Toni,
2026-07-17; candidate for a future Constitution §4 amendment. First
application: the V2 capsule adoption (MIGRATION_PLAN Phase C).

## Changelog

- 1.1.0 (2026-07-17) — Added §6 reconciliation-before-evolution (standing rule, Toni).
- 1.0.0 (2026-07-16) — Initial standard.
