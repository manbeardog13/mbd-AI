# ADR-0007 — Capabilities, not hard-coded tools (the Capability Registry)

**Status:** Accepted (2026-07-12, Toni)

## Context
The agent/tool loop (ADR-0003) needs to know what it can do. The naive design
hard-codes a fixed tool list into the loop and bakes it into the prompt. That
couples reasoning to implementation three ways:
- the model reasons about specific function names instead of *what it is trying
  to accomplish*;
- adding a provider — an MCP server (ADR-0004) or a Skill (Phase 3) — means
  editing the loop itself;
- swapping one implementation for a better one (e.g. a faster git reader) ripples
  into prompts and call sites.

We already commit to MCP (ADR-0004) and Skills (Phase 3) as future capability
sources. They need a seam to plug into. Building that seam now — while Phase 1 is
already building the tool system, security gate, and metrics — is cheaper than
retrofitting it after three call sites exist.

## Decision
Introduce a **Capability Registry** as the single seam between the agent's
reasoning and concrete implementations.

- A **Capability** is a *declared ability*, not a function reference: a stable
  `name` (`"git.status"`, `"fs.read"`), a model-readable `description`, an
  `args_schema` (JSON Schema), a `risk` class (ADR-0005), and a `provider` that
  executes it.
- **The agent reasons over the registry's current contents, discovered at
  runtime.** The prompt's tool list is *generated from the registry* every turn,
  never hard-coded. The model asks for a capability by name and intent; the
  registry resolves it.
- **Providers register capabilities through one interface:** built-in tools
  (Phase 1), MCP servers (Phase 4, ADR-0004), and Skills (Phase 3) all appear as
  capabilities. A new provider is a new *registration*, not a loop change.
- **Cross-cutting concerns are enforced once, at the registry.** Every capability
  — whatever its provider — is routed through the **security gate** (ADR-0005)
  and emits **metrics** (observability). This is *why* the seam pays for itself: a
  future MCP tool physically cannot bypass the gate, because dispatch goes through
  the registry.
- **Deterministic capabilities are preferred** when they satisfy the need
  (Principle of Least Intelligence, Constitution §3): the registry lets the loop
  pick a knowing tool over a reasoning one without special-casing.

## Consequences
- ✅ MCP (ADR-0004) and Skills (Phase 3) plug into an existing seam — **no
  agent-loop refactor when they arrive.** This is the concrete, already-decided
  future-proofing that justifies building it in Phase 1, not speculation.
- ✅ Security gate + metrics are implemented once and are unbypassable, for all
  providers present and future.
- ✅ The model reasons about *what it needs done*; the registry maps intent to the
  best available implementation, which can be swapped freely.
- ⚠️ One layer of indirection over a direct call. Mitigation: keep it **thin** — a
  map of capabilities plus a dispatch function that wraps gate + metrics. No
  plugin framework, no dependency-injection container, no dynamic loading beyond
  registration. (Applying the Least-Intelligence principle to our own
  architecture.)

## Alternatives considered
- **Hard-coded tool list in the loop** — rejected: every new provider forces a
  loop change, and the security gate + metrics get re-implemented at each call
  site (the exact retrofit ADR-0005 warns against).
- **A full plugin framework up front** — rejected: premature and clever-over-
  elegant. The registry is the *minimal* seam that satisfies the already-made MCP
  and Skills decisions and nothing more.
