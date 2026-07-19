# ADR-0027: Protected-trunk repository governance for orchestrated work

**Status:** Proposed  
**Date:** 2026-07-18  
**Owner:** Toni  
**Decision scope:** Git history, worktree ownership, CI, review, and publication

## Context

The public repository has divergent histories, a task branch as its GitHub
default, no branch protection or rulesets, no required checks, and several
long-lived worktrees. The orchestrator roadmap would increase the number of
executors and therefore amplify any ambiguity about base SHA, branch ownership,
approval, and publication.

Nero's Constitution requires incremental verified PRs, explicit confirmation
for dangerous actions, a modular monolith, and strangler-fig migration rather
than big-bang rewrites.

## Decision

Adopt one canonical `main` with short-lived lower-case host-scoped branches and
one worktree per branch. Agents fetch and observe the remote before planning;
`git pull --ff-only` is limited to clean `main`; task branches reconcile
explicitly and published history is never rewritten.

Every change enters `main` through a squash PR with deterministic CI,
dependency review, resolved conversations, and Toni's exact merge approval.
Remote rules block direct pushes, force pushes, deletions, and merge commits,
with no bypass actors. CODEOWNERS requests Toni on critical paths. Until another
collaborator exists, the required approval count remains zero to avoid an
impossible self-review gate; Toni's merge confirmation is the human boundary.

Repository policy is versioned in `governance/`, checked by `repoctl.py`, and
mirrored by a disabled GitHub ruleset template. Remote activation is a separate
approved migration after histories converge and checks have run successfully.

The code tree will not be moved wholesale to a new package layout. New
orchestration code grows as a bounded module beside the working app, and legacy
code moves only in independently verified slices.

## Consequences

Good:

- one visible source of truth and consistent history;
- mechanical blocks against the highest-risk Git mistakes;
- explicit ownership across hosted execution lanes;
- reproducible evidence before publication;
- a safe base for later orchestrator automation.

Costs:

- initial reconciliation is deliberate and conflict-heavy;
- Toni performs the final merge action until an independently trusted reviewer
  is added;
- some agent convenience is traded for fetch/preflight/receipt discipline;
- ruleset activation waits for bootstrap CI evidence.

## Alternatives considered

- Git Flow branch families: rejected as excess state for a solo maintainer.
- Direct-to-main with local hooks: rejected because hooks are bypassable and do
  not protect GitHub.
- Immediate mandatory peer approval: rejected because the only collaborator
  cannot approve their own PR.
- Big-bang `src/` migration: rejected as constitutional and operational risk.
- Merge queue now: deferred until sustained parallel PR volume justifies it.
