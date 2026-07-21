# Nero Cross-Host Continuity Ledger (v1)

A cold, deterministic, **same-machine** ledger through which an *active* Claude
or Codex session can deliberately **save** and **retrieve** selected Nero
memories — with a source receipt for every operation.

> Objective: Toni tells Nero something in one host, then asks Nero about it from
> the other host and gets back the exact stored information with its receipt.

This is **shared, auditable continuity** — not a fused model, background agent,
automatic transcript copier, or provider-to-provider runtime.

## What it is NOT

- Not a daemon, watcher, server, hook, or persistent worker. It runs when
  invoked, does one operation, and exits.
- Not a network client. No API key, no provider call, standard library only.
- Not the standalone Nero app store. It never reads or writes `data/memory.db`.
- Not proof that Anthropic or OpenAI did anything. `source_host_claim` is
  **claimed** provenance (both hosts share Toni's one Windows account). A receipt
  proves the *adapter* acted, not that a provider did.
- Hash chains here are **tamper-evident** against mistakes and accidental
  corruption. They are **not tamper-proof** against a local administrator.

## Files

| Path | Purpose |
|---|---|
| `continuity/continuityctl.py` | the cold CLI (all operations) |
| `continuity/schema.sql` | ledger schema v1 |
| `continuity/policy.json` | limits, secret patterns, exit codes (auditable) |
| `continuity/tests/test_continuity.py` | adversarial suite (drives the public CLI) |
| `continuity/tests/test_verifier_guards.py` | verifier-gate and linked-worktree regression suite |
| `data/continuity/continuity.db` | the live ledger (git-ignored, created by `init`) |
| `verify/verify_nero_continuity.py` | deterministic verifier + 10k-event benchmark |
| `.claude/skills/nero-continuity/SKILL.md` | Claude on-demand adapter |
| `docs/CODEX_CONTINUITY_HANDOFF.md` | the Codex-lane contract (separate deploy) |
| `docs/NERO_CONTINUITY_PRIVACY.md` | capture policy & limitations |
| `docs/adr/0016-cross-host-continuity-ledger.md` | the decision record |

## Quick start

```bash
# one-time
python continuity/continuityctl.py --host claude init

# save (payload on STDIN, never argv)
printf '%s' "the release ships 2026-08-01" | \
  python continuity/continuityctl.py --host claude --source-host claude \
    capture --scope handoff --topic release-date --idempotency-key rd-1

# retrieve from the other host
printf '' | python continuity/continuityctl.py --host codex recall --topic release-date

# integrity + receipts audit
python continuity/continuityctl.py --host claude verify
```

## Commands

`init · status · capture · recall · show · propose-memory · approve-memory ·
correct · revoke · forget · export --redacted · verify · backup ·
rollback-dry-run`

All content-bearing operations read the payload/query from **stdin**. Every
operation prints JSON and returns a stable exit code:

| code | exit | meaning |
|---|---|---|
| `OK` | 0 | success |
| `USAGE_ERROR` | 2 | bad arguments / no stdin |
| `UNAVAILABLE` | 3 | drive/db/integrity state unavailable — fail closed |
| `NOT_FOUND` | 4 | nothing matched (never a guess) |
| `INTEGRITY_FAILED` | 5 | tamper/corruption — recall refused |
| `BUSY` | 6 | ledger locked by another writer (bounded) |
| `AMBIGUOUS` | 7 | contradictory active facts — Toni must resolve |
| `VERSION_UNSUPPORTED` | 8 | ledger schema newer than this CLI |
| `DENIED_SENSITIVE` | 9 | secret-shaped input refused (payload not logged) |
| `IDEMPOTENCY_CONFLICT` | 10 | key reused with a different payload |
| `DENIED_OVERSIZED` | 11 | input exceeds the bounded size |

## Storage scopes

- **handoff** (default): temporary, 24h expiry, for a current cross-host task.
- **durable**: requires Toni's explicit "remember across hosts"; no expiry; a
  durable *memory* record (model-generated summary) stays a **candidate** until
  Toni approves it, and every active durable memory links to a source event.

## Design invariants

- Rollback journal (never WAL in v1), `synchronous=FULL`, foreign keys on,
  `BEGIN IMMEDIATE` writes, bounded `busy_timeout` + ≤3 lock retries with jitter.
- Append-only events; corrections/revocations/redactions are themselves appended
  events. The `status` column is a re-derivable cache.
- `event_hash`/`receipt_hash` chain **immutable** fields + the original content
  hash — never mutable plaintext — so an approved redaction preserves chain
  verification.
- Retrieval is deterministic exact + lexical only. No embeddings, no model.
- Retrieved payloads are fenced as untrusted data and are inert.

Run the suites: `python -m unittest continuity.tests.test_continuity continuity.tests.test_verifier_guards`
Run the verifier: `python verify/verify_nero_continuity.py`
