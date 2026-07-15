# Using Nero Mission Control

Mission Control is a local control dashboard for Nero's deterministic Core. It
does not start Nero's old local model, voice system, or memory database, and it
does not run automatically.

## Start it manually

The first time, create a small Python environment for Mission Control:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-mission-control.txt
```

This installs the web shell and offline test client only. It does not download
or start a model, voice engine, or worker provider.

Then start Mission Control from the repository in PowerShell:

```powershell
.\.venv\Scripts\python.exe run_mission_control.py
```

If this checkout uses a different Python environment, run its Python with the
same file. Then open [http://127.0.0.1:8765](http://127.0.0.1:8765).

To inspect another worktree:

```powershell
.\.venv\Scripts\python.exe run_mission_control.py `
  --repo "D:\path\to\worktree"
```

All linked worktrees resolve the same local state directory under Git's common
directory: `.git/nero-core/`. `mission-control.db` holds tasks, approvals, and
events; `write-lease.db` is the cross-process coordination database. Neither is
part of a commit or a GitHub push, and the path cannot be overridden from the
browser or launcher.

## Stop it

Return to the PowerShell window and press `Ctrl+C`. Nothing is installed as a
service and nothing is scheduled to restart.

## What the M1 dashboard can do

- Inspect local Git state directly.
- Explicitly fetch and refresh remote-tracking evidence.
- Say the exact local-branch/upstream relationship in plain English.
- Queue bounded read-only or local-write tasks.
- Assign a task packet to the Claude or Codex worker definition.
- Enforce one managed repository writer across all Git worktrees.
- Use task versions plus lease fencing so stale windows cannot overwrite newer
  state or release a successor's lease.
- Renew an active local-write lease only when the operator explicitly chooses
  **Keep lease**.
- Record approval evidence and every Core state transition.
- Display the append-only event timeline and integrity health.

The worker buttons prepare deterministic packets only. M1 does not contact
Anthropic or OpenAI and does not pretend a worker replied.

## What it cannot do

- It cannot commit, merge, pull, rebase, reset, checkout, or push.
- Approving a remote action cannot execute it.
- It cannot prove push permission from fetch authentication.
- It cannot stop an unrelated manual Git command outside Core's lease.
- It does not share the legacy memory database or continuity ledger with a
  worker automatically.
- It does not start from a greeting or ordinary hosted Nero conversation.

## Verify it

Run the focused, offline verifier:

```powershell
.\.venv\Scripts\python.exe verify\verify_mission_control.py
```

The verifier creates disposable Git repositories and a local bare remote. It
does not contact GitHub, Ollama, Claude, Codex, or any voice service.

For implementation details and the preservation map, see
[DESIGN-mission-control-m1.md](DESIGN-mission-control-m1.md).
