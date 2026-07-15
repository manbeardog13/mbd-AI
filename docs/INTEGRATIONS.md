# Nero integrations - maximum-access mode

Nero now discovers installed plugin skills and integration manifests at runtime.
The catalog itself is always active and does not load an Ollama model or start an
MCP process.

## What Nero can do immediately

- `integrations.list` - see installed plugins and their real availability.
- `skills.search` - search every installed `SKILL.md` by intent or plugin.
- `skills.read` - load one relevant skill into the current agent run.
- `mcp.catalog` - inspect MCP definitions and host-backed connector families;
  environment values are never returned.
- `codex.bridge.instructions` - produce a structured request when the needed
  tool exists only in the active Codex host.

The requested Computer Use, Chrome, Browser, Visualize, GitKraken Hooks,
ruflo-core, ruflo-swarm, GitHub, and Hugging Face plugins are prioritized in the
catalog. Every other compatible installed plugin is indexed too.

## Availability meanings

- `local-readable` - skill instructions are available directly.
- `bridge-backed` - the capability is authenticated/implemented by the active
  Codex host and can be brokered while that task is active.
- `host-only` - a lifecycle hook or UI runtime cannot run inside Nero itself.
- `ready-after-server-check` - an MCP stdio definition exists; its executable,
  permissions, and configuration must be valid before first launch.

## MCP execution

`StdioMCPClient` implements MCP JSON-RPC initialization, newline-delimited stdio,
paginated `tools/list`, and `tools/call`. `register_mcp_tools` registers each
discovered tool separately with the Capability Registry.

Risk defaults:

- read/list/search/fetch/status: `SAFE`
- ambiguous or execution-oriented: `MEDIUM`
- create/update/delete/publish/send/install: `HIGH`
- credential/secret/token/destructive disk operations: `CRITICAL`

Tool annotations from an MCP server are treated as untrusted hints. They cannot
turn a mutation into a read-only action. All execution still passes the existing
security gate and metrics.

## Privacy and credentials

Plugin files are read from the local cache. Credentials are never copied into
source, skill content, or catalog output. Codex-hosted GitHub and Hugging Face
authentication cannot be exported from Codex; use the live bridge or configure a
separate MCP server with credentials supplied through its environment.

## Software engineering mastery

`skills/nero-software-engineering` is the canonical cross-host coding skill. It
is deployed to the user Codex and Claude skill directories and activates on
demand for implementation, refactoring, debugging, testing, auditing, security
review, performance work, documentation, migration, and behavior-preserving
translation or adaptation between languages and platforms.

The skill combines native repository toolchains with relevant installed
engineering skills and host capabilities. Its host-resource router covers
GitHub, Hugging Face, Browser, Chrome, Computer Use, Visualize, GitKraken hooks,
Ruflo, MCP resources, and other compatible capabilities that are actually
available in the current session. Discovery is task-driven; it never starts all
plugins or loads a local model at task startup.

## Evidence-gated hybrid cognition

`skills/nero-continual-learning` implements Evidence-Gated Contextual Skill
Evolution: bounded outcome episodes, contextual resource routing, candidate
lessons, multi-context promotion gates, spaced rehearsal, regression quarantine,
and a deterministic competence backlog. It updates external skills and evidence,
not model weights.

`skills/nero-hybrid-cognition` implements the Dual-Host Evidence Fabric for
Codex and Claude sessions that Toni actually opens. It supports independent
analysis, builder/reviewer work, and non-overlapping parallel builds with atomic
claims and explicit merge approval. The protocol does not invoke providers,
export credentials, start a local model, or promise exponential speed. Approved
hybrid outcomes can feed the continual-learning ledger for future routing and
lesson evaluation.
