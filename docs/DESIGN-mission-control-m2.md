# Nero Mission Control — Milestone 2 verification design

**Status:** implemented locally with execution deliberately unavailable by default
**Governance:** [ADR-0018](adr/0018-core-owned-verification.md)
**Date:** 2026-07-15

## Outcome

Milestone 2 moves verification authority from worker-entered text into Nero
Core. It adds code-owned, content-addressed profile definitions with immutable
task bindings, compare-and-set run claims,
snapshot- and lease-bound evidence, completion gating, and an attention feed.
It does **not** add a production code-execution path. The production composition
uses `DisabledRunner`, which spawns nothing and returns a non-authoritative
`backend_unavailable` result.

```text
Operator browser
      |
      v
Mission Control API and dashboard
  |-- choose a known profile / request Core verification
  |-- never accepts command, args, env, executable, or backend
  |-- attention cursor projects durable Core events
              |
              v
Nero Core verification authority
  |-- code-owned, content-addressed profile definitions
  |-- immutable task profile bindings
  |-- task/version + Git snapshot + lease/fence validation
  |-- one CAS run claim; replay and concurrent claims fail closed
  |-- evidence hash + internally consistent event binding
  |-- only authoritative PASS may complete a task
              |
              v
Production DisabledRunner
  `-- no process, no provider, no local model, backend_unavailable

Future approved isolated runner (not included)
  `-- digest-pinned, offline, read-only, non-root, resource-limited sandbox

Separate Codex mobile automation (outside Core)
  `-- polls attention API while PC/automation/settings permit notification
