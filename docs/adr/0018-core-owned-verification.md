# ADR-0018: Core-owned verification authority

**Status:** Accepted
**Date:** 2026-07-15

## Context

Mission Control M1 let a worker return an `AgentResult` containing free-form
`tests_run` text. The scheduler accepted that text as the condition for moving
a task from `verifying` to `complete`. This made the audit trail useful as a
record of what a worker claimed, but it did not make completion independently
trustworthy. The same worker that changed the repository could describe its
own evidence, and the browser could submit an equivalent string directly.

Running a verification command directly on the host would not solve that trust
problem. Mission Control is a loopback application running with the operator's
desktop privileges. A same-user subprocess would inherit access to the host,
repository, credentials, devices, and network unless a real isolation boundary
removed them. Adding a generic command endpoint or an environment-selectable
test runner would therefore turn the dashboard into a code-execution surface.

## Decision

1. **Only Nero Core may create authoritative verification records.** Worker
   reports and operator text remain advisory. A generic task transition can
   never produce `complete`; completion requires one authoritative, passed
   `VerificationRun` bound to the task.
2. **Verification profile definitions are code-owned and content-addressed.** A
   task's bound profile ID, version, and canonical manifest digest are immutable
   after pinning. HTTP requests may select a known profile, but may not supply a
   command, executable, path, arguments, environment, backend, capability
   claim, or expected digest.
3. **Every run is compare-and-set and snapshot-bound.** Its claim records the
   task ID and version, profile identity and digest, repository/common-directory
   identity, worktree, branch, Git HEAD, clean/conflict state, and, for write
   work, the active lease ID and fencing number. Drift before or after execution
   invalidates authority. Authoritative write completion holds the canonical
   lease-registry write lock through the Core commit, preventing expiry and a
   successor fencing generation from racing the completion sink.
4. **Evidence is durable and internally consistent.** Terminal run rows carry
   canonical evidence plus its SHA-256 digest. Normal database triggers make
   terminal rows and Core events append-only through supported operations, and
   the hash chain records the run identity and evidence digest. Integrity checks
   cross-check both projections, so a partial edit or replay is detected. This
   is not authenticated tamper evidence: a same-user actor able to rewrite the
   database, triggers, and complete chain remains outside the trust boundary.
   Canonical hashes are necessary but not sufficient: integrity verification
   also compares the evidence's semantic task, profile, repository, snapshot,
   backend, and lease bindings with the immutable row and its start/terminal
   events.
5. **The production default is `DisabledRunner`.** It starts no process, does
   not contact a provider or local model, reports `backend_unavailable`, and can
   never return authoritative PASS. A fake runner exists only in tests through
   explicit dependency injection and cannot be selected through the manual
   launcher, HTTP, environment variables, profiles, or persisted data. The
   public in-process runner injection seam can still be used by arbitrary
   same-user Python composition, which is outside Mission Control's trust
   boundary rather than a hidden test mode.
6. **An execution backend is a separate future approval.** Before it can issue
   authoritative PASS it must provide an independently checked isolation
   capability set. The intended container boundary is digest-pinned and
   pre-installed, network-disabled, read-only, non-root, capability-dropped,
   deprived of host credentials/devices/Docker socket, and bounded by process,
   memory, CPU, time, and output limits. Core must never auto-pull an image or
   auto-start Docker. Windows-specific verification requires a Windows-capable
   isolation boundary; a Linux container cannot attest Windows behavior.
7. **Backend authorization is code-owned.** Core checks a runner's typed
   capability contract against a code-owned backend allowlist. Every scalar is
   runtime-validated without truthiness coercion, runner results require exact
   integer/Boolean/string types, and the final backend callback precedes all
   closing task/profile/Git/lease measurements. A runner's
   self-declared `authoritative` flag is ignored. M2 does not independently
   attest those capability claims and therefore keeps the production allowlist
   empty with `DisabledRunner` as the only production composition. A future
   backend must add independent attestation, and a one-time human approval must
   bind the exact task/version, snapshot, profile/digest, backend/image digest,
   and lease fence; it is not a reusable permission to execute arbitrary code.
8. **Migration fails closed.** M1 databases are upgraded transactionally only
   after their existing event chain verifies. Repeated or concurrent
   initialization is idempotent. A corrupt chain or schema newer than the code
   aborts initialization before mutation. Low-level safe reads remain possible
   to a caller that handles the failure, but the standard FastAPI lifespan does
   not launch a degraded dashboard. Existing M1-completed tasks stay visible as
   legacy records after a valid migration and are not relabelled Core-verified.
9. **An in-process claimed run must be terminalized.** Ordinary exceptions
   caught after the claim produce sanitized `VERIFICATION_INTERNAL_ERROR`
   evidence, block the task, and release a managed lease. Raw exception text is
   not durable evidence, and an unpaired `verification.started` event or
   running row fails integrity. A process crash or power loss can temporarily
   leave a paired running row; it never authorizes completion. On restart, the
   default `DisabledRunner` composition seals claims older than 30 seconds as
   non-authoritative `interrupted` and blocks the task. Core deliberately does
   not steal claims from arbitrary injected runners because it cannot know
   whether an external backend is still live.

10. **Observation, reconciliation, and provenance remain distinct.** Dashboard
    GETs read projections without reconciling leases or runs; reconciliation is
    an explicit protected POST. Core consistency and repository inspection have
    separate health fields, external API documentation is disabled, and
    advisory worker records retain source/provider-contact provenance. For an
    authoritative write completion, Core holds the canonical lease transaction
    through its final state commit so an expired/replaced generation cannot win
    the validation-to-completion gap.

## Consequences

- Mission Control can distinguish a worker claim, an internal chain-consistency
  result, and an authoritative verification result instead of presenting one vague
  confidence label.
- Installing M2 alone cannot make the verification backend execute the harness
  or repository test code. Attempts on the default backend produce durable
  attention evidence and block rather than manufacture success.
- Completion policy is stricter than M1, so old clients that submit
  `status=complete` receive a conflict instead of silently preserving the old
  behavior.
- A future sandbox backend is more work than a subprocess wrapper, but it can
  be reviewed and approved as an explicit security boundary rather than hidden
  inside a profile.
- Mission Control state under `.git/nero-core/` remains a same-user audit and
  coordination mechanism, not a defense against an administrator or an
  attacker already controlling Toni's account.
- Host and Origin checks reduce browser DNS-rebinding/cross-origin mutation
  risk, but caller identity is unauthenticated. Any same-user process can make a
  loopback request or construct Core directly.

## Alternatives considered

- **Trust `tests_run` when it looks detailed:** rejected because prose is not
  execution evidence and has no binding to the repository snapshot.
- **Let the browser submit a command:** rejected because a loopback page is not
  an authorization or isolation boundary.
- **Run the verifier as a local subprocess:** rejected for production because
  it would execute repository-controlled code with Mission Control's host
  privileges.
- **Let an environment variable select a fake or permissive runner:** rejected
  because configuration injection could convert production into test mode.
- **Mark existing M1 completions verified during migration:** rejected because
  historical evidence cannot be upgraded retroactively.
