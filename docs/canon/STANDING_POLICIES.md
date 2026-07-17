---
id: canon.standing-policies
title: Standing Policies - earned autonomy registry
layer: core
type: standard
status: active
owner: toni
version: 1.0.0
created: 2026-07-17
updated: 2026-07-17
sources:
  - docs/adr/0021-review-inbox.md
related:
  - docs/specs/review-inbox.spec.md
---

# Standing Policies — earned autonomy registry

The self-decision rule ("Can I decide this myself?") answers *yes* only for
acts matching a policy on this page with `status: approved`. Approval is
Toni's alone; lanes may draft. An empty or all-draft registry means
everything asks — the safe default. `inboxctl` parses this file; a policy is
machine-readable via its `## policy:` header and `status:` line.

## policy: index-regeneration
status: draft
level: 0
scope: Running scripts/build_canon_index.py after any doc add/move/retire,
  and committing the regenerated INDEX.md together with the causing change.
evidence: INDEX.md diff in the same commit; --check green.
rollback: git revert of the commit; the generator is deterministic.
requested_by: claude-lane (2026-07-17)
approval: pending Toni

## policy: verify-sweep-on-canon-commit
status: draft
level: 0
scope: Running the read-only verifier suite (verify_canon, verify_nero_voice,
  presence verifiers) before any commit touching docs/; logging results.
evidence: exit codes in the session log; failures block the commit and
  escalate to level 2.
rollback: none needed - read-only checks.
requested_by: claude-lane (2026-07-17)
approval: pending Toni

## policy: lexicon-observation
status: draft
level: 1
scope: Appending newly observed organic signature expressions (with first-seen
  date and source) to the Voice Bible lexicon section of PRESENCE_PROGRAM.md.
evidence: the diff itself; entries must cite the conversation date.
rollback: git revert; fatigue guard applies regardless.
requested_by: claude-lane (2026-07-17)
approval: pending Toni
