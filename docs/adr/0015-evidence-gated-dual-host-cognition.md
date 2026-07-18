# ADR-0015: Evidence-gated dual-host cognition

**Status:** Accepted  
**Date:** 2026-07-14

## Context

Toni wants Nero to improve from completed work and to use Codex and Claude
together for greater speed and coverage. A literal fused or self-modifying
brain is unavailable: the providers expose separate hosted sessions, neither
session can silently command the other, parallel work can collide, and repeated
model agreement is not proof. Nero Host Presence must also remain zero-start and
must not wake a local model, daemon, memory database, or GPU workload.

ADR-0012 governs the standalone application's explicitly triggered external API
council. This decision governs Toni-authorized Codex and Claude Host Mode tasks;
it does not supersede or silently enable that council.

## Decision

Adopt two cooperating, provider-neutral mechanisms:

1. **Evidence-Gated Contextual Skill Evolution (EGCSE)** stores bounded outcome
   episodes, contextual resource evidence, candidate lessons, evaluations,
   promotion gates, spaced rehearsal, and regression quarantine in a cold,
   versioned JSON ledger. It changes external context and skills, never model
   weights or permissions.
2. **Dual-Host Evidence Fabric (DHEF)** represents one task as Codex and Claude
   lanes using `parallel-analysis`, `build-review`, or non-overlapping
   `disjoint-build`. Each real hosted session must claim and submit its own lane.
   Deterministic gates check evidence and topology; explicit approval completes
   a task and may feed bounded outcomes into EGCSE.

The shared files are coordination records, not a resident mind. They contain no
credentials, hidden instructions, chain-of-thought, source contents, connector
payloads, or full conversation history. No script calls a provider or network.

## Consequences

- Independent work can run concurrently when Toni has both hosted sessions
  active, while overlapping edits use a builder/reviewer sequence.
- Cross-host review can improve coverage and produce routing evidence, but no
  fixed speedup or intelligence multiplier is promised.
- Claude and Codex remain separately permissioned; agreement grants no new
  authority.
- Read-only status creates no state file. Mutations use atomic writes and short
  leases so the protocol stays cold and recoverable.
- Lessons require repeated multi-context tests and explicit promotion. Two
  consecutive failures quarantine an active lesson.
- True automatic provider invocation would require separately authorized APIs,
  credentials, cost controls, and a new decision; it is outside this ADR.

## Alternatives considered

- **Autonomous provider-to-provider loop:** rejected because current sessions do
  not expose that control surface and it would obscure cost, consent, and data
  flow.
- **Shared free-form transcript:** rejected because it leaks context, grows
  without bound, and encourages correlated errors.
- **Concurrent edits everywhere:** rejected because merge races erase any speed
  benefit and weaken verification.
- **Local fused model or fine-tuning:** rejected because it violates Host Mode's
  local-resource boundary and does not create access to either hosted model.

