# ADR-0006 — Local-First with Intelligence Escalation

**Status:** Accepted (2026-07-12, Toni) — supersedes the earlier no-cloud stance.

## Context
The vision wants an "expert engineer beside me, years ahead" for hard
architecture and programming. The largest model that runs *usably* on a 4070
(~14B dense, or a ~30B MoE) sits **well below frontier** on exactly those hard
reasoning tasks. The only two ways past that ceiling are **a bigger GPU** or
**routing hard tasks to a cloud model**. The flagship ambition and the hard
constraints are therefore in direct tension. This is a *product* decision, not an
engineering one — it belonged to Toni, and he has made it.

## Decision — "Local-First with Intelligence Escalation"
1. **Local is the default path, always.** Every request is served by the best
   model that runs well locally. Nero competes on **continuity, memory, tools,
   proactivity, and privacy** — the things a local assistant can do that a cloud
   one can't safely — not on raw model brainpower. The local model *improves for
   free* as local models improve (the model is a replaceable Reasoning Engine —
   ADR-0002/0003).
2. **Cloud reasoning is an escalation, never a default.** For the handful of
   genuinely hard tasks, Nero may escalate to a cloud model, but only when the
   escalation is:
   - **Explicit** — a conscious choice, surfaced as a config flag that is **OFF
     by default**;
   - **Opt-in** — enabled by Toni, per-request or per-session, never assumed;
   - **Transparent** — announced in the open when it happens ("escalating this to
     a cloud model"), with what is sent made visible. It is never silent.
3. **Local privacy is never quietly traded away.** Escalation moves *only* the
   task it is invoked for. Absent an explicit opt-in, nothing leaves the machine
   — the privacy pillar (Constitution §2) holds by default.

## Consequences
- ✅ Honest: no promise the hardware can't keep. Stays 100% local unless Toni
  consciously escalates.
- ✅ Future-proof: a better local model or a bigger GPU raises the local ceiling
  with no rewrite; the escalation path is a bonus, not a crutch.
- ✅ Trust: escalation is legible — Toni always knows when reasoning left the
  machine and what went with it.
- ⚠️ Some hard tasks are visibly weaker than a frontier cloud model *until* Toni
  chooses to escalate. That is the honest, accepted trade.

## Implementation notes (for the phase that builds it)
- Escalation is a property of the **Reasoning Engine / model router** (ADR-0002),
  not a special case sprinkled through the code: the router gains a `cloud` tier
  that is unreachable unless the flag is on.
- The decision to escalate is **surfaced to the user**, not taken autonomously by
  the model, in the first version. A later, opt-in "suggest escalation" mode may
  *propose* it — still never silent, still Toni's call.
- What is transmitted on escalation is logged and shown (observability), so the
  "transparent" promise is verifiable, not just stated.

## Alternatives considered
- **Stay fully local, no cloud tier at all (option a)** — rejected by Toni: gives
  up the one path past the local ceiling for genuinely hard tasks, even under
  conscious, transparent control.
- **Cloud by default / silent routing** — rejected: violates the privacy pillar
  and the "explicit, transparent" requirement outright.
- **Pretend a local model can be frontier-grade** — rejected: dishonest, sets up
  disappointment.
