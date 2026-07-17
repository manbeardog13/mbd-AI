---
name: nero-continual-learning
description: Evidence-gated continual learning for Nero using outcome episodes, causal lesson proposals, multi-context evaluation, contextual routing across available skills/tools/models, spaced rehearsal, regression quarantine, and competence backlogs without model fine-tuning. Use when Toni asks Nero to learn, improve continuously, retain lessons from completed work, strengthen skills, choose better resources, audit weaknesses, rehearse competencies, or evolve reusable playbooks safely.
version: 1.0.0
lifecycle: permanent
owner: shared
verified_by: verify/verify_nero_learning_hybrid.py
---

# Nero Continual Learning

Use **Evidence-Gated Contextual Skill Evolution (EGCSE)**. Improve Nero's
external skills and context from verified outcomes while keeping the hosted base
model frozen and the security boundary intact.

This is not fictional instant omniscience. Never claim that Nero has learned a
subject merely because text was stored. Knowledge becomes active only after it
survives tests in multiple contexts.

## Preserve the hosted boundary

- Use the active Codex or Claude hosted model for interpretation, reflection,
  lesson drafting, and planning.
- Use only models, tools, skills, plugins, and MCP capabilities actually exposed
  by the current host. Never invent access or attempt to unlock hidden models.
- Never start Ollama, Qwen, Nero's local API, a local conversational model,
  embeddings, fine-tuning, or a background learning daemon.
- Keep the ledger cold. Read or write it only for a genuine learning task or the
  user-authorized maintenance automation; never preload it for greetings.
- Do not store raw prompts, source files, credentials, connector data, hidden
  instructions, private conversations, or chain-of-thought. Store bounded task
  classes, tags, hashes, outcomes, and user-approved lesson text.

## Run the learning loop

1. **Observe:** after a completed task, record task kind, non-sensitive tags,
   selected resource, success, quality, latency, and a short outcome note.
2. **Reflect:** use hosted reasoning to propose a causal lesson: situation,
   action, expected result, limits, and falsifier. Do not store vague praise or
   “always do X” rules without a testable boundary.
3. **Evaluate:** test the candidate in at least three successful evaluations
   spanning at least two distinct contexts. Record failures as evidence.
4. **Promote:** activate a lesson only when deterministic gates pass and Toni or
   the normal host confirmation path explicitly approves promotion.
5. **Retrieve:** inject only active lessons relevant to the current task kind and
   tags. Keep the retrieved set small.
6. **Route:** rank only the currently available candidate resources using
   quality evidence multiplied by latency capacity, with bounded exploration.
7. **Rehearse:** retest active lessons on an expanding schedule. Two consecutive
   failures quarantine a lesson automatically.
8. **Curate:** consolidate exact duplicates, investigate conflicts, retire stale
   lessons, and turn evidence gaps into a prioritized competence backlog.

Read `references/algorithm.md` for the state machine and mathematics,
`references/governance.md` for promotion and privacy rules, and
`references/research-basis.md` when explaining the research basis.

## Use the deterministic ledger

The self-contained tool is `scripts/learning_ledger.py`. It uses a versioned JSON
ledger, atomic writes, and a short-lived lock. It has no third-party dependencies
and does not contact a model or network service.

Use an explicit ledger path for repository work:

```powershell
python scripts/learning_ledger.py --ledger "D:\mbd AI\data\continual-learning.json" status
```

Common operations:

- `record` - add a bounded outcome episode and update resource-routing evidence.
- `propose` - add a testable candidate lesson.
- `evaluate` - record a pass/fail evaluation in a distinct context.
- `promote --approved` - activate an eligible lesson after confirmation.
- `retire --approved` - remove a stale or unsafe lesson from retrieval with an
  auditable reason.
- `recommend` - rank a supplied list of currently available resources.
- `lessons` - retrieve relevant active lessons.
- `backlog` - list due rehearsals, candidates lacking evidence, quarantines, and
  underexplored routes.
- `audit` - validate ledger structure, states, IDs, duplicates, and route values.

Never pass secrets in `--note`, `--statement`, tags, task kinds, resource names,
or context labels.

## Turn learning into durable skills

When an active lesson generalizes across tasks:

1. Update the narrowest relevant canonical skill or reference file.
2. Add or update an executable test or verifier that proves the lesson.
3. Validate the skill and deploy it through its existing synchronization path.
4. Preserve rollback and do not overwrite unrelated user instructions.
5. Record the implementation outcome as a new episode; do not treat the edit as
   self-validating.

Never rewrite global identity, permission, security-gate, or model-routing rules
automatically. Propose those changes for explicit review.

## Produce a useful learning report

Report:

- episodes added and their bounded fields;
- candidate lessons and exact missing evidence;
- promotions or quarantines with reasons;
- current resource ranking and uncertainty;
- due rehearsals and prioritized improvement tasks;
- skill/test changes actually implemented;
- checks run, failures, and remaining limits.

Learning quality is measured by repeated task outcomes, not by ledger size.
