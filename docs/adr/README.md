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
| [0009](0009-voice-rendering-and-backend-architecture.md) | Voice rendering profiles + pluggable backend architecture | Proposed (in force via 0010/0011; formal status review pending) |
| [0010](0010-voice-effects-pedalboard-adoption.md) | Voice effects layer: pedalboard adoption + GPL v3 acceptance | Accepted |
| [0011](0011-voice-single-path-croatian-handling.md) | Single voice production path + Croatian handling (unsupported-language 204) | Accepted |
| [0012](0012-human-triggered-external-council.md) | Human-triggered External Council for OpenAI/Claude collaboration | Accepted |
| [0013](0013-maximum-access-integration-catalog.md) | Maximum-access integration catalog + guarded MCP adapters | Accepted |
| [0014](0014-zero-start-global-host-presence.md) | Zero-start global Nero Host Presence | Accepted |
| [0015](0015-evidence-gated-dual-host-cognition.md) | Evidence-gated continual learning + dual-host coordination | Accepted |
| [0016](0016-cross-host-continuity-ledger.md) | Cross-host continuity ledger (deliberate capture, receipts) | Accepted (pending live Codex verification) |
| [0017](0017-canonical-knowledge-base.md) | Canonical knowledge base + documentation hierarchy | Proposed |
| [0018](0018-skill-lifecycle.md) | Skill lifecycle — evidence-gated promotion, versioning, rollback | Proposed |
| [0019](0019-proxima-retirement.md) | Proxima retirement | Accepted |
