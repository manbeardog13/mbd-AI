# Nero Cross-Host Continuity — Audit Bundle

**Status:** `READY_FOR_CODEX_LIVE_TEST`
**Builder:** Claude lane · **Date:** 2026-07-15
**Repository revision (pre & during build):** `ede7c867fbde41115efa50cc3652225a8d16d16f`
**Branch:** `claude/github-repo-verification-vor5iw`
**Runtime:** Python 3.14.5 · SQLite 3.50.4 (below WAL-race fixes → rollback journal kept)

This bundle is Claude's **builder-lane** evidence. It uses deterministic tests and
a simulated single-machine client for both host claims. It is **not** proof of
live cross-host continuity — that requires a separate real Codex session
(see `../../docs/CODEX_CONTINUITY_HANDOFF.md`, §8).

## Declared allowlist (only these were touched)

```
continuity/{README.md, schema.sql, continuityctl.py, policy.json, tests/test_continuity.py}
data/continuity/**                         (git-ignored runtime; NOT created in the real tree — tests used temp dirs)
.claude/skills/nero-continuity/SKILL.md
docs/adr/0016-cross-host-continuity-ledger.md
docs/CODEX_CONTINUITY_HANDOFF.md
docs/NERO_CONTINUITY_PRIVACY.md
verify/verify_nero_continuity.py
audit/nero-continuity/**
.gitignore                                 (append-only defensive block)
```

## Files changed

| File | State |
|---|---|
| `continuity/README.md` | new |
| `continuity/schema.sql` | new |
| `continuity/policy.json` | new |
| `continuity/continuityctl.py` | new |
| `continuity/tests/test_continuity.py` | new |
| `.claude/skills/nero-continuity/SKILL.md` | new |
| `docs/adr/0016-cross-host-continuity-ledger.md` | new |
| `docs/CODEX_CONTINUITY_HANDOFF.md` | new |
| `docs/NERO_CONTINUITY_PRIVACY.md` | new |
| `verify/verify_nero_continuity.py` | new |
| `audit/nero-continuity/*` | new (this bundle) |
| `.gitignore` | appended (defensive; `data/` already ignored the ledger) |

## Existing files proven UNCHANGED (pre == post sha256)

| File | sha256 | changed |
|---|---|---|
| `data/memory.db` | `9dcfcac419…dabfb946` | **no** |
| `~/.claude/CLAUDE.md` (Claude host capsule) | `579d453abb…f89755f0` | **no** |
| `~/.codex/AGENTS.md` (Codex host capsule) | `d598491101…3e38b12d3` | **no** |
| repo `AGENTS.md` / `CLAUDE.md` / `docs/NERO_CLAUDE_GLOBAL_CAPSULE.md` | unchanged | **no** |
| existing `claude-teaching` rows in memory.db | untouched (memory.db byte-identical) | **no** |

### Honest exception — external Codex-owned drift (NOT caused by this build)

`~/.codex/config.toml` changed `16a39e47…` → `0acd0aa6…` at `2026-07-15T00:41:27+02:00`.
Claude wrote **nothing** under `~/.codex`. In the same window the live Codex
desktop app also rewrote `.codex-global-state.json(.bak)`, `.codex/cache/*`,
`.codex/browser/config.toml`, and bundled-marketplace `plugin.json` files — i.e.
Codex's own background activity. See `global-drift-evidence.json`. This is exactly
the "claimed vs genuine provenance / shared Windows account" reality the task's
truth boundary anticipates.

## Automated test results (see `test-evidence.json`)

- `python -m unittest continuity.tests.test_continuity` → **exit 0, Ran 36 tests, OK**
- `python verify/verify_nero_continuity.py` → **exit 0, all_pass=true** (`verify_result.json`)

Adversarial coverage (all via the public CLI against isolated temp DBs): Unicode/
Croatian roundtrip; canonical serialization + UTC format; event & receipt chain
verification; duplicate idempotency key same payload (idempotent) and different
payload (`IDEMPOTENCY_CONFLICT`); two processes × 20 unique writes (40 contiguous
sequences); 20 simultaneous duplicates (exactly 1 stored); reader during write;
forced lock → bounded `BUSY`; kill before commit (rolled back) and after commit
(persisted); direct payload mutation → recall `INTEGRITY_FAILED`; receipt
mutation → verify fail; row deletion/gap → fail; status tamper → fail;
unsupported schema → `VERSION_UNSUPPORTED`; missing/malformed/read-only storage →
`UNAVAILABLE`; prompt-injection payload inert; secret-shaped + oversized rejection
(`DENIED_SENSITIVE`/`DENIED_OVERSIZED`); nonce NOT treated as secret; correction/
supersession; expiry & revocation; conflicting active facts → `AMBIGUOUS`;
traversal/metacharacter resistance; backup + rollback-dry-run; no-neighbor-capture;
redacted export hides plaintext; secret-shaped session-id rejected.

