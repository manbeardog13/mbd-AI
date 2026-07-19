# Nero

> [!IMPORTANT]
> **Hosted-only lock:** the standalone local Nero runtime, local model, project
> server, memory preload, and local voice launch paths are hard-disabled under
> ADR-0014. Active Nero Host Presence is static hosted context. Do not run the
> historical launchers or treat `data/memory.db` as shared hosted memory.

Nero is Toni's local-first cognitive-assistant project and its evidence-gated
host integration repository. The codebase is a modular monolith with explicit
security, capability, continuity, presence, voice, Familiar, School, and
verification boundaries.

## Start here

Read in this order:

1. [The Nero Constitution](docs/CONSTITUTION.md) - governing law.
2. [Canon start page](docs/canon/README.md) - source hierarchy and master index.
3. [Project brief](docs/PROJECT_BRIEF.md) - current narrative snapshot.
4. [Repository Git policy](docs/repository/GIT_POLICY.md) - branch, pull, push,
   review, and publication rules.
5. [Repository migration plan](docs/repository/MIGRATION_PLAN.md) - current
   history reconciliation and remote-enforcement sequence.

## Repository safety state

The live 2026-07-18 audit found a public repository with a task branch as the
GitHub default, divergent histories, no rulesets, no `main` protection, and no
required CI. The local governance package in this branch does **not** mean those
remote settings are fixed. Remote reconciliation, default-branch changes,
ruleset activation, push, merge, and publication each require Toni's exact
approval.

Inspect the local state without changing it:

```powershell
python scripts/repoctl.py audit
```

## Architecture at a glance

```text
Hosted identity plane (static, zero-start)
    -> Codex/Claude execution lanes with explicit capabilities
    -> guarded repository work and evidence

Standalone application plane (hard-disabled until deliberately revived)
    app/ -> agent loop, capability registry, security gate, state, web shell
    continuity/ -> explicit cross-host ledger, separate from local app memory
    presence/ + familiar/ -> opt-in presentation and semantic state
    voice/ -> dormant standalone presentation components

Governance plane
    docs/ + ADRs + specs
    governance/ + .github/ + .githooks/
    tests/ + verify/
    School/ -> separately governed shared training evidence
```

## Canonical layout

```text
.github/       CODEOWNERS, PR template, pinned CI/security workflows, ruleset
.githooks/     local mechanical Git safety hooks
governance/    machine-readable local and desired GitHub policy
docs/
  adr/         architectural decisions - why
  specs/       boundary contracts - what must hold
  canon/       knowledge standard, index, audits, canonical structure
  repository/  Git policy, research baseline, reconciliation plan
  orchestration/ orchestrator program roadmap
app/           modular-monolith application code
continuity/    explicit continuity ledger subsystem
presence/      presence contracts and runtime bridges
familiar/      desktop Familiar assets/runtime source
voice/         standalone voice components
skills/        evidence-gated Nero skills
School/        School protocol, tasks, grading, and audit evidence
scripts/       deterministic maintenance and policy tools
tests/         automated tests
verify/        repository and subsystem verification spine
audit/         dated initiative evidence bundles
```

Runtime data, downloaded models, local configuration, generated output, and
private databases remain untracked.

## Verification

Use the project virtual environment when available:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests continuity/tests `
  School/tooling/test_schoolctl.py School/tooling/test_task_graders.py -q
.venv\Scripts\python.exe verify/verify_repository_governance.py
.venv\Scripts\python.exe verify/verify_canon.py
.venv\Scripts\python.exe scripts/build_canon_index.py --check
```

Do not run `verify_everything.py` for hosted-presence work: it includes dormant
standalone/local-model checks. Select the deterministic verifier relevant to the
current scope.

## Plans

- [Authoritative Nero roadmap](docs/ROADMAP.md)
- [Orchestrator delivery roadmap](docs/orchestration/ROADMAP.md)
- [Repository convergence gate](docs/repository/MIGRATION_PLAN.md)
- [Progress log](PROGRESS.md)

The orchestrator is not a license for unattended publication or simulated
cross-host contact. Every adapter must report its real capabilities and every
consequential transition remains inside the security and approval gates.

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) before creating a branch or worktree.
Do not report vulnerabilities or secrets publicly; follow
[SECURITY.md](SECURITY.md).
