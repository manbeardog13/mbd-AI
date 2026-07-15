# ADR-0017: Authoritative Core and hosted-worker boundaries

**Status:** Accepted
**Date:** 2026-07-15

## Context

Nero currently has three distinct surfaces: zero-start hosted identity, a
hard-disabled standalone local application, and a cold continuity ledger. The
Mission Control proposal adds deterministic Git inspection, task scheduling,
worker adapters, approvals, and audit history. Making either Claude or Codex
the owner would recreate model lock-in; silently starting a local service would
violate ADR-0014.

## Decision

1. **Nero Core is model-independent authority.** It owns task state, measured
   Git state, approvals, repository leases, events, and orchestration policy.
   Models propose or execute bounded work; they do not own those records.
2. **Core is explicitly launched.** Mission Control receives a separate manual
   composition root. Greetings and ordinary hosted tasks never start Core, the
   legacy application, a model, a database, or a project hook. ADR-0014 remains
   fully applicable to Host Presence.
3. **The implementation remains a modular monolith.** Git, scheduler, adapters,
   journal, verification, memory, voice, and vision are logical modules behind
   typed interfaces in one control plane unless extraction is later justified.
4. **Claude and Codex are replaceable hosted-worker adapters.** Every task packet
   names the provider, bounded context, capabilities, branch/worktree, lease,
   acceptance criteria, and context version. Results are normalized. Workers do
   not own identity, memory, scheduling, approval, Git truth, or push authority.
5. **One repository-global write lease.** The lease key is Git's canonical
   common directory, so separate worktrees cannot acquire simultaneous managed
   write authority. Ownership uses an unguessable token, expiry, heartbeat, and
   restart recovery. It coordinates Nero-managed workers, not unrelated manual
   Git clients.
6. **Remote truth is measured and writes fail closed.** Core fetches before
   calculating remote state, records freshness, and never asks a model to
   describe Git. Milestone 1 exposes no remote mutation. Future commit/push
   operations must pass the Capability Registry, Security Gate, verification,
   remote-freshness checks, a dry-run preview, and explicit human approval.
7. **Audit and memory stay distinct.** Core records every action and transition
   through the Action Journal service. The continuity ledger remains a separate,
   deliberate cross-host transport; the standalone memory database is not
   silently merged into either store.
8. **Absence fails closed.** Without a running Core or adapter, hosted Nero
   remains ordinary hosted identity. No host may invent shared memory, a lease,
   worker completion, or remote state.

## Consequences

- Mission Control can coordinate different engines without making identity
  model-specific.
- Host Presence remains zero-start and adds no resident Nero resource use.
- A user must explicitly launch Core before durable orchestration is available.
- Cloud use must disclose provider and bounded context, adding an intentional
  approval step but preserving privacy and provenance.
- Manual Git activity outside Core can still race; the UI must describe that
  limitation honestly.

## Alternatives considered

- **Claude or Codex as orchestrator:** rejected because the provider would own
  identity and state and could not independently verify itself.
- **Always-running local Nero daemon:** rejected because it violates ADR-0014
  and adds hidden resource use.
- **Microservices/event bus:** rejected by ADR-0001; logical modules and typed
  contracts provide the needed replaceability with one debuggable process.
- **One lease per worktree:** rejected because worktrees share refs and Git's
  common directory, so simultaneous writers can still race.
