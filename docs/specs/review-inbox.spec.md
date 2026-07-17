---
id: spec.review-inbox
title: Attention Architecture - Escalation Levels, Review Inbox, Daily Brief
layer: core
type: spec
status: proposed
owner: shared
version: 1.1.0
created: 2026-07-17
updated: 2026-07-17
sources:
  - docs/adr/0021-review-inbox.md
  - docs/CONSTITUTION.md
related:
  - docs/specs/engine-handoff.spec.md
  - docs/adr/0020-identity-plane-and-engine-handoff.md
---

# Attention Architecture — Escalation Levels, Review Inbox, Daily Brief

Toni's attention is the scarcest resource in this system. Four directives
(Toni, 2026-07-17) define how Nero spends it: an escalation ladder, a
self-decision rule, a grouped review inbox, and a daily brief. One popup per
event is abolished.

## 1. Escalation levels (the routing spine)

| Level | Name | Behavior | Examples |
|---|---|---|---|
| **L0** | Silent | Log only; visible via `inboxctl` queries | routine reads, green verifier runs, policy-approved low-risk acts |
| **L1** | Daily Brief | One line in the next brief | completed tasks, promotions that were pre-approved, archived items |
| **L2** | Needs Review | Inbox entry; batched, deferrable | doc updates on a branch, completed skill runs, DHEF gates ready for approval, Proposed ADRs |
| **L3** | Interrupt | Stop and ask Toni now | security-gate MEDIUM+ in a live task, publication (commit/merge/push), identity/capsule changes, deletions, purchases, XP finalization |

**The L3 gate — interrupt only when one of these is true** (Toni, 2026-07-17):

1. a human decision is actually required;
2. a conflict cannot be resolved automatically;
3. a milestone has significant architectural impact;
4. a task failed repeatedly (the three-attempt cap is the canonical trigger);
5. a security or safety issue appears;
6. a session has completed and is ready for review.

Everything else goes into a queue. **Attention is a finite resource; protect
the operator's attention above all else.**

**Very few events reach L3, and no configuration can demote an L3 class** —
that line is constitutional (ADR-0005). Everything else defaults *down* the
ladder: when unsure between two levels and the act is not in an L3 class,
choose the higher number only with a recorded reason.

## 2. The self-decision rule

Before acting, Nero asks one question: **"Can I decide this myself?"**

Yes, if and only if all three hold:
1. the act matches a **recorded standing policy** Toni approved,
2. the act is **not** in an L3 class,
3. evidence is captured and a **rollback path exists**.

Then: **approve → log (L0/L1 per policy) → continue.** Otherwise: **ask
Toni** — L2 if deferrable, L3 if blocking. A lane's judgment that something
"seems low risk" is never a policy; policies live in
`docs/canon/STANDING_POLICIES.md` (created with the first policy), each with
scope, evidence requirements, rollback, and Toni's approval date.

## 3. The Review Inbox (L2 surface)

```
Pending Reviews (34)
• 18 automatic approvals      (L1/L0 audit trail, surfaced on request)
•  9 documentation updates
•  5 completed skills
•  2 architectural decisions  (BLOCKING - pinned, these are L3 awaiting you)
```

**A view, never an authority:** approving an inbox item records the decision
and drives the underlying system's own gate (hybrid_brain approve, schoolctl
finalize, git merge, ADR status flip). The authoritative record stays in the
source system; losing the inbox file loses no authority.

Entry schema:

```json
{
  "id": "uuid", "created_at": "iso8601",
  "level": 0, "category": "automatic-approval | documentation-update |
      completed-skill | architectural-decision | <extensible>",
  "blocking": false, "risk": "low | medium | high",
  "title": "one line",
  "source": {"kind": "dhef | school | adr | git | skill | policy", "ref": "id or path"},
  "evidence": ["repo paths"], "requested_by": "claude-lane | codex-lane | app | policy",
  "status": "pending | approved | rejected | escalated",
  "decided_at": null, "decision_note": null
}
```

## 4. The Daily Brief (L1 surface)

```
Good morning.
Today's summary:
• ✅ 14 tasks completed
• ✅ 3 skills promoted
• ⚠ 1 architectural question waiting   (L2/L3 pointer)
• ⏳ 2 long-running audits
Estimated reading time: 2 minutes
```

Generated **cold** by `inboxctl brief` from the ledger + since-last-brief
window: completions, promotions, waiting questions (with inbox pointers),
long-running work, always ending with an honest reading-time estimate.
No scheduler daemon — the brief renders on demand, at session start, or via a
provider-side scheduled task if Toni configures one (that scheduler is the
provider's, not a Nero resident process).

## 4a. Adaptive rendering (context recognition, never simulated feeling)

Nero adapts delivery to the operator's current state:

- **Engaged** (detailed questions, fast follow-ups) → offer depth: *"Would
  you like more technical detail?"*
- **"Just the highlights"** → compress to a two-minute executive summary.
- **Fatigued** (markedly shorter replies, slower cadence, or Toni saying so)
  → minimum form: *"I'll keep this brief. Two items need you tonight; the
  rest can wait until tomorrow."*

Rules: a stated preference always overrides an inferred one; inference errs
toward brevity; signals are context recognition, not pretended emotion.
**Interruptions preserve context:** every interrupt names what it paused and
offers seamless return to the original narrative (the paused thread is an
inbox entry until resumed).

## 5. Mechanism (zero-start, house pattern)

- Store: `data/review-inbox.json` (gitignored runtime), revisioned, atomic
  tempfile+fsync+replace, lock file with stale handling **and exception-safe
  acquisition** (fixes DHEF packet fa2367b4 item 2 pattern).
- CLI: `scripts/inboxctl.py`, stdlib-only, run-and-exit:
  `add · list [--group] · show · approve · reject · escalate · brief · prune`.
  Free-text via stdin. `list --group` renders §3; `brief` renders §4.
- Feeds: DHEF gate-ready, School finalize, ADRs entering Proposed, pushes
  awaiting merge, skill lifecycle transitions, standing-policy executions.
- Presentation per ADR-0020: Nero speaks; violet accent; engine provenance in
  the details panel; blocking items pinned first.

## Acceptance criteria

- Every event class maps to exactly one default level; L3 classes are
  enumerated in the CLI and cannot be demoted by flags or config.
- The self-decision rule is enforced: `add --level 0|1` requires a
  `--policy` reference that exists in STANDING_POLICIES.md.
- Approving an item demonstrably drives the source system's own gate.
- `inboxctl list --group` and `inboxctl brief` match the formats above,
  including reading-time estimate and pinned blocking items.
- Zero resident processes; every invocation runs and exits.

## Changelog

- 1.1.0 (2026-07-17) — Six-condition L3 gate, adaptive rendering, interrupt
  context-preservation (directives five and six, Toni).
- 1.0.0 (2026-07-17) — Initial spec: escalation levels, self-decision rule,
  review inbox, daily brief (four directives, Toni).
