---
id: repository.reconciliation-report-2026-07-19
title: "Complete local repository reconciliation report"
layer: operational
type: report
status: active
owner: shared
created: 2026-07-19
updated: 2026-07-19
---

# Complete local repository reconciliation report

## Decision and scope

The repository was reconciled locally in the isolated worktree
`D:\mbd AI-reconcile-repository` on branch `codex/reconcile-repository`.
No push, force-push, pull request, default-branch change, ruleset activation,
repository-setting change, branch deletion, or tag deletion was performed.

The canonical history was determined by reachability and repository content,
not names:

- `c9ad17f` is the coherent Core/coherence base. It already contains the work
  represented by `origin/main`, the current GitHub default branch, architect
  memory, M1 repair, continuity integration, and orchestrator integration.
- `9d5d77d` is a genuine 15-commit Voice Platform line not reachable from that
  base.
- `57d97bc` is a genuine 34-commit recovery/canon/identity/inbox/Familiar/
  Voidbound line not reachable from that base.

Both divergent lines were merged with merge commits so every original commit
and both parent relationships remain addressable.

## Preservation controls

- The original worktree at `D:\mbd AI` remains on `codex/ORCHESTRAION`; its
  pre-existing tracked and untracked work was not committed, reset, stashed,
  overwritten, or deleted.
- Before creating the isolated worktree, all non-ignored uncommitted work was
  captured with an alternate Git index as
  `uncommitted.patch` (95,646 bytes), SHA-256
  `6793C5F6723F3A08506B3A1F9F60D9E762E6C627DA9F1264FD53E1E085CB161A`.
  The patch remains outside the repository in the task-specific temporary
  directory as a recovery belt-and-suspenders copy.
- The ignored original file `.codex/environments/environment.toml` stayed only
  in the original worktree and was not read into or copied through the patch.
- `git fetch origin --tags` was completed before reconciliation decisions. It
  did not prune or delete any ref. No tag existed at the fetched snapshot.
- The later config verifier created a default ignored `config.yaml` in the
  isolated worktree; it was removed as generated verifier output and was not
  committed.

## Branches and refs analyzed

| Ref | Fetched/analyzed tip | Disposition |
|---|---:|---|
| `origin/main` | `0b78e42` | Ancestor of canonical Core base; incorporated |
| `origin/claude/github-repo-verification-vor5iw` | `e3c7dc6` | GitHub default at fetch; ancestor of canonical Core base; incorporated |
| `origin/claude/architect-memory` | `334bf71` | Ancestor of canonical Core base; incorporated |
| `origin/claude/m1-verifier-gate-repair` | `41c47db` | Ancestor of canonical Core base; incorporated |
| `origin/claude/voice-system-v121` | `9d5d77d` | 15 unique commits; merged as a parent |
| `origin/claude/rescue-dirty-worktree-20260715` | `57d97bc` | 34 unique commits; merged as a parent |
| `codex/nero-host-continuity-integration` | `c125b1a` | Ancestor of canonical Core base; incorporated |
| `codex/nero-orchestrator-integration` | `2d06921` | Ancestor of canonical Core base; incorporated |
| `codex/nero-coherence-reset` | `c9ad17f` | Selected content-evidenced Core base |
| `codex/nero-mission-control-m1` | `41c47db` | Alias of analyzed M1 repair tip |
| `codex/nero-mission-control-m2` | `c9ad17f` | Alias of selected Core base |
| `claude/rescue-dirty-worktree-20260715` | `57d97bc` | Local alias of analyzed recovery tip |
| `codex/ORCHESTRAION` | `57d97bc` | Original worktree branch; left untouched |
| local `claude/github-repo-verification-vor5iw` | `91af05e` | Stale local tracking branch; remote tip separately analyzed |

No branch or tag was deleted, renamed, reset, or force-moved.

## Commits incorporated

### Voice Platform line (15)

`570a3e1`, `f2a744d`, `5951c14`, `44395b9`, `d4dc2d7`, `1bfcdff`,
`ff8ec1b`, `b186c42`, `b2d6745`, `151460e`, `3ddde95`, `1efb849`,
`9de1e20`, `edce249`, `9d5d77d`.

These are Voice Stages 1-13 plus their architecture/status documentation.

### Recovery/canon/identity/Familiar/Voidbound line (34)

`bbc4a8f`, `ede7c86`, `91af05e`, `4a6d224`, `5e4960c`, `efd1a9b`,
`fb4a729`, `3a09fcc`, `9cdb2b8`, `7e2a538`, `15b2276`, `6d159f5`,
`9ef6e2d`, `7dbb6aa`, `eb34997`, `6ab3db1`, `b9a679a`, `dd3184b`,
`ca40058`, `bdc935c`, `a8dddd9`, `674605c`, `0ef87e2`, `a7a3039`,
`5b95a4d`, `95aa846`, `9424e27`, `4c97682`, `3e6966a`, `b328d3e`,
`de7498e`, `db4fc3b`, `c56f4eb`, `57d97bc`.

