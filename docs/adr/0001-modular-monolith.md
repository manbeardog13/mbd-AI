# ADR-0001 — Modular monolith, not microservices

**Status:** Accepted

## Context
The V2 directive proposed ~14 independent "engines" over an internal event bus
with per-service self-healing. Nero runs on **one PC**, is used by **one person**,
and is maintained by that person (modest coding experience) plus an AI pair,
shipping one small PR at a time verified on the machine.

A distributed/event-bus design on a single machine buys nothing (there is nothing
to distribute) and costs a great deal: asynchronous indirection replaces
synchronous, stack-traceable calls; "services" invent failure modes (crashes,
reconnects) that a single process doesn't have; and the whole thing becomes a
concurrent-systems project no solo maintainer can own.

## Decision
Build a **modular monolith**: one application, one process where practical, one
debugger. Code is organized into modules (`core/ memory/ workspace/ planning/
tools/ terminal/ browser/ security/ observability/ ...`) that talk to each other
only through **defined interfaces**, never by reaching into internals. Extracting
a module into a separate process later must remain *possible*, but is never
*required*.

## Consequences
- ✅ One stack trace, one debugger, one deploy. A modest coder + AI can reason
  about the whole system.
- ✅ Interfaces keep coupling low, so modules stay swappable and testable.
- ✅ No self-inflicted distributed-systems failure modes.
- ⚠️ Discipline required: module boundaries must be enforced in review, or the
  monolith rots into a big ball of mud. Mitigation: interfaces + tests per module.
- ⚠️ True parallelism across modules is limited to async I/O (fine — see ADR-0002).

## Alternatives considered
- **Microservices / event bus** — rejected: distributed cost, zero distributed
  benefit, un-ownable by this team, destroys debuggability.
- **Unstructured monolith (one big app, no boundaries)** — rejected: becomes
  unmaintainable as capabilities grow; the whole point is *modular*.
