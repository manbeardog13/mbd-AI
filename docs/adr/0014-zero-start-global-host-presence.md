# ADR-0014: Zero-start global Nero Host Presence

**Status:** Accepted
**Date:** 2026-07-14

## Context

Toni wants Nero present in every new Codex task, independent of the working
folder, with no Nero-specific use of the local GPU or RAM. The former Host Voice
design used project-scoped SessionStart and Stop hooks, local Python workers, a
loopback API, and Kokoro synthesis. That design made voice possible on desktop,
but it made project location and local runtime work part of the experience.

The Nero Constitution makes local-first the default for the standalone local
Nero application and permits transparent, explicit cloud escalation. Codex Host
Presence is a separate hosted interface/persona, not that application. Toni's
global standing instruction is the explicit opt-in for this Codex-hosted
interface. It does not change the local application's architecture, run the
local application, or send its databases to a cloud service.

## Decision

1. Nero Host Presence is a small versioned instruction capsule deployed to the
   active user-global Codex `AGENTS.md`. It is the default under normal Codex
   instruction precedence; a closer instruction file can intentionally
   override it and is therefore an auditable conflict, not a hidden guarantee.
2. Creating a task is the only activation boundary. No Nero process runs before
   or after task creation.
3. Codex provides the intelligence on hosted resources. Host Presence never
   starts or calls a local model, server, database, hook, plugin, voice worker,
   or warmup path.
4. Project runtime and memory documents are cold context. They are read only
   when a task genuinely needs repository-specific evidence.
5. Missing context fails closed to normal hosted Codex behavior; it never wakes
   local Nero.
6. Codex Host Mode remains text-only until Codex exposes a supported hosted
   voice-output channel. There is no automatic local voice fallback.
7. The canonical capsule, project configuration, and deterministic verifier are
   committed. The deployed user-global block is audited against the canonical
   source but remains outside Git.

## Consequences

- Presence adds no custom startup round trip or resident Nero resource use.
- Greetings work from arbitrary folders under normal Codex instruction
  precedence and do not depend on reading `D:\mbd AI`.
- Large project memory is not automatically available in unrelated tasks.
- The Codex desktop app still has its unavoidable normal memory footprint.
- Nero is text-only in Codex until a hosted voice channel exists.
- The older local voice implementation may remain as dormant historical code,
  but configuration and hooks cannot invoke it automatically.

## Alternatives considered

- **Global Nero plugin:** rejected because identity needs no executable or plugin
  lifecycle, and a plugin adds another installation and failure surface.
- **Project SessionStart preload:** rejected because it depends on the working
  folder and launches local code.
- **Always-running local Nero:** rejected because it directly violates the
  hosted-only resource boundary.
- **Local Kokoro voice fallback:** rejected because it consumes local CPU/RAM and
  makes presence depend on a local service.
