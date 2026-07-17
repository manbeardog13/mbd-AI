---
id: handoff.inbox-build-2026-07-17
title: Engine Handoff - Review Inbox Build (Codex)
layer: operational
type: handoff
status: active
owner: shared
created: 2026-07-17
updated: 2026-07-17
sources:
  - docs/specs/review-inbox.spec.md
  - docs/adr/0021-review-inbox.md
related:
  - docs/specs/engine-handoff.spec.md
---

# Engine Handoff — Review Inbox Build

**Task:** implement the attention-architecture CLI · **Date:** 2026-07-17 ·
**Target engine:** Codex · Nero, emitted for Codex execution (first artifact
under `docs/specs/engine-handoff.spec.md`).

## Architecture summary

Nero's governance gates all speak to Toni synchronously today. ADR-0021
replaces that with four escalation levels (L0 log → L1 daily brief → L2 inbox
→ L3 interrupt), a policy-gated self-decision rule, a grouped review inbox,
and a cold daily brief. The build is one stdlib CLI plus one runtime JSON
store, following the existing hybrid-brain persistence pattern. Nothing
resident; every invocation runs and exits. DHEF packet
`ac362276-d7fb-44fb-bf79-f1b5d07d6afa` awaits the Codex builder lane
(claim → build → submit; Claude reviews; Toni approves).

## Extracted decisions

1. Four levels, L3 = exactly six interrupt conditions — ADR-0021 §1.
2. Self-approval only under recorded standing policies — ADR-0021 §2.
3. Inbox is a queue-view, never a second authority — ADR-0021 §3.
4. Brief is generated cold with a reading-time estimate — ADR-0021 §4.
5. House persistence pattern incl. exception-safe lock acquisition —
   spec §5 (fixes the fa2367b4 item-2 lock defect class).

## Constraints and boundaries

Stdlib only; no network, model, daemon, hook, or scheduled task. No access to
`data/memory.db`, School ledgers, or credentials. L3 class list hardcoded and
non-demotable. `data/review-inbox.json` is gitignored runtime. Lane ownership
and security gates unchanged. Commit/push only with Toni's approval.

## Ready-to-paste prompt

```
You are the Codex builder lane for DHEF packet
ac362276-d7fb-44fb-bf79-f1b5d07d6afa in D:\mbd AI (claim it first:
python skills/nero-hybrid-cognition/scripts/hybrid_brain.py
  --state data/hybrid-brain.json claim --task-id
  ac362276-d7fb-44fb-bf79-f1b5d07d6afa --host codex).

Build exactly per docs/specs/review-inbox.spec.md v1.1:
1. scripts/inboxctl.py - stdlib-only cold CLI with subcommands:
   add, list [--group], show, approve, reject, escalate, brief, prune.
   Persistence: data/review-inbox.json, revisioned, atomic
   tempfile+fsync+replace, lock file with 300s stale handling AND
   exception-safe acquisition (close/unlink on any failure between
   os.open and os.close - see hybrid_brain.py lock() for the pattern to
   improve). Entry schema and level semantics: spec sections 1-3.
   L3 classes are an immutable tuple; no flag or config may demote them.
   add --level 0|1 must fail unless --policy names a policy present in
   docs/canon/STANDING_POLICIES.md (create that file with a header and
   "no policies recorded yet" body).
   list --group renders spec section 3's grouped format, blocking pinned
   first; brief renders spec section 4 with an honest reading-time
   estimate (int(ceil(words/200)) minutes).
   approve/reject/escalate record decision + note (stdin) and, when
   source.kind is dhef, print the exact hybrid_brain command that drives
   the authoritative gate (do not execute it).
2. tests/test_review_inbox.py - unittest, importlib-loaded like
   tests/test_hybrid_cognition.py, covering: L3 non-demotion, policy-gated
   self-approval, grouped rendering, brief rendering, lock robustness
   (orphaned lock file is healed), atomic persistence.
3. verify/verify_nero_inbox.py - deterministic JSON {ok, checks} verifier:
   CLI help works, temp-store round-trip, L3 immutability, formats match.

Acceptance: python -m unittest tests.test_review_inbox passes;
python verify/verify_nero_inbox.py exits 0; no file outside
scripts/inboxctl.py, tests/test_review_inbox.py,
verify/verify_nero_inbox.py, docs/canon/STANDING_POLICIES.md is touched.
Stop conditions: any spec ambiguity -> submit lane with the question in
risks rather than inventing semantics; three failed attempts -> stop.
When done: hybrid_brain submit --host codex with summary, evidence,
checks, risks. Do not commit or push.
```

## Acceptance checks

- Unit tests green; verifier exits 0; `git status` shows only the four
  allowed paths.
- Claude reviewer lane confirms spec conformance and submits a verdict.
- Toni approves the merge gate; only then does anything get committed.

## Changelog

- 2026-07-17 — Emitted (Fable, Claude lane).
