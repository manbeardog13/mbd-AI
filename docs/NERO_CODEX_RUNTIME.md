# Nero Host Runtime

**Mode:** global zero-start Host Mode
**Capsule:** `NERO_GLOBAL_CAPSULE_V1`
**Intelligence:** Codex on OpenAI-hosted resources
**Local Nero runtime:** prohibited for Host Mode
**Voice:** text-only until a supported hosted Codex voice channel exists

## Purpose

Nero's conversational identity is available in every Codex task through the
small static capsule in `docs/NERO_GLOBAL_CAPSULE.md`, deployed to the
user-global Codex instructions. Presence is context, not a running process.
This is a separately opted-in hosted Codex interface/persona, not the
standalone local Nero application governed by the Constitution's local-first
runtime design.

This design eliminates a separate startup path. No model, server, database,
plugin, hook, router, voice worker, or warmup process is required before Toni
can speak with Nero.

## Request flow

1. A new Codex task receives the global capsule during normal task creation.
2. A greeting or presence check returns immediately through the no-tool fast
   path.
3. Codex supplies reasoning, personality rendering, planning, and tool use on
   hosted resources.
4. Repository context is loaded only when the current task genuinely needs it.
5. Missing context fails closed to normal hosted Codex behavior, never to local
   Nero.
6. The final answer is text. There is no automatic local voice handoff.

## Resource contract

Host Mode must not start or call:

- Ollama, Qwen, or another local language model;
- local embeddings, reflection, or model routing;
- Nero's local API or project server;
- the local memory database merely for presence;
- local voice synthesis, speaker playback, or model warmup;
- any Nero-specific daemon, background worker, GPU allocation, or resident RAM
  workload.

The Codex desktop application necessarily uses local memory to display a task.
The guarantee is that Nero adds no separate local runtime or model allocation.

## Context tiers

1. **Hot context:** the global capsule only. It contains durable identity,
   routing, truth, resource, and voice rules.
2. **Task evidence:** relevant repository files, deterministic local sources,
   and authenticated Codex-host connectors selected for the current request.
3. **Cold project history:** memory summaries, handoffs, reviews, and ADRs read
   only when they materially affect the task.

## Truth boundary

Static presence is not proof that a local service, database, repository, or
plugin was contacted. Nero must state only what actually happened. A missing
capability is reported plainly and must never trigger a local-model fallback.

## Verification

Run:

```powershell
python verify/verify_nero_global_presence.py --audit-user-state
python tests/run_nero_host_contract.py
```

The verifier checks the canonical/global capsule match, instruction shadowing,
empty hooks, hardcoded hosted-only switches, live local-runtime state, stale
policy text, and removal of the unfinished personal plugin.
