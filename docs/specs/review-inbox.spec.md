---
id: spec.review-inbox
title: Attention Architecture - Escalation Levels, Review Inbox, Daily Brief
layer: core
type: spec
status: active
owner: shared
version: 1.4.0
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

### 1a. Canonical event catalog (Phase 1b)

`inboxctl` owns a versioned catalog. Callers provide a cataloged `category`;
the CLI derives `event_class`, `default_level`, and any immutable L3 trigger.
Unknown categories fail closed. A caller may raise an event above its default
only with `--level-reason`; promotion to L3 additionally requires one of the
six exact `--l3-trigger` values. No caller may lower a default.

- L0: `routine-read`, `green-verifier`, `automatic-approval`,
  `index-regeneration`.
- L1: `completed-task`, `preapproved-promotion`, `archived-item`,
  `lexicon-observation`.
- L2: `documentation-update`, `completed-skill`, `dhef-gate-ready`,
  `architectural-decision`, `generic-review`.
- L3: the six trigger names in §1.

Legacy L3 aliases remain recognizable but resolve to the six triggers:
`security-gate` → security/safety; `publication`, `deletion`, `purchase`, and
`xp-finalization` → human decision required; `identity-change` → architectural
milestone.

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
  "id": "uuid", "created_at": "canonical UTC iso8601",
  "category": "cataloged event or sanctioned legacy alias",
  "event_class": "canonical catalog key", "default_level": 2,
  "level": 3, "level_reason": "why raised above default or null",
  "l3_trigger": "one of the six exact triggers or null",
  "blocking": false, "risk": "low | medium | high",
  "title": "one line",
  "source": {"kind": "dhef | school | adr | git | skill | policy", "ref": "id or path"},
  "evidence": ["repo paths"], "requested_by": "claude-lane | codex-lane | app | policy",
  "status": "pending | approved | rejected",
  "decided_at": null, "decision_note": null, "policy": null,
  "policy_provenance": null, "rollback": null,
  "gate_state": "not_requested | not_applicable | awaiting_execution | legacy_unknown",
  "gate_action": null
}
```

The persisted state is schema version 3 with event-catalog version 1. Every
entry carries all routing and gate fields. `migrate` previews schema-1 or
schema-2 conversion without writing; `migrate --apply` writes an exact
`.v1.bak` or `.v2.bak` backup, matching the source schema, before the atomic
schema-3 replacement. Ambiguous legacy L3 routing or review entries without
source references block migration. Legacy approvals without recoverable
actions become `legacy_unknown`; historical self-approvals without provenance
remain visible as explicitly unverified history.

`gate_action`, when present, is an immutable structured object, never a shell
command:

```json
{
  "adapter": "dhef | school | adr | git | skill | policy",
  "render_version": 1,
  "operation": "adapter-specific operation code",
  "arguments": {"validated": "adapter-specific values"}
}
```

Adapter operations are fixed at render version 1: `dhef.approve_task`
(`task_id`, script/state pointers, quality `0.9`, decision note),
`school.finalize_task` (`task`, script pointer),
`adr.record_decision` (`ref`, accepted status, publication-gate marker),
`git.merge_after_review` (`ref`, publication-gate marker),
`skill.update_lifecycle` (`ref`, lifecycle-spec path), and
`policy.review_registry` (`ref`, publication-gate marker).

The inbox records Toni's decision, not completion of the source gate. An
approved external action therefore remains `awaiting_execution` until a future
source integration can attest completion. Repeating approval returns the exact
persisted action without changing the entry or revision. No approval path
executes, shells out, or regenerates a historical action through newer adapter
code.

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

### 4b. Delivery acknowledgement (Phase 2)

Rendering a brief creates a bounded pending-delivery record containing its
UUID, exact content digest, explicit presentation mode, and closed
`since_at..through_at` window. The acknowledged watermark does **not** move at
render time. Repeating `brief` returns the exact persisted content without a
revision change; `brief --ack <uuid>` alone advances `last_brief_at` and clears
the pending delivery. New events after `through_at` remain for the next brief.
This makes output failure recoverable without duplicate window advancement.

Presentation is explicit: `--mode standard | highlights | minimum | detailed`.
A pending brief cannot silently change modes. Stated caller choice is the only
persisted signal; the CLI does not infer or store a psychological profile.

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
  tempfile+fsync+replace. Concurrency uses a persistent lock file and a
  kernel-owned advisory exclusive lock on its open descriptor; the lock path is
  never renamed or unlinked. Kernel release on descriptor close or process
  death is stale handling. Unsupported locking platforms fail closed.
- CLI: `scripts/inboxctl.py`, stdlib-only, run-and-exit:
  `add · feed · list [--group] · show · approve · reject · escalate · brief · prune · migrate`.
  Free-text via stdin. `list --group` renders §3; `brief` renders §4.
- Schema: every load and pre-save validates the full schema-3 shape, catalog routing,
  temporal relationships, collection bounds, policy provenance, and gate
  invariants. State is bounded to 5 MiB, 10,000 entries, and 100 evidence items
  per entry.
- Authority paths: production is fixed to `data/review-inbox.json` and
  `docs/canon/STANDING_POLICIES.md`, with link-component rejection. Fixture
  overrides are accepted only inside an external `NERO_INBOX_TEST_ROOT`.
- Feeds: DHEF gate-ready, School finalize, ADRs entering Proposed, pushes
  awaiting merge, skill lifecycle transitions, standing-policy executions.
- Presentation per ADR-0020: Nero speaks; violet accent; engine provenance in
  the details panel; blocking items pinned first.

### 5a. Source-action adapters

Approval preflights the source reference and builds the immutable structured
action before changing state. DHEF and School accept bounded safe identifiers;
git accepts a conservative ref and rejects traversal/ref-parser constructs;
ADR, skill, and policy accept only their bounded repository-relative reference
forms with no absolute path, traversal, control character, or shell
metacharacter. All six source kinds have an adapter. Invalid or unsupported
actions fail with a nonzero exit and leave both state bytes and revision
unchanged.

### 5b. Cold feed envelope (Phase 2)

`feed` accepts exactly one version-1 JSON object on stdin. The fixed provider
pairs are `dhef/gate-ready`, `school/finalize-ready`, `adr/proposed`,
`git/awaiting-merge`, `skill/lifecycle-transition`, and `policy/executed`.
Each pair derives its category and source kind; callers cannot choose a lower
level. The tuple `(provider,event,id)` is hashed into a bounded receipt stored
under the inbox lock, so retry returns the original entry without a state
write. Policy execution still passes the complete self-decision rule.

New L3 entries and escalations carry paired `paused_context` and `resume_hint`
fields. Operator views render both so an interrupt identifies what stopped and
how to continue. Schema-1/2 migration preserves older entries with null context
rather than fabricating history.

## Acceptance criteria

- Every event class maps to exactly one default level; L3 classes are
  enumerated in the CLI and cannot be demoted by flags or config.
- The self-decision rule is enforced: L0/L1 require an exact approved policy
  match on level, event class, category, source kind, and risk, plus evidence
  and concrete rollback proof. Registry version, registry digest, normalized
  policy fields, Toni approval provenance, and an internal provenance digest
  are persisted with the entry.
- Approving an item demonstrably produces the validated structured action for
  the source system's own gate, persists that exact action, and never executes
  the gate itself.
- `inboxctl list --group` and `inboxctl brief` match the formats above,
  including reading-time estimate and pinned blocking items.
- Brief output is replayable until an exact UUID acknowledgement advances the
  watermark; all four explicit presentation modes retain the reading-time line.
- Every sanctioned source feed is catalog-routed and idempotent under
  concurrent retry; feed ingestion never executes a source gate.
- Zero resident processes; every invocation runs and exits.
- Concurrent mutation cannot lose an update; process death releases the lock
  without pathname stale-breaking; corrupt or invariant-breaking state fails
  closed before mutation.

## v1.2.1 amendments (Phase 1a invariant-safe approval core)

- Approval is preflight-first, print-only, persistent, recoverable, and
  idempotent. All six source kinds have strict adapters.
- Kernel-owned persistent-file locking replaces timestamp-based stale-lock
  breaking.
- Full schema and cross-field validation runs on load and before save.
  Argument, validation, and preflight failures are JSON on stderr and leave
  state unchanged. A post-replace durability failure reports
  `committed=true` and `durability_uncertain=true`; persisted approval actions
  remain recoverable after output delivery failure.

## v1.3 amendments (Phase 1b deterministic routing and autonomy)

- Canonical event catalog version 1 derives every default and exact L3 trigger.
- Schema 2 persists routing, rollback, and verified policy provenance.
- Production state and policy authority paths are fixed; test fixtures are
  confined to an explicit external root.
- Schema-1 migration is preview-first, backup-protected, atomic, and refuses
  ambiguous authority claims.
- Policy authorization occurs under the inbox lock and the registry digest is
  rechecked immediately before commit.

## v1.2 amendments (implementation-driven, dual-review findings)

- **Escalate raises, never hides:** escalation pins an item at interrupt
  level (status stays pending) instead of archiving it.
- **Fixture registry injection** is confined beneath `NERO_INBOX_TEST_ROOT` so
  health checks survive registry lifecycle without creating production authority.
- **Self-approval requires non-empty `--evidence`** (the rule's third leg).
- **Watermarked briefs:** `last_brief_at` persists in state; briefs report
  since-last-brief with entry ids and long-running flags.
- **Audit on request:** `list --status approved|rejected|all`; `--policy`
  rejected at levels >= 2 to keep the automatic-approval count honest.
- **Gate-command registry** covers all six source kinds, print-only, with
  ref validation against injection; `status` verb sanctioned.

## Changelog

- 1.4.0 (2026-07-17) — Phase 2 exact presentation, replayable brief delivery,
  explicit adaptive modes, cold idempotent feeds, and interruption context.
- 1.3.0 (2026-07-17) — Phase 1b canonical event routing, schema-2 migration,
  strict policy provenance, and canonical authority paths.
- 1.2.1 (2026-07-17) — Phase 1a lock, validation, stderr, and recoverable
  structured-action hardening after independent review.
- 1.2.0 (2026-07-17) — Implementation-driven amendments after dual
  independent review (see v1.2 section).
- 1.1.0 (2026-07-17) — Six-condition L3 gate, adaptive rendering, interrupt
  context-preservation (directives five and six, Toni).
- 1.0.0 (2026-07-17) — Initial spec: escalation levels, self-decision rule,
  review inbox, daily brief (four directives, Toni).
