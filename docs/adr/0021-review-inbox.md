# ADR-0021: Attention architecture — escalate rarely, batch reviews, brief daily

**Status:** Accepted (v1.4 Phase 2 implemented; directed by Toni, 2026-07-17)
**Date:** 2026-07-17

## Context

Every gate in Nero's governance currently speaks to Toni synchronously —
approval commands pasted into chat, one popup per event. Migration day
produced dozens of such interrupts. Toni issued four directives: a review
inbox instead of popups; a self-decision rule ("Can I decide this myself?
yes → approve, log, continue; no → ask"); a daily brief instead of constant
notifications; and four formal escalation levels with very few events ever
reaching the top.

## Decision

Adopt `docs/specs/review-inbox.spec.md` (v1.4):

1. **Four escalation levels** route every event: L0 silent log, L1 daily
   brief, L2 review inbox, L3 interrupt. L3 classes (security-gate MEDIUM+,
   publication, identity changes, deletions, purchases, XP) are enumerated
   and constitutionally immovable — no configuration demotes them.
2. **The self-decision rule** gates autonomy: self-approval exists only under
   a recorded standing policy (new `docs/canon/STANDING_POLICIES.md`), never
   under in-the-moment judgment; every self-approved act is logged with
   evidence and a rollback path.
3. **The Review Inbox** is the single L2 surface — a queue-view over
   authoritative gates, never a second authority.
4. **The Daily Brief** is the single L1 surface — generated cold, honest
   reading-time estimate, pointers into the inbox for anything waiting.
5. Implementation: house cold-CLI pattern (`scripts/inboxctl.py` +
   `data/review-inbox.json`), zero-start, stdlib-only. Built through the
   fabric: Codex builds, Claude reviews, Toni approves.

6. **Adaptive rendering:** briefs and all Nero communication adapt to the
   operator's engagement (depth on request, highlights on request, minimum
   form on fatigue signals); stated preference beats inference; inference
   errs toward brevity; interrupts preserve context and offer seamless
   return.
7. **The L3 gate is exactly six conditions** (decision required, unresolvable
   conflict, architecturally significant milestone, repeated failure,
   security/safety, session ready for review). Everything else queues.
8. **Approval is a recoverable print-only decision:** every source adapter
   validates its reference and creates an immutable structured action before
   the inbox records approval. The inbox persists and can re-return that exact
   action, but never invokes it; the source system remains authoritative.
9. **Concurrency is kernel-owned:** the runtime store uses a persistent lock
    file with an advisory exclusive lock on the open descriptor. The path is
    never renamed or unlinked, and process death releases ownership without an
    age-based stale-lock race.
10. **Routing is catalog-owned:** callers name a recognized event; the catalog
    derives its default level and exact L3 trigger. Upward overrides require a
    reason, L3 promotion requires one of the six triggers, and demotion fails.
11. **Autonomy is provenance-bound:** L0/L1 acts must exactly match an approved
    machine policy and persist registry version/digest, normalized scope,
    rollback proof, Toni's approval provenance, and a provenance checksum.
12. **Production authority paths are fixed:** alternate state and policy files
    exist only inside an explicit external verifier root, never as parallel
    production surfaces.

## Phase 1a implementation boundary

Phase 1a originally retained schema v1 while adding optional `gate_state` and
immutable structured `gate_action`. Phase 1b supersedes that transitional
shape with explicit schema-v2 migration while preserving legacy uncertainty.

Phase 1a covers lock correctness, exhaustive state invariants, stderr failure
reporting, and validated idempotent source actions. Exact grouped-list and brief
rendering, delivery-safe brief acknowledgement, automatic feed integration,
and adaptive presentation remain separately testable follow-up work; this
boundary does not weaken their commitments in the specification.

## Phase 1b implementation boundary

Schema v2, event-catalog version 1, exact L3 routing, strict policy matching,
canonical authority paths, and explicit schema-1 migration are implemented in
v1.3. Migration previews without mutation, refuses ambiguous routing, and on
`--apply` preserves the exact schema-1 bytes in a `.v1.bak` file before atomic
replacement. Historical approvals are never upgraded into authority claims:
missing gate actions become `legacy_unknown`, and missing policy provenance is
marked unverified.

Phase 2 now completes exact grouped-list and daily-brief presentation,
delivery acknowledgement, cold feed integration, adaptive modes, and
interruption context. Schema 3 adds only the bounded delivery/feed state and
paired context fields; all source authority remains external. Migration from
schema 1 or 2 is preview-first and preserves the exact source bytes as
`.v1.bak` or `.v2.bak`, respectively, before atomic schema-3 replacement.

## Phase 2 implementation

Brief rendering persists a closed delivery window and exact content before it
prints. Retries replay that content byte-for-byte; only `brief --ack <uuid>`
advances the watermark. Four explicit rendering modes implement the adaptive
contract without persisting inferred psychology. The six sanctioned feed pairs
arrive as versioned JSON on stdin, derive their catalog route, and deduplicate
under the existing kernel lock. New interrupts name paused work and a return
path. No feed, brief, or Familiar integration executes a source gate.

## Constitution amendment (proposed text - awaiting Toni's amendment PR)

Proposed addition to CONSTITUTION.md §4 (How we work):

> **Respect the operator's cognitive bandwidth.** Attention is a finite
> resource; protect it above all else. Summarize before expanding,
> prioritize before detailing, and adapt delivery to the operator's current
> engagement. Interrupt only for a decision genuinely required now, an
> unresolvable conflict, an architecturally significant milestone, repeated
> failure, a security or safety issue, or a completed session ready for
> review - everything else queues. Interruption preserves context and always
> allows seamless return.

Per the Constitution's own amendment procedure this lands only through a PR
titled "Constitution amendment" opened by Toni, referencing this ADR.

## Consequences

- Toni's interrupt rate collapses to genuinely blocking decisions; the rest
  becomes a two-minute morning read plus an occasional batch review.
- Lanes gain a uniform "file it" primitive; autonomy becomes auditable
  policy rather than vibes.
- Cost: policies must be written deliberately (empty policy file = nothing
  self-approves, which is the safe default); one more runtime ledger.
- Unread-inbox risk mitigated by brief pointers and blocking-item pinning.
- Approval can survive output failure because the normalized action is stored
  with the decision and returned unchanged on retry.
- Cost: adapter render versions become an explicit compatibility surface; this
  is preferred to silently reinterpreting old decisions.

## Alternatives considered

- **Auto-approve by judgment call:** rejected — batching attention must never
  become batching authority; policies or nothing.
- **Provider-native notifications / resident watcher:** rejected — violates
  zero-start (ADR-0014) and fragments across engines.
- **Status quo (chat-paste approvals):** rejected — it is the 34-popup
  problem with extra steps; empirically failed on 2026-07-17.
