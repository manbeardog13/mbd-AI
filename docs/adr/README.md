# Architecture Decision Records

Short documents that capture *why* a significant architectural choice was made,
so future contributors (human or AI) extend the reasoning instead of unknowingly
reversing it.

**Format** (keep each ADR to ~1 page):
- **Status** — Proposed / Accepted / Superseded by ADR-XXXX
- **Context** — the forces at play (hardware, constraints, goals)
- **Decision** — what we chose
- **Consequences** — the good and the bad we accept
- **Alternatives considered** — and why they lost

**Changing a decision:** don't edit an Accepted ADR's decision — write a new ADR
that supersedes it, and set the old one's status to "Superseded by ADR-XXXX".

## Log

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-modular-monolith.md) | Modular monolith, not microservices | Accepted |
| [0002](0002-model-router-sequential-swap.md) | Model layer is a sequential VRAM-aware swap router | Accepted |
| [0003](0003-agent-tool-loop.md) | The agent/tool loop is the core execution primitive | Accepted |
| [0004](0004-mcp-for-plugins.md) | MCP is the plugin standard | Accepted |
| [0005](0005-security-gate.md) | Security gate + human-in-the-loop terminal, built first | Accepted |
| [0006](0006-local-model-ceiling.md) | Local-First with Intelligence Escalation (cloud is explicit, opt-in, transparent) | Accepted |
| [0007](0007-capability-registry.md) | Capabilities, not hard-coded tools — the Capability Registry | Accepted |
| [0008](0008-executive-memory.md) | Executive Memory — the working-state register | Accepted |
