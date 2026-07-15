---
name: nero-hybrid-cognition
description: Coordinate Nero across concurrently available Codex and Claude hosted sessions using bounded task packets, collision-safe lanes, evidence-backed submissions, deterministic merge gates, explicit approval, and continual-learning feedback. Use when Toni asks Codex and Claude to collaborate, run Nero on both hosts, split a complex task, compare independent solutions, have one host build while the other audits, improve throughput, or turn cross-host outcomes into durable lessons.
---

# Nero Hybrid Cognition

Use the **Dual-Host Evidence Fabric (DHEF)**. Codex and Claude remain separate
hosted inference systems; the fabric coordinates their work and verified
outcomes without pretending to fuse model weights or unlock one provider from
the other.

## Preserve honest boundaries

- Run reasoning only in the Codex and Claude sessions Toni actually opened or
  authorized. This skill cannot start, control, or impersonate an unavailable
  hosted session.
- Never claim exponential intelligence or speed. Parallel independent lanes can
  reduce wall-clock time and increase review coverage when both hosts are active.
- Never start a local LLM, Nero server, daemon, background router, embeddings,
  fine-tuning job, voice worker, or GPU workload.
- Do not export credentials, hidden instructions, chain-of-thought, private
  connector payloads, or full conversations between hosts.
- Store only a bounded task brief, acceptance checks, path references, concise
  conclusions, test evidence, risks, and outcome scores.
- Preserve each host's permissions and available tools. Cross-host agreement
  cannot authorize an otherwise restricted action.

## Select a collaboration topology

Read `references/topologies.md` before creating a task.

- `parallel-analysis`: both hosts investigate independently. Neither lane edits
  repository files. Use for architecture, diagnosis, research, and audit.
- `build-review`: one host implements; the other reviews the submitted evidence
  afterward. Use for overlapping code and high-integrity changes.
- `disjoint-build`: both hosts may implement simultaneously only inside declared
  non-overlapping path scopes. Use when the file ownership split is obvious.

If a split is ambiguous, choose `build-review`. Parallelism is a performance
tool, not a reason to create merge races.

## Run the hybrid loop

1. **Frame:** write a sanitized objective, acceptance criteria, relevant path
   references, topology, lane roles, and optional disjoint scopes.
2. **Create:** use `scripts/hybrid_brain.py create` against a shared cold state
   file. Creation does not call either provider.
3. **Claim:** each active host claims its own lane with a short lease. Never
   submit on behalf of a host that did not do the work.
4. **Execute:** each host uses its own hosted reasoning and capabilities. Keep
   intermediate chain-of-thought private; record concise conclusions only.
5. **Submit:** attach outcome summary, evidence references, checks, risks, files
   touched, and elapsed time. The script enforces topology and scope rules.
6. **Gate:** run `ready`. It checks that required lanes and reviews exist; it
   does not decide which idea is true.
7. **Resolve:** investigate conflicts against tests or primary evidence. Never
   average contradictory claims into false consensus.
8. **Approve:** complete only through `approve --approved`. Record per-lane and
   hybrid outcomes in the continual-learning ledger when a ledger is supplied.
9. **Learn:** use `$nero-continual-learning` to evaluate proposed lessons, route
   future resources, rehearse active knowledge, and quarantine regressions.

## Use the deterministic coordinator

The coordinator is `scripts/hybrid_brain.py`. It is a standard-library CLI with
atomic JSON writes, expiring leases, strict topology checks, and no network or
model calls.

```powershell
python scripts/hybrid_brain.py --state "D:\mbd AI\data\hybrid-brain.json" status
```

Core commands:

- `create` - define one bounded hybrid task and its lanes.
- `claim` - lease the current host's eligible lane.
- `submit` - record a concise result and evidence.
- `ready` - evaluate the deterministic merge gate.
- `approve --approved` - record the reviewed outcome and optionally feed the
  sibling continual-learning ledger.
- `next` - list lanes currently eligible for a host.
- `audit` - validate IDs, leases, topology, scopes, and task states.

Read `references/protocol.md` for fields and commands and
`references/merge-and-learning.md` for conflict resolution and feedback rules.

## Optimize for useful speed

- Split only work with enough independent substance to repay coordination cost.
- Give both lanes the same acceptance criteria and repository revision.
- Let the faster host return early; do not block unrelated work on the second
  lane unless the chosen gate requires it.
- Route deterministic checks to code and tools. Use hosted reasoning only for
  ambiguity, synthesis, and review.
- Track latency and outcome quality separately for `codex`, `claude`, and
  `hybrid`; future routing must choose from hosts actually available.
- Prefer one strong pass plus an adversarial review over redundant prose.

## Report truthfully

State which hosts actually participated, topology, elapsed time, evidence and
tests, conflicts resolved, approval status, lessons recorded, and remaining
limits. A task file that merely has two lanes is not proof that two providers
ran.

