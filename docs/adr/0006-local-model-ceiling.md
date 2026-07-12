# ADR-0006 — Accept the local model ceiling; keep cloud as an opt-in flag

**Status:** Proposed — needs Toni's explicit confirmation

## Context
The vision wants an "expert engineer beside me, years ahead" for hard
architecture and programming. The largest model that runs *usably* on a 4070
(~14B dense, or a ~30B MoE) sits **well below frontier** on exactly those hard
reasoning tasks. The only two ways past that ceiling are **a bigger GPU** or
**routing hard tasks to a cloud model** — and both are currently excluded by the
constraints (single 4070; owner has declined cloud). So the flagship ambition and
the hard constraints are in direct tension. This is a *product* decision, not an
engineering one — it belongs to Toni.

## Decision (proposed)
- **Accept the local ceiling.** Nero competes on **continuity, memory, tools,
  proactivity, and privacy** — the things a local assistant can do that a cloud
  one can't safely — rather than on raw model brainpower. The primary model is
  "the best model that runs well locally," and it *improves for free* as local
  models improve (the model is a replaceable component — ADR-0003).
- **Leave the door open, closed by default.** Because the LLM is a replaceable
  Reasoning Engine, an **opt-in cloud tier** for the handful of genuinely hard
  tasks is a **config flag, OFF by default, per-request, and visibly announced**
  when used. Turning it on is a conscious choice Toni makes in the open — it is
  never silent and never the default. (This would revise the current no-cloud
  stance; hence "Proposed".)

## Consequences
- ✅ Honest: no promise the hardware can't keep. Stays 100% local unless Toni
  flips the flag.
- ✅ Future-proof: a better local model or a bigger GPU raises the ceiling with no
  rewrite.
- ⚠️ Some hard tasks will be visibly weaker than a frontier cloud model, unless/
  until the opt-in tier is enabled.

## Alternatives considered
- **Pretend a local model can be frontier-grade** — rejected: dishonest, sets up
  disappointment.
- **Cloud by default** — rejected: violates the privacy pillar.

## Decision needed from Toni
Confirm one:
- **(a)** Stay fully local, accept the ceiling (no cloud tier at all), or
- **(b)** Adopt this ADR as written — local by default, with an opt-in cloud flag
  reserved for hard tasks you consciously enable.
