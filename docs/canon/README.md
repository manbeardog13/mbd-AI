---
id: canon.readme
title: Nero Canon — Start Here
layer: core
type: index
status: active
owner: shared
version: 1.0.0
created: 2026-07-16
updated: 2026-07-16
related:
  - docs/canon/INDEX.md
  - docs/canon/KNOWLEDGE_STANDARD.md
---

# Nero Canon — Start Here

You are a model (or a human) meeting Nero through this repository. This
directory is the knowledge system: the standards that organize everything, the
generated index of everything, and the dated reports that keep it honest.

**Guiding principle: this repo alone is enough to understand Nero.** The
North Star above it (Identity Charter, ADR-0024): **a user should never
have to wonder which Nero they are speaking to.** If you
find that false anywhere, that gap is a bug — file it in the next audit.

## Read in this order

1. **The identity capsule** — already in your task context if you're a hosted
   session (deployed from `docs/NERO_GLOBAL_CAPSULE.md` /
   `docs/host/NERO_CLAUDE_GLOBAL_CAPSULE.md`).
2. **[The Constitution](../CONSTITUTION.md)** — the law. Pillar order decides
   conflicts. Nothing below it wins against it.
3. **This file**, then **[INDEX.md](INDEX.md)** — the map of all knowledge.
4. **[PROJECT_BRIEF.md](../PROJECT_BRIEF.md)** — the current state snapshot.
5. Everything else **cold, on demand**. Source order: Toni's current
   instruction → Constitution → primary evidence → dated summaries/memory.

## The hierarchy every document lives in

```
Vision (VISION.md) → Principles (CONSTITUTION.md) → Decisions (docs/adr/)
→ Contracts (docs/specs/) → Implementation (app/ …) → Tests (verify/, tests/)
→ Skills (skills/, .claude/skills/)
```

Lower levels cite higher levels and never contradict them.

## What's in this directory

| File | Job |
|---|---|
| [INDEX.md](INDEX.md) | Generated master index — `python scripts/build_canon_index.py` |
| [CANONICAL_STRUCTURE.md](CANONICAL_STRUCTURE.md) | Where every kind of knowledge lives; core/operational/archival |
| [KNOWLEDGE_STANDARD.md](KNOWLEDGE_STANDARD.md) | Frontmatter metadata, index mechanism, changelog policy |
| [AUDIT_REPORT.md](AUDIT_REPORT.md) | 2026-07-16 audit: duplicates, overlap clusters, gaps |
| [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) | 2026-07-16 review: component map, challenged assumptions, risks |
| [PROXIMA_DEPENDENCY_REPORT.md](PROXIMA_DEPENDENCY_REPORT.md) | What Proxima was; why it's retiring (ADR-0019) |
| [MIGRATION_PLAN.md](MIGRATION_PLAN.md) | Phased path to the canonical structure; what's executed vs pending |

Boundary contracts live in [`docs/specs/`](../specs/): currently
[memory-architecture](../specs/memory-architecture.spec.md) (who may touch
which memory store) and [skill-lifecycle](../specs/skill-lifecycle.spec.md)
(how capabilities earn trust). Decisions live in [`docs/adr/`](../adr/README.md).

## Things a fresh model must not do (the short list)

- Don't touch `data/memory.db` — it belongs to the standalone local app
  (memory-architecture.spec, plane 1).
- Don't start local models, daemons, or voice for Host Mode — zero-start,
  fail closed (ADR-0014).
- Don't route to skills that aren't `permanent` (skill-lifecycle.spec).
- Don't edit School ledgers or the other lane's files — protocols govern both.
- Don't commit, merge, push, or publish without Toni's current, explicit
  approval for the exact action.
- Don't claim any contact or verification that didn't happen in this task.

## Maintenance

Adding/moving/retiring a knowledge file? Follow KNOWLEDGE_STANDARD.md,
regenerate INDEX.md in the same change, and touch `updated` in frontmatter.
Big changes get an ADR. Dated reports (audits, reviews) are immutable once
their date passes — write a new one.

## Changelog

- 1.0.0 (2026-07-16) — Canon layer established (ADR-0017, Proposed).
