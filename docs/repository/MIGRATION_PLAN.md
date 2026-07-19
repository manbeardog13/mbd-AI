---
id: repository.migration-plan
title: Repository Reconciliation and Governance Activation Plan
layer: operational
type: plan
status: active
owner: shared
version: 1.0.0
created: 2026-07-18
updated: 2026-07-18
sources:
  - docs/repository/RESEARCH_2026-07-18.md
  - docs/repository/GIT_POLICY.md
related:
  - docs/orchestration/ROADMAP.md
  - .github/rulesets/main.json
---

# Repository Reconciliation and Governance Activation Plan

This plan repairs the current split history before remote enforcement is
enabled. Hashes are a 2026-07-18 snapshot and must be fetched and rechecked at
execution time.

## Current lines that must converge

| Role | Ref | Snapshot SHA | Relationship |
|---|---|---:|---|
| Intended trunk | `origin/main` | `0b78e42` | Ten commits absent from the current worktree |
| Current GitHub default | `origin/claude/github-repo-verification-vor5iw` | `e3c7dc6` | Diverged from `main`; must stop being default |
| Existing integration/fix line | `origin/claude/m1-verifier-gate-repair` | `41c47db` | Contains both remote lines and focused gate repairs |
| Latest local recovery line | `codex/ORCHESTRAION` | `57d97bc` before this task | Thirty-four unique commits; unpublished and ten commits behind `origin/main` |

PR #16 targets the wrong default branch and has no checks. Do not merge it in
its current form. Preserve it as evidence until the reconciliation PR
supersedes it.

## R0 - Freeze and record

Status: **local governance package building; remote unchanged**.

1. Stop non-emergency remote pushes and merges.
2. Fetch and record all remote refs, open PRs, rulesets, repository settings,
   and worktrees.
3. Create recoverable local bundles or safety refs for every source line.
   Publishing those refs requires separate approval.
4. Confirm no worktree has uncommitted user changes before any cleanup.

Exit: inventory signed off by Toni; every unique line has a recoverable object
ID and owner.

## R1 - Build one reconciliation branch

Start from `origin/claude/m1-verifier-gate-repair`, because the live merge
preview showed that it already contains both `origin/main` and the current
GitHub-default line. Create a new isolated worktree and branch such as
`codex/reconcile-repository`.

Merge the latest recovery/governance line into it with `--no-commit`. The
2026-07-18 `git merge-tree` preview identified conflict paths across host
configuration, continuity evidence, canonical docs, application integration,
and verifiers. Resolve each path against current primary evidence; never use a
blanket `ours` or `theirs` strategy. Preserve lane ownership and the current V2
host capsule.

Produce a reconciliation manifest listing:

- every conflicting path and chosen source;
- deleted/retired behavior that remains deleted;
- verifier/test evidence;
- unresolved semantic duplicates;
- the exact parent SHAs preserved by the merge.

Exit: clean reconciliation worktree; all deterministic suites green; no local
runtime, memory database, or voice process invoked.

## R2 - Publish one reconciliation PR

Requires Toni's exact approval for commit, push, and PR creation as separate
publication steps.

The PR targets `main`, not the stale default branch. Until the governance
workflows exist on a reachable remote ref, treat their first runs as bootstrap
evidence rather than pretending required checks already protect the branch.
Obtain an independent architecture/security review if another qualified
reviewer is available; otherwise document the single-reviewer limitation.

Exit: reconciliation PR green and explicitly approved for merge.

## R3 - Make `main` canonical

After the reconciliation merge and a fresh fetch:

1. Verify `main` contains every approved source line.
2. Change the GitHub default branch to `main`.
3. Retarget or close stale PRs; do not silently merge them.
4. Allow squash merge only and enable delete-branch-on-merge.
5. Enable Dependabot alerts/security updates and private vulnerability
   reporting.
6. Restrict Actions to approved sources, require full SHA pinning, and set the
   default `GITHUB_TOKEN` permission to read.

These are remote mutations and have not been performed by this task.

Exit: GitHub reports `main` as default and the repository settings match
`governance/github/repository-settings.json`.

## R4 - Activate enforcement

1. Run every new workflow at least once and confirm the exact check names.
2. Import `.github/rulesets/main.json` as disabled.
3. Compare the imported rule payload with the file.
4. With Toni's approval, activate it. GitHub Evaluate mode is Enterprise-only,
   so this personal public repository uses disabled review followed by active.
5. Attempt safe negative tests from a disposable branch: direct `main` push,
   force update, unresolved PR, and failed required check must all be blocked.

Exit: no bypass actors; direct/force/delete updates blocked; PR plus required
checks required for `main`.

## R5 - Clean branch and worktree debt

Only after R4 and per-ref verification:

- archive an evidence table for superseded branches;
- delete remote branches only with Toni's exact approval;
- remove linked worktrees only when clean and no longer needed;
- repair or prune the currently reported stale worktree metadata after its
  target is proven missing;
- rename future branches under the lower-case host-scoped convention.

Do not delete history merely for visual tidiness. The result is one canonical
trunk, short-lived branches, and preserved PR/ADR evidence.

## Rollback

If reconciliation or enforcement fails, disable the ruleset, leave `main` and
all safety refs intact, and revert the repository setting changes one at a
time. Never solve a governance lockout by force-pushing or deleting the only
known-good ref.
