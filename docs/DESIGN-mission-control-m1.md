# Nero Mission Control — Milestone 1 design

**Status:** implemented and verified locally on `codex/nero-mission-control-m1`

**Governance:** [ADR-0017](adr/0017-authoritative-core-and-host-boundaries.md)
**Date:** 2026-07-15

## Outcome

Milestone 1 establishes a deterministic, model-independent Nero Core and a
manually launched Mission Control shell. Core owns orchestration state. Claude
and Codex are named, replaceable workers that receive bounded task packets;
neither worker owns Nero's identity, Git truth, scheduling, memory, approvals,
or remote-write authority.

Mission Control is deliberately not the legacy Nero application and is never
started by Host Presence. It runs only when the operator launches
`run_mission_control.py`.

## Component structure

```text
Operator browser
    |
    v
Mission Control shell (mission_control/)
    |-- read dashboard / queue tasks / record approvals
    |-- no commit, merge, pull, rebase, reset, checkout, or push route
    v
Nero Core (app/core/)
    |-- MissionControlService   composition and policy boundary
    |-- Scheduler               dependencies, state machine, single writer
    |-- GitService              direct inspection + explicit fetch only
    |-- CoreStore               versioned tasks, approvals, hash-chained events
    |-- Lease registry          canonical Git-common-dir fencing + heartbeat
    `-- Claude/Codex adapters   bounded packets and normalized results only
            |
            `-- no API invocation in M1; no local-repository or remote-write claim
```

The implementation remains one modular monolith with typed Python contracts.
No event bus, daemon, local model, or background worker was introduced.

## Deterministic contracts

`app/core/contracts.py` defines serializable `Task`, `AgentResult`, `GitState`,
`Approval`, `Event`, and `MemoryRecord` contracts. It also defines the bounded
`TaskPacket`, repository `Lease`, and `WorkerDescriptor` used by the M1 shell.
Provider SDK objects never enter Core state.

## Git truth

`GitService` asks Git directly for the repository root, canonical common
directory, worktree, branch, upstream, status, conflicts, worktrees, refs, and
last commit. It discovers the current branch's tracked remote before fetching.
A successful explicit `git fetch --prune <tracked-remote>` is the only Git
metadata mutation. Ahead/behind claims require a fresh versioned receipt bound
to the repository, tracked remote, redacted remote URL, and upstream. A failed
fetch overwrites the prior receipt and withholds counts. Authentication is not
confused with push permission.

Relationship text always identifies both sides, for example:

> Local branch main is 2 commits ahead and 0 commits behind upstream branch
> origin/main.

Fetch reachability/authentication is reported separately from push permission.
M1 never tests or claims push permission.

## Scheduling and the write lease

Tasks use a guarded state machine and explicit dependency checks. A write task
may be assigned only when remote evidence is fresh, a branch and upstream are
known, the worktree is clean and conflict-free, and the local branch is not
behind.

The one managed write lease is stored under Git's canonical common directory,
so separate processes, state databases, and worktrees contend on the same
SQLite row. Acquisition is transactional. Each grant has an opaque ID and a
monotonically increasing fencing number; the random credential is retained only
in the owning Core process and persisted only as a hash. Explicit heartbeat,
expiry, release, append-only lease history, and restart failure are
deterministic. Stale credentials cannot release or renew a successor. The lease
coordinates Nero-managed work, not unrelated manual Git clients.

Task assignment and transition use a monotonically increasing task version in
their SQL compare-and-set condition. A stale dashboard or concurrent request
gets a conflict rather than overwriting newer state. Verified completion is
only legal from `verifying` and requires a normalized result with explicit test
or operator evidence.

## Approvals and remote writes

The interface keeps remote-write controls visible so the policy is legible,
but they are disabled. Approval requests and decisions are durable evidence.
Even an approved `git.push` request records `remote_mutation.not_executed` and
has no execution path. There are no HTTP routes or Core service methods for
commit, merge, pull, rebase, reset, checkout, or push in M1.

## Event integrity

Task, approval, metadata, and event mutations are committed atomically in the
Core state database. `core_events` is append-only at the database layer and
each row hashes its canonical payload plus the previous event hash. A broken or
malformed chain forces read-only safe mode before fetch or any other mutation.
Lease state and its append-only history are atomic in the separate canonical
coordination database. Assignment uses lease-first, task-CAS, and compensating
release; it does not claim an impossible transaction across two databases.
Safe-mode views use a non-mutating lease peek, and heartbeat performs a Core
integrity preflight before it can extend the canonical lease.

This is the orchestration event ledger for M1. It does not rename, rewrite, or
import the standalone application's Stage-1 `action_journal` table. A later
approved adapter may project verified Core events into the wider Action Journal
service once that service's dispatch and safe-mode stages exist.

## Preservation and migration boundary

| Existing surface | M1 treatment |
|---|---|
| Hosted Nero identity capsule | Preserved; zero-start and independent of the repository |
| `.codex/nero-host.json` and empty Codex hooks | Preserved; all local-runtime/autostart switches stay disabled |
| Standalone local chat/model runtime | Preserved but dormant; Mission Control never imports or launches it |
| Standalone `data/memory.db` | Preserved; never read, copied, or merged by Core |
| Cross-host continuity ledger | Preserved as deliberate cold transport; not treated as automatic worker memory |
| Local voice/vision code | Preserved but dormant; presentation is outside M1 Core identity |
| Stage-1 `action_journal` | Preserved unchanged; Core uses a separate namespaced event ledger |

There is therefore no destructive data migration in M1. The migration is an
authority migration: new orchestration decisions live in Core, while legacy
stores keep their original meanings.

## M1 acceptance evidence

1. Git inspection is direct and covered with real temporary repositories.
2. Relationship wording names the exact local branch and upstream branch.
3. The queue enforces exactly one fenced repository-global managed writer
   across separate processes, Core databases, and linked worktrees.
4. Claude and Codex are provider-labelled workers, not Nero owners.
5. Remote approval is visible, durable, and non-executing.
6. Core mutations and transitions are hash-chained and append-only.
7. Identity, continuity, memory, voice, and journal boundaries are documented
   and preserved without database mixing.
8. Automated tests cover clean, dirty, ahead, behind, diverged, conflict,
   detached HEAD, local/remote-only refs, unavailable remote, failed auth,
   tracked non-origin remotes, receipt invalidation, credential redaction,
   separate-database lease contention, expiry, fencing, heartbeat, stale task
   versions, safe mode, scheduler failures, API policy, and interface safety.

## Deferred deliberately

Real Claude/Codex invocation, automatic dispatch, local Git mutation, guarded
commit/push execution, memory consolidation, voice, vision, and autostart are
not part of M1. Their absence is a safety boundary, not an unfinished hidden
path.
