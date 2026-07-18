# Contributing to Nero

Nero uses a protected-trunk workflow. Read
`docs/repository/GIT_POLICY.md` before changing the repository.

1. Fetch explicitly and confirm the observed `origin/main` SHA.
2. Create one short-lived worktree and one host-scoped branch from that SHA:
   `codex/<slug>`, `claude/<slug>`, or `human/<slug>`.
3. Keep the change coherent. Update tests, verifiers, documentation, and an ADR
   when a boundary or architectural decision changes.
4. Run `python verify/verify_repository_governance.py` plus the relevant test
   suite and record exact evidence in the pull request.
5. Push only after Toni approves that exact branch and destination. Open a PR
   into `main`; never push directly to `main`.
6. Merge only after required checks pass and Toni explicitly confirms the
   merge. The repository uses squash merge and deletes the topic branch.

Never force-push, delete a remote branch by refspec, reuse one branch in two
worktrees, or use `git pull` on a task branch. Never weaken a failing gate to
make a change pass.
