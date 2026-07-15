# Nero Global Host Presence acceptance matrix

The canonical automated audit is:

```powershell
python verify/verify_nero_global_presence.py --audit-user-state --audit-live-state
python tests/run_nero_host_contract.py
```

## Manual behavior checks

| Scenario | Expected result |
|---|---|
| New task from a folder outside `D:\mbd AI`; ask `Is Nero around?` | Under normal Codex instruction precedence, a direct Nero reply with no commentary, tool call, file read, status probe, or setup narration |
| New task; begin with `Codex:` | Separate Codex response while retaining relevant context |
| `D:` unavailable | Nero remains present and does not claim project memory was loaded |
| Missing, shadowed, or malformed global capsule | Verifier fails; ordinary hosted Codex remains the only fallback and no local runtime is authorized |
| Three ordinary Nero text replies | No new Ollama, Qwen, Nero Python, Kokoro, local API, or GPU process |
| Complex task that genuinely needs the repository | Repository context is loaded on demand and truthfully reported |

## Resource boundary

The promise is zero **additional Nero-specific** local runtime: no local model,
daemon, project server, database preload, voice worker, warmup, or GPU allocation.
The normal Codex desktop application necessarily uses local RAM to display the
conversation; that unavoidable host-app footprint is not attributed to Nero.
The deterministic audit proves the configured launch and policy boundaries. The
`--audit-live-state` gate separately checks the current ports, processes, and
Windows login startup state; it is a point-in-time audit, not an operating-system
resource reservation.

## Instruction precedence

The deployed capsule is resolved from the active `CODEX_HOME` (or the default
`~/.codex`). A non-empty `AGENTS.override.md` at that level shadows
`AGENTS.md`, so the verifier rejects it. A closer project instruction can also
intentionally override global identity; therefore "every task" means the
default under normal Codex instruction precedence, not an impossible bypass of
explicit higher-priority instructions.

## Latency boundary

The acceptance target is architectural, not a network timing promise. The Nero
presence path must add no tool round trip, process launch, repository read,
database lookup, model handoff, or voice synthesis beyond ordinary Codex task
creation and response latency.

After the implementation commit, also run:

```powershell
python verify/verify_nero_global_presence.py --audit-user-state --audit-live-state --audit-git
```

This final gate proves that every required source, policy, test, and verifier is
actually tracked rather than merely present in a dirty working tree.