```

## Profile contract

A verification profile is a code-owned manifest with a stable ID, positive
integer version, display metadata, a repository-relative harness label and
hash, required operating-system family and isolation capabilities, timeout,
and a canonical manifest digest. The manifest is data for Core policy; it is not
an HTTP-supplied command line.

Profiles are content-addressed by that digest. Once bound, the task's profile
ID/version/digest tuple is immutable; a changed harness produces a different
digest and fails resolution rather than silently changing the pinned policy.
The M2 registry hashes the harness from the installed Mission Control source
checkout (the source tree containing `verification.py`), not from an arbitrary
repository selected with `--repo`. This is sufficient while execution is
disabled. A future runner must carry and independently verify that trusted
harness binding before its result can become authoritative.

The profile closure contains ten files: the verifier wrapper plus the nine
test modules that it invokes. `harness_files` records the relative path and
SHA-256 digest of each member, while `harness_sha256` remains the wrapper digest
for compatibility. The canonical manifest covers the ordered full closure, so
changing a test while leaving the wrapper untouched still changes the profile
digest and invalidates a pinned task.

When a profile is bound to a task, Core stores all three identity fields:

- `verification_profile_id`
- `verification_profile_version`
- `verification_profile_digest`

Changing any field after a caller observed the task requires the current task
version and advances that version. A run re-resolves the profile from the
code-owned registry and rejects an unknown, removed, or digest-drifted manifest.
The profile identity is also copied into bounded worker packets returned by
assignment. M2 does not deliver those packets to a provider; a future or
external invocation can use the acceptance contract without gaining
verification authority.

## Run claim and evidence lifecycle

1. The task must be in `verifying`, at the exact expected version, with a pinned
   profile known to the current registry.
2. Core measures the repository itself. The claim binds canonical repository
   identity, worktree, local branch, HEAD, clean state, and conflict state. A
   write task also requires the live lease ID and exact fencing number held by
   the task owner.
3. Core atomically inserts one `running` attempt. A stale version, active run,
   reused receipt, or competing claim loses the compare-and-set race.
4. Core invokes the injected runner with a typed request. Capability and result
   scalars are validated at runtime without truthiness or numeric coercion; a
   string `"false"` and Boolean `False` as an exit code are invalid contracts. In the manual
   production composition this is exact `DisabledRunner`; it does not launch or
   contact anything.
5. Core makes its final backend-controlled capability read, then measures the
   profile, task, repository, and lease again with no backend callback after
   that closing snapshot. Snapshot or fence drift makes
   the result non-authoritative regardless of runner output.
6. For an authoritative write-task result, Core holds an immediate transaction
   on the canonical lease registry across the Core-state commit. No expired
   lease can be replaced by a higher fencing generation in that final gap.
7. Core canonicalizes the evidence, stores its SHA-256 digest, appends a
   verification event carrying the run ID and digest, and makes the terminal
   run immutable.
8. Only a `passed` result from a code-authorized backend whose typed capability
   contract satisfies the pinned profile may atomically set the task's
   `verified_run_id` and status to `complete`. Unavailable or failed production
   verification blocks or fails the task according to its terminal status and
   releases its managed write lease during orderly in-process finalization.

After the atomic run claim, Core owns orderly in-process recovery as well as
success. An unexpected caught post-claim exception is sealed as a
non-authoritative `error` run with
`VERIFICATION_INTERNAL_ERROR`, a Core-generated binding receipt, and no raw
exception text. The task becomes blocked and a managed write lease is released.
A process crash or power loss can temporarily leave a paired `running` row.
Such a row never authorizes completion and the repository-level active-run
constraint prevents a successor from silently overlapping it. A newly started
default `DisabledRunner` service seals claims older than 30 seconds as
non-authoritative `interrupted` and blocks their tasks. Core does not
automatically steal claims belonging to an arbitrary injected runner because
it cannot determine whether that external backend is still live.

Terminal statuses distinguish `passed`, `failed`, `blocked`,
`backend_unavailable`, `timed_out`, `stale`, `error`, and `interrupted`. The UI
shows these states directly instead of converting all failures into generic
test prose.

## Authority boundaries

The following inputs are never trusted as completion evidence:

- a Claude or Codex `AgentResult.tests_run` string;
- an operator-entered summary or checklist;
- a profile or runner's claim that it is authoritative;
- an HTTP field naming a command, path, argument, environment, image, or backend;
- a receipt from another task, task version, profile digest, Git HEAD, worktree,
  branch, or lease fence;
- evidence stored without a matching immutable run and event-chain record.

Database triggers make the event ledger and terminal-run rows append-only under
supported operations. Hashes and semantic cross-checks detect partial edits and
inconsistent projections; they are not authentication and do not defeat a
same-user actor able to rewrite the database, triggers, and complete chain.
Ordinary task and approval projections remain mutable through guarded Core
operations.

## Production runner boundary

The manual production composition uses only exact `DisabledRunner`. Its
capabilities explicitly say execution is unavailable and isolation is disabled. Its `run` method
returns structured unavailability evidence and is required to spawn zero child
processes. It never auto-starts Docker, Windows Sandbox, a provider, a local
model, or a voice/memory service.

Tests may inject an in-memory fake directly into `MissionControlService` to
exercise the positive completion path and hostile runner outputs. Test
fixtures are not selectable through the manual launcher, API, environment,
profile registry, or database. `MissionControlService` and `create_app(service=)`
remain public in-process dependency-injection seams, so arbitrary same-user
Python composition can supply another runner; that is outside the local
control-plane trust boundary. Core recomputes authority so a supplied runner
returning `passed` still cannot complete a task when its allowlist, capability,
snapshot, profile, or lease binding is wrong.

The capability object is a typed runner contract, not independent attestation.
That limitation is safe in M2 because the production backend allowlist is empty
and the only production composition is `DisabledRunner`. A future execution
backend must add a separately reviewed capability-attestation boundary before
it can enter the allowlist.

## M1-to-M2 migration

Initialization verifies the existing M1 event chain before schema mutation,
then uses one immediate transaction to add task profile columns, the
verification-run ledger, uniqueness indexes, immutability triggers, schema
metadata, and one `schema.migrated` event. A second initializer observes the
same current schema and makes no duplicate event or destructive change.
Legacy non-schema metadata did not have M2 event bindings, so migration removes
those rows and records one `meta.invalidated` tombstone per key. Tasks,
approvals, and the existing event history remain intact.

Migration behavior is deliberately conservative:

| Input state | M2 behavior |
|---|---|
| Clean M1 database | Transactionally upgraded; tasks, approvals, and events preserved; legacy non-schema metadata invalidated |
| Already-current M2 database | No-op and readable |
| Two concurrent initializers | One migration; both end on current schema |
| Corrupt M1 event chain | No schema mutation; initialization aborts safely |
| Schema version newer than M2 | No downgrade or mutation; initialization aborts safely |
| Missing/downgraded metadata mixed with M2 artifacts | No inferred re-migration; initialization aborts safely |
| M1 task already complete | Preserved as legacy, `verified_run_id` remains empty |

`schema_version` is reserved to the transactional migrator and cannot be
changed through general metadata writes. Integrity checks pair a running run
with its exact `verifying` task projection, pair every terminal receipt with
its exact task transition, recompute the complete profile manifest, and bind
the full final-workspace projection rather than only HEAD and cleanliness.

## Git receipt and inspection provenance

An explicit refresh strictly reads the validated tracked merge-ref
advertisement, fetches that ref into the object database without writing
`FETCH_HEAD`, and accepts freshness only when the advertised commit is present
locally afterward. It supplies an empty command-line refmap,
so repository-controlled `remote.<name>.fetch` destinations cannot rewrite
local heads, tags, replace refs, or remote-tracking refs. Tags, pruning,
submodules, maintenance, auto-GC, commit-graph use/writes, replacement objects,
shallow topology, and legacy grafts are disabled or fail closed for the
measured relationship.
Repository-selection environment variables are removed from every Git child;
the returned root must contain the requested path. Assume-unchanged and
skip-worktree index entries fail closed, submodule dirtiness cannot be hidden
by ignore configuration, and initial/final full HEAD, branch, tracked remote,
merge ref, URL, and worktree observations must agree. Scheduling performs a
second observation after its claim and refuses a mixed-binding packet.

The version-2 receipt records the canonical repository key, safe remote name,
redacted display URL, SHA-256 fingerprint of the exact raw URL, logical
upstream, exact validated merge source ref, advertised-and-fetched commit OID,
attempt/success times, success flag, and
reachability classification. Ahead/behind uses that persisted OID while the
receipt is fresh and the object remains present; manually editing a cached
remote-tracking ref cannot rebind the counts. Changing hidden URL userinfo,
query text, or an SCP-style username invalidates the fingerprint even when the
redacted URL looks identical. `fetch_succeeded` proves configured transport
reachability, not a person's credential identity or push permission.

Failed or malformed status output sets `inspection_ok=false` and blocks packet
preparation from guessed state. Failed or malformed `rev-list` output clears
freshness and withholds counts. Local `.` upstreams and unsafe option-like
remote names are not invoked. `local_only_branches` and
`remote_only_branches` describe cached local refs only;
`branch_inventory_scope=cached_local_refs_not_remote_verified` makes that limit
explicit. Packet context carries `inspection_ok` and
`git_observation_errors` as provenance.

## API and interface

The M2 surface adds profile discovery, profile binding, Core verification,
verification-run evidence, and a cursor-based attention projection. Verification
requests carry only the current task version. The verification request model rejects unknown
fields, including `command`, `args`, `env`, `executable`, `path`, and `backend`.
Advisory result payloads may contain additional data, but no advisory field is
ever interpreted as executable input.

`GET /overview`, `/tasks`, `/workers`, and `/git` are observational: they do
not expire leases, interrupt runs, append lifecycle events, or reconcile state.
Lifecycle reconciliation is the explicit protected `POST /reconcile` action.
The attention reader fixes an upper event-sequence snapshot for each page, so
an event appended during the read appears once on the next cursor instead of
being returned and replayed.

Every `/api/mc/*` call requires `X-Nero-Local: 1`; browser mutations additionally
require a matching loopback Origin/Host authority. FastAPI's Swagger, ReDoc,
and OpenAPI routes are disabled, so `/api/docs` and `/openapi.json` return 404.

Loopback Host and browser Origin/header checks reject common DNS-rebinding and
cross-origin mutation requests. They do not authenticate caller identity: a
same-user process can issue a loopback request or use the public Python
composition seams. This is a local browser boundary, not account isolation.

Health keeps provenance domains separate. `internal_state_ok` and
`internal_state_health` describe Core schema, event-chain, and verification
consistency. `repository_inspection_ok` and Git `inspection_ok` describe
whether repository state was safely measured. Worker results retain `source`
and `provider_contacted`; the interface does not collapse these into a generic
`ok` claim or imply that a packet adapter contacted a provider.

Claude and Codex packet adapters only construct bounded data and normalize
returned data; Mission Control does not contact either provider in M2.

The dashboard replaces the manual completion dialog with **Run Core
verification**. It labels the default backend unavailable, renders profile and
evidence hashes with safe wrapping, and uses touch targets of at least 44 CSS
pixels. “Needs attention” includes terminal verification problems, blocked or
failed tasks, milestone completions, and requested/decided approvals. The feed
is still loopback-only; Codex mobile automation can relay notifications, but a
phone cannot open the PC's `127.0.0.1` page directly. That notification path is
a separate Codex automation, not Core: it requires the PC to be awake, the
automation to be running, and mobile notifications to be enabled in Codex.
Its loopback poller must send `X-Nero-Local: 1` on every `/api/mc/*` request.
That relay is outside Core and may send attention or approval summary text
through Codex's hosted notification path; it is not a fully local channel.

## Security acceptance matrix

M2 verification must keep these negative cases covered:

- manual `complete` and worker `tests_run` evidence are rejected;
- top-level arbitrary commands, paths, arguments, environments, and backend
  selectors are rejected by the verification request schema, and no accepted
  advisory result field is executed;
- the production runner creates no subprocess and never yields authoritative
  PASS;
- repository-supplied fake runners exist only in tests and are not
  runtime-selectable; arbitrary same-user Python DI is outside the boundary;
- stale task versions, profile drift, Git drift, dirty/conflicted worktrees,
  wrong worktrees or branches, expired/replaced leases, and reused receipts fail
  closed;
- concurrent claims produce at most one active run;
- terminal run update/delete and evidence/event mismatch are detected;
- rehashed evidence still has to match every semantic run, task, profile, Git,
  backend, and lease field; a matching digest alone is insufficient;
- every `verification.started` event has exactly one running/terminal row and
  every row has exactly one matching start event;
- caught post-claim internal failures are sanitized, terminalized, and release
  leases; default disabled-backend startup reconciles >30-second abandoned
  claims to non-authoritative `interrupted`;
- current-schema tables, columns, indexes, predicates, and trigger definitions
  are validated rather than trusted by object name;
- the schema-version key is reserved, and corrupt, downgraded, mixed-artifact,
  or future-schema state never rewrites evidence;
- running-run/task projections and terminal receipt/task-transition pairs are
  exact; full profile manifests and final workspaces are semantically checked;
- attention cursors advance monotonically against an upper snapshot without
  duplicating earlier or concurrently appended items;
- raw remote fingerprints and fetched OIDs bind receipts; malformed Git output,
  replace refs, local upstreams, unsafe remote names, and hostile fetch
  destinations cannot manufacture trusted topology or rewrite protected refs;
- observational GETs never reconcile; the protected POST is the explicit
  lifecycle attempt, and external API discovery is disabled;
- static UI contains no manual verification evidence form and no local-history
  or remote-write Git route; explicit refresh changes no branch, tag, or
  remote-tracking ref and limits Git writes to fetch evidence, objects, and
  bookkeeping.

## Deferred deliberately

An isolated execution backend, image acquisition, container or Windows Sandbox
lifecycle, automatic hosted-worker dispatch, Git commit/push, remote dashboard
access, and phone-to-loopback networking remain outside M2. Adding any execution
backend requires its own threat-model review, authenticated approval design,
capability attestation, and negative tests. A same-user subprocess wrapper is
not an acceptable shortcut.
