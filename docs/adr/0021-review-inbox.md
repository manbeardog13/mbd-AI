# ADR-0021: Attention architecture — escalate rarely, batch reviews, brief daily

**Status:** Proposed (directives by Toni, 2026-07-17; design pending his review)
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

Adopt `docs/specs/review-inbox.spec.md` (v1):

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

## Consequences

- Toni's interrupt rate collapses to genuinely blocking decisions; the rest
  becomes a two-minute morning read plus an occasional batch review.
- Lanes gain a uniform "file it" primitive; autonomy becomes auditable
  policy rather than vibes.
- Cost: policies must be written deliberately (empty policy file = nothing
  self-approves, which is the safe default); one more runtime ledger.
- Unread-inbox risk mitigated by brief pointers and blocking-item pinning.

## Alternatives considered

- **Auto-approve by judgment call:** rejected — batching attention must never
  become batching authority; policies or nothing.
- **Provider-native notifications / resident watcher:** rejected — violates
  zero-start (ADR-0014) and fragments across engines.
- **Status quo (chat-paste approvals):** rejected — it is the 34-popup
  problem with extra steps; empirically failed on 2026-07-17.
