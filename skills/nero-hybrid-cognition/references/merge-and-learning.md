# Merge and learning rules

## Evidence merge

1. Normalize conclusions into claims and acceptance checks.
2. Prefer executable tests, repository facts, and primary sources over host
   agreement.
3. Mark each material claim as corroborated, single-source, or conflicting.
4. For conflicts, run the cheapest discriminating check. If no check is
   possible, preserve the disagreement and lower confidence.
5. Do not merge code from concurrent lanes outside their declared path scopes.
6. Require explicit approval before a hybrid task becomes completed evidence.

Two matching answers are correlated opinions, not two independent facts, when
they share the same source or copied reasoning.

## Learning feedback

On approval, record three resource classes when evidence exists:

- `codex-hosted` for Codex's submitted lane;
- `claude-hosted` for Claude's submitted lane;
- `codex-claude-hybrid` for the reviewed aggregate.

Use the same task kind but distinct context hashes. Score quality from acceptance
checks and reviewer evidence, not fluency. Record failed and blocked lanes too;
hiding failures poisons the router.

Candidate lessons still pass the EGCSE promotion gate: three successful tests,
two distinct contexts, zero failures, average score at least 0.80, and explicit
approval. Cross-host agreement does not waive any gate.

## Throughput claims

Report measured wall-clock latency and participation. Never infer a 2x speedup
from the existence of two lanes. Parallel speedup is bounded by the sequential
portion, tool bottlenecks, coordination overhead, and the slower required lane.

