# ADR-0013 - Maximum-access integration catalog and guarded MCP adapters

**Status:** Accepted (2026-07-14, Toni)

## Context

Toni wants Nero to use as many installed Codex/Claude skills and MCP-backed
integrations as possible, including Computer Use, Chrome, Browser, Visualize,
GitKraken Hooks, Ruflo, GitHub, and Hugging Face. Several are proprietary or
authenticated host runtimes; copying their files does not make them callable by
a separate local process. Injecting every full skill into a 14B model prompt
would also consume the context before work begins.

## Decision

- Discover all installed plugin manifests and `SKILL.md` files under the local
  plugin cache. Give Nero `skills.search` and `skills.read` so she loads only the
  instructions relevant to the current task.
- Keep every installed integration visible through `integrations.list` and
  `mcp.catalog`, with an honest transport/availability state.
- Represent Codex-hosted connectors and proprietary host runtimes as
  `bridge-backed`, never as fake local executables. While a Codex task is
  actively brokering the work, Nero may return the structured request described
  by `codex.bridge.instructions`.
- Provide a standards-based stdio MCP client. After a server artifact is scanned
  and approved, discover its tools and register each one as a normal Capability.
- Read-only MCP operations may be `SAFE`; mutations are `HIGH`; ambiguous tools
  are `MEDIUM`; credential/destructive tools are `CRITICAL`. Server annotations
  are untrusted hints and cannot de-escalate a named mutation.
- Maximum-access mode means maximum discovery and frictionless reads. It does
  not bypass the Capability Registry, security gate, project jail, or audit
  metrics. Secrets stay in environment/config and never appear in the catalog.

## Consequences

- Nero gains broad skill knowledge without permanently flooding model context.
- New installed skills appear after catalog refresh without agent-loop changes.
- MCP providers inherit one guarded dispatch path and per-tool risk.
- Host-only tools remain dependent on an active host bridge; absence is visible.
- Actual server packages are not launched or downloaded during discovery.