## Concurrency results

40/40 unique concurrent writes persisted with contiguous, unique sequences; 20
simultaneous duplicate writes collapsed to exactly 1 event; reader-during-write
and forced-lock (`BUSY`, bounded < 40 s) verified; verify OK after each.

## Performance & zero-resident (see `verify_result.json`, `zero_resident_proof.json`)

Corpus: **10,000 bounded events**, verify OK.

| metric | value | budget |
|---|---|---|
| in-process read overhead p95 / p99 | **10.0 / 10.6 ms** | ≤250 / ≤500 ms ✓ |
| in-process write overhead p95 / p99 | **25.5 / 60.6 ms** | ≤250 / ≤500 ms ✓ |
| cold-CLI read p50/p95/p99 | 137 / 203 / 238 ms | context |
| cold-CLI write p50/p95/p99 | 135 / 180 / 203 ms | context |
| interpreter+import start (median) | ~36 ms | — |

Continuity overhead is measured separately from process spawn: the ledger's own
read/write cost is ~10–25 ms p95. Cold-CLI figures include Python spawn + Windows
AV; a single earlier write sample spiked to 586 ms (process-launch/fsync tail),
which is why the budget gate is asserted on in-process overhead, with cold-CLI
reported for context.

**Zero-resident:** after the full run — 0 lingering `continuityctl` processes,
0 new continuity scheduled tasks, 0 new services, 0 new Run-keys, listening-port
count 65→64 (unrelated). (An earlier scan false-positived on the measurement
PowerShell whose own command line contained the literal "continuityctl"; corrected
to match only `python.exe … continuityctl.py`.) No local model, embedding, voice,
Nero API, or GPU invoked; zero network activity.

## Security & privacy review (3 lanes, run sequentially in-lane)

Subagents were **not** spawned (harness policy: only on explicit user request);
the three lanes were performed sequentially by the builder and are labelled as
such. Findings:

1. **Architecture** — consistent with the Constitution (Least Intelligence: exact+
   lexical, no model), ADR-0014 (zero-start), ADR-0015 (separate from DHEF/EGCSE),
   and the standalone app (never touches `data/memory.db`). ADR-0016 recorded.
2. **Privacy/security** — overcapture blocked (stdin-only, no neighbor capture);
   injection inert; traversal/symlink/reparse rejected; no shell (stdin content,
   no `os.system`); provenance labelled "claimed" everywhere; `forget`=redaction,
   no silent hard-delete; backups via online-backup API; rollback dry-run is
   read-only on live. **Fix applied:** secret-scan `--session-id` (argv stored as
   plaintext + hashed). **Known residual:** pattern-based secret detection can
   miss an unlabeled high-entropy secret — a deliberate tradeoff so a shared nonce
   is storable; documented in the privacy doc.
3. **Verification** — concurrency/idempotency/crash/tamper/replay covered; false
   recall blocked (NOT_FOUND, guess-trap); disabled/unavailable path fails closed;
   status is `READY_FOR_CODEX_LIVE_TEST` (no live claim). **Known scope:** AMBIGUOUS
   detection is topic-scoped in v1; recall preflight verifies events (returned rows
   + global structure), while receipt-chain tamper is caught by `verify`.

## Rollback manifest

- Delete `data/continuity/` to remove all stored continuity data (git-ignored).
- Remove the allowlisted new files and revert the appended `.gitignore` block.
- No global config, hook, service, scheduled task, or `data/memory.db` change was
  made by this build; nothing else to undo. `backup` + `rollback-dry-run` prove a
  ledger snapshot is restorable and verifiable without mutating live.

## Proposed-but-not-deployed

- `proposed-global-claude-block.md` — optional global Claude routing block
  (managed markers + rollback). **Not deployed** (editing global CLAUDE.md is a
  stop-and-ask boundary).
- Codex managed instruction block — in `../../docs/CODEX_CONTINUITY_HANDOFF.md` §5.
  **Not deployed** (Codex owns its side).

## Live-test checklist — PENDING (Codex + fresh Claude sessions + Toni)

Unknown-challenge `NOT_FOUND` · Codex→Claude nonce round-trip · disabled-continuity
`UNAVAILABLE` control · Claude→Codex reverse · guess trap · correction preserved.
No nonce appears in any file, fixture, log, or prompt. Only after both live
directions **and** the disabled control have evidence may status become
`LIVE_BIDIRECTIONAL_VERIFIED` — which Claude may not assign.
