# ADR-0016: Cross-host continuity ledger

**Status:** Accepted (Claude builder lane; pending live Codex verification)
**Date:** 2026-07-15

## Context

Toni wants to tell Nero something in one host (Claude- or Codex-hosted) and later
ask Nero about it from the other host, receiving the exact stored information
with a source receipt. The two presentations of Nero are separate hosted
sessions expressing one designed identity; neither can silently command the
other, and the static identity capsules (ADR-0014) do **not** synchronize
conversations. ADR-0015's DHEF/EGCSE coordinate *task evidence and lessons*, not
deliberate conversational memory transport, and must not be repurposed for it.

A literal shared mind is unavailable and undesirable. What is needed is a narrow,
auditable transport for **deliberately selected** memories that stays cold,
local, and honest about provenance — because both hosts run under Toni's one
Windows account, so a "Codex" or "Claude" label is *claimed*, not
provider-attested.

## Decision

Add a dedicated, standard-library-only **continuity ledger** at
`data/continuity/continuity.db`, driven by a cold CLI (`continuity/continuityctl.py`)
that each active session invokes on-demand:

1. **Deliberate capture only.** Nothing is stored unless Toni uses explicit
   routing language ("remember across hosts", "share/sync across hosts",
   "create a handoff"). Two scopes: `handoff` (24h) and `durable` (approved).
   Neighboring messages, transcripts, tool output, and secrets are never stored;
   secret-shaped input fails `DENIED_SENSITIVE` without logging the payload.
2. **Append-only, hash-chained events + receipts.** Every read/write/correction/
   revocation produces a chained receipt. Hashes cover immutable fields and the
   original content hash — not mutable plaintext — so an approved redaction keeps
   the chain verifiable. Corrections and revocations are appended events; the
   `status` column is a re-derivable cache.
3. **Claimed provenance, stated as such.** `source_host_claim` is recorded and
   always labelled as claimed. A receipt proves the *adapter* acted, not that a
   provider did.
4. **Deterministic retrieval.** Exact + lexical search only — no embeddings, no
   local inference. Contradictory active facts return `AMBIGUOUS`; unverifiable
   recall returns `NOT_FOUND`/`UNAVAILABLE`/`INTEGRITY_FAILED`. Retrieved
   payloads are fenced as untrusted data and are inert.
5. **Fail closed.** Missing drive/db, newer schema, tamper, or integrity failure
   refuse the operation rather than guessing. Integrity failure blocks recall.
6. **Zero-resident, permission-preserving.** Rollback journal (never WAL in v1),
   `synchronous=FULL`, `BEGIN IMMEDIATE` writes, bounded `busy_timeout` + ≤3 lock
   retries. No daemon, hook, port, scheduled task, network call, model, voice, or
   GPU. Content and queries pass via stdin, never argv.

The ledger is separate from `data/memory.db` (the standalone app), from DHEF/
EGCSE (task evidence), and from School (training). v1 does not read, migrate, or
modify any of them.

## Consequences

- Toni gets deliberate, auditable cross-host memory with receipts, without a
  fused model, background agent, or automatic sync.
- Each host must run its own adapter; a Claude write does not notify Codex, and
  vice versa. Retrieval is a pull, not a push.
- Provenance is honest but weak: labels are claimed, and a local administrator
  can still tamper (hash chains are tamper-evident, not tamper-proof).
- Live cross-host proof requires a **separate real Codex session** to deploy the
  Codex-side adapter and complete the bidirectional round-trip and disabled-
  continuity control. Until then this ADR is builder-verified only.
- Any future automatic capture, host hook, network provenance, or Desktop
  Familiar connection is out of scope and requires a new decision + Toni's
  approval.

## Alternatives considered

- **Reuse `data/memory.db`:** rejected — it belongs to the standalone app; mixing
  cross-host transport into it risks its integrity and the app's assumptions.
- **Extend DHEF for conversation transport:** rejected — DHEF is task-evidence
  coordination; ADR-0015 explicitly excludes free-form conversational sync.
- **Embedding/semantic recall:** rejected — would wake a local model and make
  retrieval non-deterministic; exact+lexical is knowable by construction
  (Constitution §3, Principle of Least Intelligence).
- **A watcher/hook that auto-captures:** rejected — violates "capture nothing by
  default", the zero-start boundary, and privacy.
- **WAL mode for throughput:** rejected in v1 — the observed SQLite (3.50.4) is
  below the relevant WAL-race fixes; rollback journal + `synchronous=FULL` is the
  safe default for a low-volume, correctness-first ledger.