These preserve the zero-start recovery, canon migration, identity evolution,
review inbox hardening, Desktop Familiar, School evidence, and Voidbound work.

### Reconciliation and restored-governance commits

| Commit | Purpose |
|---:|---|
| `74a5083` | Merge the complete Voice Platform line without conflict |
| `f8c7325` | Merge the recovery line with deliberate semantic resolutions |
| `f0ec3c9` | Add protected-trunk workflows, policy, hooks, and repository tooling |
| `2e4fcd7` | Add Git policy, migration research, ADR-0027, and orchestration roadmap |
| `6a16457` | Make installed-skill conformance newline-portable while retaining binary byte checks |

All commits already reachable from `c9ad17f` are incorporated through ancestry;
none were replayed or duplicated.

## Conflicts and semantic resolutions

The Voice merge was clean. The recovery merge produced 24 conflicted paths:

| Path | Resolution |
|---|---|
| `.claude/hooks/brief-staleness-check.sh` | Kept the later advisory-only shell stop hook; it cannot authorize Git mutation and no SessionStart hook was introduced. |
| `.claude/settings.json` | Kept the recovery hook wiring because it matches the retained shell hook; hosted startup remains disabled. |
| `.claude/skills/nero-continuity/SKILL.md` | Kept the hardened, live-tested continuity contract and added the later lifecycle metadata. |
| `.gitignore` | Kept recovery/Familiar/School exclusions, then layered the approved governance exclusions. |
| `AGENTS.md` | Kept the later hosted-only and School protocol block. |
| `PROGRESS.md` | Used the later product state, then applied the approved governance status update. |
| `README.md` | Used the later project/canon structure, then applied the approved repository-governance rewrite. |
| `app/capabilities/builtin/__init__.py` | Registered both unique behaviors: Core `fs.read` and the recovery integration catalog. |
| `app/main.py` | Kept the later lifecycle, collaboration, adventure, presence, and canonical voice surface; retained the hard hosted-only lock. The unique Core capability remains wired through the combined registry. |
| `audit/nero-continuity/AUDIT.md` | Retained the later hardened verifier evidence from the Core line; added canon frontmatter and updated moved host-document paths. |
| `audit/nero-continuity/proposed-global-claude-block.md` | Retained the non-deployed proposal and added canon metadata; nothing was deployed globally. |
| `audit/nero-continuity/test-evidence.json` | Retained the stronger 14-gate/240-sample hardened evidence rather than the older builder-only evidence. |
| `audit/nero-continuity/verify_result.json` | Retained protected-path and semantic cold-sample gates from the hardened run. |
| `continuity/README.md` | Retained verifier-guard and live-control details; added canon metadata and the moved handoff path. |
| `docs/NERO_CONTINUITY_PRIVACY.md` | Retained the hardened privacy contract and added canon metadata. |
| `docs/PROJECT_BRIEF.md` | Kept the later canon/identity/Familiar/Voidbound project state; Voice code and ADR history remain preserved independently. |
| `docs/adr/0016-cross-host-continuity-ledger.md` | Retained the evidence-backed live-round-trip status rather than regressing to “pending live Codex verification.” |
| `docs/adr/README.md` | Combined every decision. Duplicate 0017/0018 identifiers were resolved: Core boundary/verification remain 0017/0018; canonical knowledge and skill lifecycle moved to unique 0028/0029 paths with references updated. Governance is 0027. |
| `docs/reviews/2026-07-14-zero-start-host-presence-audit.md` | Retained the substantive audit and added canon metadata. |
| `tests/test_nero_global_presence.py` | Retained the stronger no-preload/no-publication hook assertion, adapted to the retained shell hook. |
| `verify/verify_nero_continuity.py` | Retained linked-worktree protected-root resolution, protected-file gates, and semantic cold-sample checks. |
| `verify/verify_nero_global_presence.py` | Kept the later canon-migrated guide paths. |
| `voice/__init__.py` | Combined the independent Voice Platform boundary with the later Director/rendering architecture description. |
| `voice/profiles/__init__.py` | Exposed both profile systems without type collision: manifest `VoiceProfile` is `CastVoiceProfile`; Director `VoiceProfile` keeps the public name. |

The governance patch then conflicted on three generated/index files. ADR entries
were unioned, both canon changelog entries retained with the corrected ADR-0028
reference, and `docs/canon/INDEX.md` was deterministically regenerated rather
than hand-merging stale counts.

## Intentionally excluded or deferred

- No commit or unique source work was excluded.
- Duplicate branch aliases were not replayed because their commits are already
  ancestors; replaying them would create duplicates rather than preserve work.
