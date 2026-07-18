---
id: canon.standing-policies
title: Standing Policies - earned autonomy registry
layer: core
type: standard
status: active
owner: toni
version: 1.1.0
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

Phase 1b treats the fields below as the complete machine authorization record:
`level`, `event_class`, `categories`, `source_kinds`, `risks`,
`evidence_required`, `rollback`, `approved_by`, and `approved_at`. An approved
policy authorizes only an exact match and its normalized fields plus registry
version and SHA-256 digest are persisted with every self-decision. Draft or
malformed sections grant no authority. All current policies remain draft.

## policy: index-regeneration
status: draft
level: 0
event_class: silent-log
categories: index-regeneration
source_kinds: policy
risks: low
evidence_required: true
scope: Running scripts/build_canon_index.py after any doc add/move/retire,
  and committing the regenerated INDEX.md together with the causing change.
evidence: INDEX.md diff in the same commit; --check green.
rollback: git revert of the commit; the generator is deterministic.
approved_by: pending
approved_at: pending
requested_by: claude-lane (2026-07-17)
approval: pending Toni

## policy: verify-sweep-on-canon-commit
status: draft
level: 0
event_class: silent-log
categories: green-verifier
source_kinds: policy
risks: low
evidence_required: true
scope: Running the read-only verifier suite (verify_canon, verify_nero_voice,
  presence verifiers) before any commit touching docs/; logging results.
evidence: exit codes in the session log; failures block the commit and
  escalate to level 2.
rollback: none needed - read-only checks.
approved_by: pending
approved_at: pending
requested_by: claude-lane (2026-07-17)
approval: pending Toni

## policy: lexicon-observation
status: draft
level: 1
event_class: daily-brief
categories: lexicon-observation
source_kinds: policy
risks: low
evidence_required: true
scope: Appending newly observed organic signature expressions (with first-seen
  date and source) to the Voice Bible lexicon section of PRESENCE_PROGRAM.md.
evidence: the diff itself; entries must cite the conversation date.
rollback: git revert; fatigue guard applies regardless.
approved_by: pending
approved_at: pending
requested_by: claude-lane (2026-07-17)
approval: pending Toni
