---
id: spec.memory-architecture
title: Nero Memory Architecture
layer: core
type: spec
status: proposed
owner: shared
version: 1.0.0
created: 2026-07-16
updated: 2026-07-16
sources:
  - docs/CONSTITUTION.md
  - docs/adr/0008-executive-memory.md
  - docs/adr/0014-zero-start-global-host-presence.md
  - docs/adr/0015-evidence-gated-dual-host-cognition.md
  - docs/adr/0016-cross-host-continuity-ledger.md
  - docs/NERO_CONTINUITY_PRIVACY.md
  - docs/PROJECT_BRIEF.md
related:
  - docs/adr/0017-canonical-knowledge-base.md
  - docs/canon/KNOWLEDGE_STANDARD.md
verified_by: verify/verify_memory.py, verify/verify_nero_continuity.py, verify/verify_world_model.py
---

# Nero Memory Architecture

One page of truth about every place Nero remembers anything: what each store is
for, who may write it, who may read it, and which flows are forbidden. A new
model onboarding from this repo should read this before touching any store.

## Invariants (apply to every plane)

1. **One owner per store.** Every store has exactly one writing authority.
   Nothing else writes it, ever — not "helpfully," not on fallback.
2. **Deliberate capture.** Nothing conversational is persisted without an
   explicit, deliberate trigger (reflection inside the standalone app; explicit
   routing language for cross-host). No auto-scraping, no transcript capture.
3. **Fail closed, say so.** A store that is missing, locked, or fails integrity
   produces an honest "can't verify" — never an inferred answer presented as
   remembered (ADR-0016, NERO_CONTINUITY_PRIVACY).
4. **Claimed provenance is labelled claimed.** Host labels are not
   provider-attested; receipts prove the adapter acted, nothing more.
5. **Hosted sessions add no resident memory machinery.** No preload, daemon,
   watcher, or warmup exists for any plane (ADR-0014).

## The memory planes

| # | Plane | Store | Sole writer | Readers | Lifecycle |
|---|-------|-------|-------------|---------|-----------|
| 1 | Conversational long-term memory | `data/memory.db` (typed: semantic · episodic · preference · experience · procedural; confidence, importance, decay, entities, embeddings) | **Standalone local app only** (reflection pass) | Standalone app | Decay + reinforcement; safe schema migration |
| 2 | Executive Memory (working-state register) | app SQLite (ADR-0008) | Standalone app agent loop; `project`/`branch` **observed from git, never guessed** | Standalone app | Per-task; reset endpoints |
| 3 | World model (continuity picture) | `world_state` table | Standalone app background pass | Standalone app (read into every prompt) | Continuously updated; owner reset via API |
| 4 | Cross-host continuity ledger | `data/continuity/continuity.db` (ADR-0016) | `continuity/continuityctl.py`, invoked cold by the active hosted session **only on Toni's explicit routing language** | Either hosted lane, on demand, pull-only | Append-only, hash-chained; `handoff` 24 h / `durable` approved |
| 5 | Static identity & host-mode facts | `docs/NERO_GLOBAL_CAPSULE.md`, `docs/NERO_CLAUDE_GLOBAL_CAPSULE.md`, `docs/NERO_CODEX_MEMORY.md`, `docs/NERO_TAUGHT_KNOWLEDGE.md` | Toni (deliberate edits; deployment is a manual configuration act) | Any host, cold | Versioned capsule blocks; verify scripts check deployed copies |
| 6 | Evidence & learning records | `School/experience.json`, `School/DEBATE CC/` ledgers, EGCSE learning ledger | `School/tooling/schoolctl.py` (finalize) and the EGCSE maintenance path | Both lanes for School work | Evidence-gated; XP only via `finalize` ≥ 8.7 |
| 7 | Provider-native memory | Claude auto-memory, Codex memory, Ruflo `memory_store` | The provider's own machinery | That provider only | External to Nero |

## Prohibited flows (the boundary matrix)

- Hosted sessions (Claude or Codex lane) **never** read, write, preload,
  export, or describe `data/memory.db` as shared memory. It belongs to the
  standalone app.
- **Exception, tightly scoped:** taught-knowledge batches via
  `scripts/claude_teach_nero.py` are a Toni-requested, idempotent, offline
  batch operation (rows `source='claude-teaching'`, embeddings left null so no
  local model wakes). Every batch must be mirrored in
  `docs/NERO_TAUGHT_KNOWLEDGE.md` (the audit copy). This is a maintenance act,
  not a runtime path. *Note: capsule V2 wording and this exception need formal
  reconciliation — see Open items.*
- The continuity ledger never reads or writes `data/memory.db`, DHEF/EGCSE
  records, or School records (ADR-0016 v1 boundary).
- DHEF/EGCSE (task evidence, lessons) is **not** conversational memory and must
  not be repurposed as a transport for it (ADR-0015, restated by ADR-0016).
- Provider-native memory is never authoritative for Nero facts and never
  auto-writes any Nero store.
- No plane synchronizes automatically with any other. Every cross-plane copy is
  a deliberate act with an audit trail (receipt, ledger entry, or doc changelog).

## Read path for a fresh model (onboarding order)

1. The deployed identity capsule (arrives with the task context).
2. `docs/CONSTITUTION.md` — the law.
3. `docs/canon/README.md` → `docs/canon/INDEX.md` — the map.
4. `docs/PROJECT_BRIEF.md` — current state snapshot.
5. Everything else cold, on demand, per the source order: Toni's current
   instruction → Constitution → primary evidence → dated summaries/memory.

## Failure semantics

| Condition | Required behavior |
|---|---|
| Store unavailable / locked / integrity failure | Refuse the operation; tell Toni which store and why (`UNAVAILABLE`, `INTEGRITY_FAILED`) |
| Contradictory active facts (ledger) | Return `AMBIGUOUS`; Toni resolves — never a silent pick |
| Nothing matched | `NOT_FOUND`; never a guess presented as recall |
| Secret-shaped input | `DENIED_SENSITIVE`; payload never logged or echoed |

## Versioning & change policy

- Schema changes to any store require: a version marker in the store, a
  migration note in the owning subsystem's doc, and an ADR when the change
  alters a boundary in this spec.
- This spec is the canonical boundary document. A change to any boundary here
  is an architecture decision → new ADR, per `docs/adr/README.md`.

## Open items (reconciliation queue)

1. **Capsule V1/V2 drift.** Repo sources carry `NERO_GLOBAL_CAPSULE_V1` /
   `NERO_CLAUDE_GLOBAL_CAPSULE_V1`; the deployed Claude capsule is `V2` with
   materially different identity routing (single-voice) and an explicit
   memory.db exclusivity clause. The repo must be brought back to
   canonical-source truth (see MIGRATION_PLAN Phase C).
2. **Teach-script vs exclusivity wording.** V2's exclusivity clause and the
   `claude_teach_nero.py` pathway must be reconciled in one sentence of capsule
   text (proposal: "batch teaching via the script, on explicit request, with
   audit mirror, is the sole exception").
3. **Claude-lane deployment verification.** `verify_nero_global_presence.py`
   covers the Codex lane; an equivalent check for the deployed Claude capsule
   does not exist yet.

## Changelog

- 1.0.0 (2026-07-16) — Initial spec, drafted from primary sources during the
  canonical knowledge base audit.
