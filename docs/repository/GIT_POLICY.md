---
id: repository.git-policy
title: Repository Git and Publication Policy
layer: core
type: standard
status: proposed
owner: toni
version: 1.0.0
created: 2026-07-18
updated: 2026-07-18
sources:
  - docs/CONSTITUTION.md
  - docs/adr/0005-security-gate.md
  - docs/adr/0027-repository-governance.md
related:
  - governance/repository-policy.json
  - docs/repository/MIGRATION_PLAN.md
---

# Repository Git and Publication Policy

This is the repository's human-readable Git contract. The machine-readable
subset is `governance/repository-policy.json`. Neither document grants an agent
permission to commit, push, merge, release, or change remote settings.

## Authority and invariants

1. Toni is the final authority for publication.
2. `main` is the only canonical integration branch.
3. A task has one named branch and one worktree. Two agents never write the
   same branch or worktree.
4. Remote state is observed with Git or GitHub APIs; it is never inferred from
   a prompt, dashboard label, or stale handoff.
5. Every change reaches `main` through a pull request and required checks.
6. Force pushes, direct pushes to `main`, remote ref deletion, and history
   rewriting of a published branch are forbidden.
7. A verifier failure is evidence. Do not weaken the verifier to obtain green.

## Change state machine

```text
observed base
    -> local task branch
    -> locally verified
    -> Toni approves exact push
    -> remote task branch + pull request
    -> CI/review green
    -> Toni approves exact merge
    -> squash merge to main
    -> remote task branch deleted
```

Approval does not flow forward automatically. Approval to edit is not approval
to commit; approval to commit is not approval to push; approval to push is not
approval to merge or release.

## Branches and worktrees

New branch names are lower-case and host-scoped:

- `codex/<short-slug>`
- `claude/<short-slug>`
- `human/<short-slug>`
- GitHub-managed `dependabot/...`

Use PR labels and Conventional Commit prefixes to express `feat`, `fix`,
`docs`, `refactor`, and `chore`; do not create permanent `feature/`, `review/`,
`experiment/`, or `hotfix/` branch families. A hotfix follows the same gates,
with priority changed rather than safety removed.

Before creating a task branch:

```powershell
git fetch origin --prune
git rev-parse origin/main
git worktree list --porcelain
git worktree add -b codex/<slug> "D:\mbd AI-<slug>" origin/main
```

The operator records the observed `origin/main` SHA in the task or PR. Do not
use `-B`, `--force`, or an already checked-out branch.

## Pull and synchronization rules

`git pull` is allowed only on a clean local `main` that tracks `origin/main`,
and only as:

```powershell
git pull --ff-only origin main
```

Task branches do not use `git pull`. They synchronize explicitly:

```powershell
git fetch origin --prune
git rev-list --left-right --count origin/main...HEAD
```

If the task branch is unpublished, it may be rebased locally onto
`origin/main`. Once published, do not rewrite it. Merge `origin/main` into the
task branch or create a fresh branch and cherry-pick the reviewed commits. A
divergence or conflict is a stop condition until it is reviewed.

## Push rules

Immediately before any approved push:

```powershell
git fetch origin --prune
python scripts/repoctl.py audit
git diff --check
python verify/verify_repository_governance.py
```

The push must name the exact source and destination:

```powershell
git push --set-upstream origin HEAD:refs/heads/codex/<slug>
```

The tracked pre-push hook blocks protected-branch pushes, deletions, force
updates, refspec renames, stale canonical bases, unknown remotes, and dirty
worktrees. It is a mechanical control only; it cannot prove human approval.

Activate it only after reviewing this policy:

```powershell
git config core.hooksPath .githooks
```

## Pull requests and merge

- Base: `main` only.
- Merge method: squash only.
- Required checks: `repository-policy`, `python-tests-3.13`,
  `python-tests-3.14`, and `dependency-review`.
- Required conversations must be resolved.
- CODEOWNERS requests Toni for critical paths. Because this is currently a
  single-collaborator personal repository, zero peer approvals are required;
  requiring one would make self-authored work impossible to merge. Toni's
  explicit merge action remains the approval boundary. Add an independent
  reviewer before raising the remote approval count.
- CodeQL runs on PRs and weekly but is not an initial merge blocker until its
  baseline is triaged.
- Delete the task branch after merge. Retain the PR, test logs, and ADR as the
  durable audit trail.

## Releases

No local tag push is allowed by the base policy. A release is a separate,
explicitly approved workflow from a verified `main` commit. The future release
workflow must use a protected GitHub environment, least-privilege token, pinned
actions, generated checksums, and artifact attestations for executable output.

## Recovery

- Wrong base before publication: create a fresh branch from `origin/main` and
  cherry-pick only reviewed commits.
- Wrong base after publication: close or supersede the PR; do not force-push.
- Accidental secret: stop, rotate it, remove it from history with a reviewed
  incident procedure, and invalidate any affected artifacts.
- Stale worktree metadata: inspect `git worktree list --porcelain`; prune only
  after the exact missing path and branch are verified.
- Remote/default divergence: follow `MIGRATION_PLAN.md`; do not change the
  default branch merely to make a dashboard appear green.

## Changelog

- 1.0.0 (2026-07-18) - proposed protected-trunk policy for the reconciliation
  and orchestrator program.