- Generated `config.yaml`, `__pycache__`, and other runtime artifacts were not
  committed.
- The aggregate `verify_everything.py` wrapper was not invoked because it probes
  Ollama/local APIs, GPU, embeddings, standalone memory, and local speech. Those
  paths are forbidden by the current hosted-only contract. Its safe offline
  components were run individually.
- The standalone continuity performance verifier was not run in this hosted
  session because its protection gate hashes the standalone app's
  `data/memory.db`, which hosted Nero must not read. All 50 continuity tests,
  including its verifier-guard tests, passed against isolated temporary data.
- Local audio/GPU/VRAM/latency and audible-persona checks remain reserved for an
  explicitly launched standalone RTX-4070 workflow; the model-independent Voice
  verifier passed without synthesizing audio.
- Remote publication and every GitHub mutation are deferred for Toni's explicit
  approval.

## Resulting local commit graph

```text
6a16457  fix(verify): normalize deployed skill line endings
2e4fcd7  docs(governance): define reconciliation policy and orchestration roadmap
f0ec3c9  feat(governance): add protected-trunk repository control plane
f8c7325  merge(history): recovery/canon/Familiar/Voidbound
|\
| 57d97bc  recovery/canon/identity/Familiar/Voidbound tip (34 unique commits)
74a5083  merge(voice): preserve complete Voice Platform history
|\
| 9d5d77d  Voice Platform V1.2.1 tip (15 unique commits)
c9ad17f  Core/coherence base
|-- c125b1a  continuity integration
|-- 2d06921  orchestrator integration
|-- 41c47db  M1 verifier repair
|-- 334bf71  architect memory line
|-- e3c7dc6  fetched GitHub default line
`-- 0b78e42  origin/main
```

The final report/School-ledger commit is intentionally added after this report
is finalized; its hash is recorded in the handoff summary.

## Verification results

### Complete collected tests

Pytest collected **530 tests**. Every collected test passed, plus **86 subtests**:

- remaining application matrix: 402 passed, 50 subtests;
- Mission Control Git: 31 passed, 7 subtests;
- Mission Control verification authority: 37 passed, 18 subtests;
- repository leases: 4 passed;
- continuity: 50 passed, 11 subtests;
- School tooling/graders: 6 passed.

The initial all-in-one invocations timed out at 120 seconds and 600 seconds
without a result. Isolation proved this was suite duration, not failure: the
Mission Control verification file alone took 319.85 seconds, and the remaining
application matrix took 214.19 seconds.

### Standalone deterministic verifiers

All authorized deterministic/offline verifiers passed:

- repository governance: 13 checks, 3 workflows;
- canon: current deterministic index, 87 valid unique frontmatter blocks,
  resolved links/banners, 29 consistent ADRs;
- global hosted presence and Claude presence;
- capability registry, `fs.read`, executive memory, security gate (32
  adversarial attempts, 0 escapes), config loading, and offline memory logic;
- integrations catalog (37 plugins, 253 skills, no MCP server launched);
- learning/hybrid skills and software-engineering skill deployments;
- Nero textual voice (19 probes) and Voice Stages 1-13 model-independent checks;
- Familiar v2 including temporary source compilation;
- Review Inbox (33 checks including concurrency, injection, provenance, and
  migration controls);
- Voidbound Codex static/security contract;
- School structure/protocol;
- Identity Review: 6/6 green;
- Mission Control packaged verifier: 134 tests in 552.24 seconds, PASS.

Warnings were limited to 875 FastAPI/Starlette deprecation warnings for
`asyncio.iscoroutinefunction`; no correctness failure resulted. No ESET scan was
run, per the standing rule.

## Safest publication sequence

1. Perform an independent read-only review of this branch and this report.
2. After explicit approval, push only `codex/reconcile-repository` as a new
   remote branch with a normal non-force push. Re-fetch and verify its exact OID.
3. Open a draft PR targeting `main`. Do not squash or rebase: use a merge commit
   so the Voice and recovery parent histories remain intact.
4. Require the repository CI, CodeQL, dependency review, canon, governance, and
   full offline tests to pass on GitHub. Resolve any platform-only failure with a
   new reviewable commit; never rewrite this branch's published history.
5. Obtain independent semantic review of the 24 conflict decisions and the ADR
   renumbering before marking the PR ready.
6. Merge only after Toni's explicit approval. Fetch and verify that all analyzed
   tips remain ancestors of the merged commit.
7. In a separate approved operation, change the default branch to the reconciled
   `main`, then activate the prepared ruleset and repository settings. Verify
   enforcement with a non-destructive test branch.
8. Only after a stability window, inventory fully merged legacy branches and
   request separate approval before deleting any branch. Preserve tags and an
   immutable reconciliation receipt.

## Final boundary

The local reconciliation is complete. Publication is intentionally stopped at
the approval gate. This report is the sole basis for the next remote decision.
