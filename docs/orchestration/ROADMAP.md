---
id: orchestration.roadmap
title: Nero Orchestrator Delivery Roadmap
layer: operational
type: plan
status: active
owner: toni
version: 1.0.0
created: 2026-07-18
updated: 2026-07-18
sources:
  - off-repo: C:/Users/tonij/iCloudDrive/Nero AI/NERO_Orchestrator_Roadmap.md
  - docs/CONSTITUTION.md
  - docs/ROADMAP.md
related:
  - docs/repository/MIGRATION_PLAN.md
  - docs/adr/0027-repository-governance.md
  - docs/specs/review-inbox.spec.md
---

# Nero Orchestrator Delivery Roadmap

This incorporates Toni's living orchestrator draft without creating a second
conflicting set of Nero phases. The main roadmap retains its canonical phase
names; this program uses `OR-*` milestones.

## Mission

Give Toni one trustworthy task surface where Nero can prepare work, route it to
supported executors, collect evidence, request the right approval, and report a
truthful outcome without manual copy/paste between every step.

Nero remains a local-first modular monolith. Hosted Codex/Claude/ChatGPT are
adapters with explicit capabilities and provenance, not always-awake services
or shared consciousness. Cross-host continuity uses the approved explicit
ledger only when Toni asks; orchestration task state is not conversational
memory.

## Non-negotiable architecture

```text
Toni
  -> Review Inbox / Mission Control
  -> Orchestration application service
       -> task store + append-only events
       -> planner interface
       -> executor adapters
       -> verifier/reviewer adapters
       -> approval gate
       -> Git adapter
  -> evidence + truthful status
```

- One deployment and database boundary where practical.
- Domain objects do not import provider SDKs, GitHub clients, or UI code.
- Every external action passes through the existing capability registry and
  security gate.
- Adapters declare whether they support automatic invocation, manual handoff,
  polling, cancellation, and receipts. Unsupported wake/contact behavior is
  shown as unsupported, never simulated.
- Git is an output adapter, not the task database and not an approval oracle.
- No executor may commit, push, merge, message a person, release, or expose a
  service merely because a task reached "done".

## Core task envelope

Every work item carries at least:

- immutable task ID, parent ID, creator, created time;
- requested outcome and explicit non-goals;
- repository, observed base ref/SHA, branch, worktree, and scope paths;
- risk class and required approval transitions;
- assigned executor/reviewer identities and actual invocation provenance;
- attempt number with bounded retry policy;
- evidence commands, outputs/hashes, artifacts, and verifier verdicts;
- state, blocker, next action, and terminal receipt.

State transitions are append-only events with optimistic concurrency. A task
cannot skip from implementation to publication; every gate checks current
evidence, current Git state, and current approval scope.

## OR-0 - Repository convergence

Goal: one canonical protected `main` and deterministic publication policy.

Deliverables:

- reconcile the divergent remote/current histories;
- land CI, CODEOWNERS, dependency review, CodeQL baseline, policy verifier, and
  pre-push mechanical gate;
- make `main` the GitHub default;
- activate the no-bypass ruleset after first successful workflow runs;
- retire stale branches/worktrees only after evidence and approval.

Exit gate: `docs/repository/MIGRATION_PLAN.md` R0-R5 complete; a safe negative
test proves direct, force, delete, unresolved, and failing-check updates cannot
enter `main`.

## OR-1 - Domain and durable queue

Goal: a provider-neutral task model and single queue, with no automatic model
invocation.

Build beside existing code under `app/orchestration/`:

- typed task/event/approval/evidence models;
- SQLite schema and migrations owned by the orchestration module;
- command service with idempotency keys and compare-and-swap transitions;
- deterministic retry/attempt caps;
- read models for queued, running, waiting approval, blocked, and complete.

Exit gate: crash/restart preserves task state; duplicate commands cannot repeat
an external action; invalid transitions fail closed; migrations round-trip on a
copy; no provider or Git operation occurs in domain tests.

## OR-2 - Manual executor and evidence loop

Goal: Toni can submit a task, approve its bounded plan, hand it to Codex, and
return structured results without reconstructing state.

Build:

- planner output schema with acceptance criteria and non-goals;
- executor packet and result receipt;
- manual Codex adapter first, because it is observable and debuggable;
- automatic evidence capture for commands, changed paths, test summaries, and
  current Git state;
- cancellation, timeout, stale-result, and duplicate-result handling.

Exit gate: one real repository task completes from inbox to verified result
with no manual copy of branch/SHA/scope; the adapter never claims Codex was
invoked unless a supported channel actually returned a receipt.

## OR-3 - Independent review and approval routing

Goal: route the right evidence to an independent reviewer and surface one
deduplicated approval queue.

Build:

- policy-derived review packets isolated from executor conclusions;
- architecture, security, test, and documentation review types;
- verdict schema: `SHIP`, `SHIP_WITH_CONDITIONS`, `DO_NOT_SHIP`, `BLOCKED`;
- approval scopes with expiry, exact target, and consumed receipt;
- Familiar/Mission Control states that report facts, never instructions.

Exit gate: executor cannot self-approve; stale evidence invalidates approval;
changed diffs dismiss prior review; notification dedupe passes adversarial
tests; approval never broadens from commit to push/merge/release.

## OR-4 - GitHub publication adapter

Goal: prepare publication safely while keeping Toni as final authority.

Build:

- read-only Git/GitHub status and divergence adapter;
- branch/worktree creation proposal and preflight;
- commit proposal with exact files/message but no implicit commit;
- approved push and PR creation adapters with receipts;
- CI/review polling; merge proposal; post-merge verification;
- rollback/revert proposal.

Exit gate: all negative paths are tested: dirty tree, wrong remote, wrong base,
stale fetch, protected destination, force refspec, failed CI, unresolved review,
expired approval, and changed diff. No test or failure can publish.

## OR-5 - Supported automation

Goal: reduce coordination only where adapters and policy can prove safety.

Candidates after OR-0 through OR-4 are stable:

- provider API invocation where credentials, costs, and data export are
  explicit and approved;
- progress streaming, cancellation, cost budgets, and bounded retries;
- parallel tasks only for disjoint scopes and separate worktrees;
- scheduled health checks that do not start services merely to monitor them;
- release workflow with protected environment and artifact attestations.

Exit gate: every automated action is idempotent, reversible or compensatable,
bounded, observable, cancelable, and covered by a risk/approval policy. A manual
mode remains available and produces the same task receipts.

## Deferred until evidence supports them

- dynamic self-selected agents without an allowlisted capability contract;
- automatic skill learning or self-modifying policy;
- background provider invocation without a supported wake/API channel;
- using provider-native memory as shared Nero continuity;
- microservices, event buses, Kubernetes, or cloud deployment;
- automatic merge/release;
- confidence numbers without calibrated measurement.

## Success measures

- Median Toni interventions per ordinary task, split by necessary approvals and
  avoidable coordination.
- Percentage of terminal tasks with complete provenance and reproducible
  evidence.
- Zero unauthorized external actions, publication escapes, or approval-scope
  escalations.
- Recovery time after process crash or stale executor response.
- False success/false contact claims: zero.
- Foreground latency overhead of orchestration excluding provider inference.

## Immediate next decision

Complete OR-0 before building queue or provider automation. Once the
reconciliation branch and remote activation are explicitly approved, create
the OR-1 task agreement and ADR for the task/event model.

## Changelog

- 1.0.0 (2026-07-18) - integrated Toni's draft with current constitutional,
  hosted-resource, continuity, and repository-governance boundaries.
