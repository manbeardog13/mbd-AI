# ADR-0004 — MCP is the plugin standard

**Status:** Accepted

## Context
The vision lists ~13 external integrations (GitHub, Docker, Spotify, Calendar,
Notion, Obsidian, Email, Home Assistant, …). Hand-rolling and maintaining a
proprietary connector SDK for all of them would rot faster than one person can
patch, and would reinvent a problem the ecosystem has already standardized.

## Decision
Adopt the **Model Context Protocol (MCP)** as the plugin/tool-integration
standard. Nero's tool registry (ADR-0003) can mount MCP servers as tool
providers. We ship **2–3 connectors the owner actually uses daily** (e.g.
filesystem, GitHub, one media/productivity), and let everything else be a
community MCP server dropped into config.

## Consequences
- ✅ Maintenance of most connectors is offloaded upstream; the catalog grows
  without our code growing.
- ✅ One standardized capability abstraction; tools from MCP and native tools look
  the same to the agent loop.
- ⚠️ MCP servers are external processes / trust boundaries — they go through the
  same security gate and risk classification (ADR-0005), and network-touching
  ones are opt-in (privacy pillar).
- ⚠️ Some desired integrations may lack a good MCP server yet; those wait or get a
  minimal native tool, not a bespoke SDK.

## Alternatives considered
- **Proprietary plugin SDK** — rejected: unbounded maintenance, non-standard,
  reinvents MCP.
- **No plugins (core only)** — rejected: extensibility is a pillar; the whole
  point is that capabilities are installable.
