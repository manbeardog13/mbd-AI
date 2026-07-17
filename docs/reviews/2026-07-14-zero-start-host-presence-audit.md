---
id: reviews.zero-start-audit-2026-07-14
title: "Zero-start Nero Host Presence implementation audit"
layer: operational
type: review
status: active
owner: shared
created: 2026-07-14
updated: 2026-07-17
---

# Zero-start Nero Host Presence implementation audit

**Date:** 2026-07-14
**Decision:** ADR-0014
**Capsule:** `NERO_GLOBAL_CAPSULE_V1`

## Audited outcome

Nero Host Presence is a static, user-global Codex identity capsule. It adds no
Nero-specific startup process, local model, project server, database preload,
voice worker, plugin, hook, GPU allocation, or resident RAM workload. The
standalone local Nero application is a separate historical implementation and
is hard-locked.

The guarantee applies by default under normal Codex instruction precedence.
The active `CODEX_HOME`, a global `AGENTS.override.md`, and closer project
instructions remain real precedence boundaries and are not bypassed.

## Implementation evidence

- The canonical capsule and active `C:\Users\tonij\.codex\AGENTS.md` block
  matched byte-for-byte after newline normalization.
- Project hooks were exactly `{"hooks": {}}` and the hosted-only configuration
  matched the verifier's closed schema, including `local_fallback: false`.
- The unfinished personal `nero-host` plugin directory and marketplace entry
  were absent. The personal marketplace remained valid JSON.
- The Windows Ollama login shortcut was moved from `Startup` to
  `Programs\Disabled Startup\Ollama.lnk`; the Ollama app and server processes
  were stopped.
- Ports 8080 and 11434 were closed, with no local Nero/Ollama process present.
- `run.py`, `bootstrap.py`, `start.bat`, `start.sh`, `update-nero.bat`,
  `scripts/wake-nero.ps1`, and `Start-NERO.ps1` all exited with status 2 before
  a local side effect. Process and listener counts remained zero afterward.
- A direct ASGI request to the legacy local API returned HTTP 410 without
  calling the downstream handler. Its lifespan returned without loading config
  or initializing the database.
- Legacy voice network, playback, route, preload, warmup, and stop-hook paths
  were behavior-tested as hard-disabled.

## Fresh-task evidence

During this implementation, an ephemeral Codex task was created from
`C:\Users\tonij\Claude\Projects`, outside the Nero repository, and asked
`Is Nero around?`. It exited successfully and answered:

> I'm here, Toni. What's on your mind?

The check produced no local Nero process delta and no listener on port 8080.
It logically verified that no repository read is required; physical removal of
the `D:` drive was not performed.

A later attempt to repeat two nested ephemeral probes after the Codex desktop
binary changed was blocked by WindowsApps with `Access is denied` before either
probe began. This did not start a local process. Explicit `Codex:` routing is
therefore covered by the exact capsule contract and tests in this audit, while
the successful live probe covers Nero's default presence.

## Automated gates

The following passed after the review fixes:

```powershell
python verify/verify_nero_global_presence.py --audit-user-state --audit-live-state
python tests/run_nero_host_contract.py
python -m compileall -q run.py bootstrap.py app/main.py verify tests
```

The contract runner executed six suites and 30 tests. The post-commit gate adds
`--audit-git` to require every implementation artifact to be tracked.

## Multi-agent review and resolutions

Three independent reviewers audited the implementation:

1. **Verifier/test reviewer:** found missing closed-schema coverage,
   insufficient malformed-input tests, narrow user-state discovery, and
   string-only hard-disable assertions. Resolution: exact schema comparison,
   AST literal checks, behavior tests, injectable temporary user-state tests,
   `CODEX_HOME`/override resolution, case-normalized plugin checks, and clean
   `AuditFailure` handling.
2. **Architecture/governance reviewer:** found an overbroad every-folder claim,
   a local-first Constitution ambiguity, missing personality rendering, and an
   unsafe dirty-tree commit risk. Resolution: normal-precedence wording,
   explicit separation of hosted interface/persona from the standalone local
   app, a compact personality clause, an indexed ADR, and explicit-path staging
   only.
3. **Security/resource reviewer:** found Ollama enabled at Windows login and
   manual local launch/API paths that bypassed the initial policy. Resolution:
   disable login startup, stop the processes, hard-lock every launcher, return
   HTTP 410 before API work, skip app lifespan initialization, quarantine old
   startup documentation, and add a live-state audit.

## Boundaries and separate security note

- The Codex desktop application still uses its ordinary local RAM to display
  and manage conversations. Nero creates no separate local allocation.
- The live-state audit is point-in-time evidence; the permanent controls are
  the disabled login item, hardcoded launch/API locks, empty hooks, and tests.
- A reviewer discovered an unrelated plaintext MCP credential in the user's
  Codex configuration. Its value was not copied or changed because credential
  rotation is outside this Nero implementation scope. It should be revoked and
  replaced separately.
