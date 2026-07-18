# Repository governance

This directory is the machine-readable policy layer for repository operations.
It does not grant permission to commit, push, merge, release, or alter GitHub.
Those actions still require Toni's current approval for the exact action and
destination.

- `repository-policy.json` is enforced by `scripts/repoctl.py` and the local
  pre-push hook.
- `github/repository-settings.json` records the desired remote state.
- `.github/rulesets/main.json` is an importable, disabled ruleset template.
- `verify/verify_repository_governance.py` validates the policy package.

Human-readable rules and the activation order live in
`docs/repository/GIT_POLICY.md` and `docs/repository/MIGRATION_PLAN.md`.
