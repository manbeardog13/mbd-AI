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

## What the M2 dashboard can do

- Inspect local Git state directly.
- Explicitly fetch the tracked merge ref into receipt-bound local evidence.
- Keep branch inventory explicitly scoped to cached local refs; refresh does not
  apply repository-controlled fetch destinations or rewrite branch/tag refs.
- Say the exact local-branch/upstream relationship in plain English.
- Queue bounded read-only or local-write tasks.
- Prepare a task packet through the Claude or Codex packet-adapter definition.
- Enforce one managed repository writer across all Git worktrees.
- Use task versions plus lease fencing so stale windows cannot overwrite newer
  state or release a successor's lease.
- Renew an active local-write lease only when the operator explicitly chooses
  **Keep lease**.
- Record approval evidence and every Core state transition.
- Display the trigger-guarded event timeline and internal consistency health.
- Pin an immutable task binding to a code-owned, content-addressed verification
  profile definition.
- Claim and record Core-owned verification attempts with task, Git snapshot,
  profile, and write-lease fencing bindings.
- Reject worker or operator prose as trusted completion evidence.
- Display terminal evidence hashes with internal consistency checks, explicit
  backend-unavailable states, and a cursor-based **Needs attention** feed for
  milestones and pending decisions.
- Keep overview, task, worker, and Git GETs observational; lifecycle expiry and
  interruption are attempted by the protected **Reconcile** action.

The worker assignment buttons move a task to `preparing`, may acquire a managed
write lease, and return a deterministic packet to the browser. They do not
contact Anthropic or OpenAI, deliver the packet to a provider, or pretend a
worker replied.

The production verification backend is intentionally disabled in M2. Choosing
**Run Core verification** records that no approved isolation backend is
available; it starts no process and cannot mark the task complete. Positive
verification is covered with an explicitly injected fake in offline tests, not
by a switch available to the launcher, browser, environment, or database.

Mission Control's Host/Origin checks are a local browser safety boundary, not
login authentication. Any process already running as the same Windows user is
outside that boundary. Event hashes detect partial or inconsistent edits; they
are not authenticated proof against a same-user actor who can rewrite the whole
database and chain.

Mobile milestone notifications come from the separate Codex automation. They
require this PC to be awake, the automation to be running, and mobile
notifications to be enabled in Codex; the phone does not connect directly to
this PC's `127.0.0.1` dashboard. The local poller must send
`X-Nero-Local: 1` on every `/api/mc/*` request.
The automation is outside Core and may relay milestone or approval summary text
through Codex's hosted notification path, so mobile notification is not a fully
local channel.

Swagger, ReDoc, and external OpenAPI discovery are disabled. Health reports
Core consistency as `internal_state_ok` and repository measurement separately
as `repository_inspection_ok`; there is no generic `ok` claim. Advisory worker
records also show their `source` and whether Mission Control contacted a
provider.

## What it cannot do

- It cannot commit, merge, pull, rebase, reset, checkout, or push.
- Approving a remote action cannot execute it.
- A successful fetch proves read reachability, not credential identity or push
  permission; failure categories are heuristic.
- Receipt freshness binds the exact raw-URL fingerprint and fetched commit OID.
  Hidden URL changes invalidate it, while edits to cached tracking refs cannot
  rebind ahead/behind. Replacement objects and hostile fetch destinations are
  excluded from the measured topology.
- It cannot stop an unrelated manual Git command outside Core's lease.
- It does not share the legacy memory database or continuity ledger with a
  worker automatically.
- It does not start from a greeting or ordinary hosted Nero conversation.
- The disabled verification backend cannot execute the verification harness or
  repository test code, or manufacture authoritative PASS. Git inspection
  suppresses repository hooks, fsmonitor, optional index locks, implicit object
  fetching, and replacement topology. Worktree status may still invoke a
  locally configured clean/filter helper; an explicit fetch may use Git's
  configured transport and credential helper.
- It cannot auto-start Docker, pull an image, start Windows Sandbox, or select a
  permissive runner through an API field or environment variable.

## Verify it

Run the focused, offline verifier:

```powershell
.\.venv\Scripts\python.exe verify\verify_mission_control.py
```

The verifier's Git fixtures are configured only with disposable repositories
and local bare remotes. It contains no GitHub, Ollama, hosted-worker, or voice
service call; the production verification composition remains DisabledRunner.

For the original Core and preservation map, see
[DESIGN-mission-control-m1.md](DESIGN-mission-control-m1.md). For the M2
verification authority, threat boundary, migration rules, and acceptance
matrix, see [DESIGN-mission-control-m2.md](DESIGN-mission-control-m2.md) and
[ADR-0018](adr/0018-core-owned-verification.md).
