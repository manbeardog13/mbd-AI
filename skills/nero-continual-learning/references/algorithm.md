# Evidence-Gated Contextual Skill Evolution (EGCSE)

## Contents

1. Design objective
2. State model
3. Episode learning
4. Resource routing
5. Lesson lifecycle
6. Rehearsal and quarantine
7. Competence backlog
8. What the algorithm cannot do

## 1. Design objective

EGCSE improves a frozen hosted agent by evolving external evidence, routing
statistics, and reusable skills. It does not update model weights and does not
grant new tools or authority.

Optimize for five properties:

- **utility:** repeated task success and quality;
- **truth:** no lesson activates without outcome evidence;
- **transfer:** evidence spans distinct contexts;
- **stability:** incremental updates do not erase established detail;
- **reversibility:** every lesson can be quarantined or retired.

## 2. State model

The ledger contains:

- `episodes`: bounded outcomes with task kind, tags, context hash, resource,
  success, quality, latency, and short sanitized note;
- `routes`: Beta evidence and mean latency for `(task_kind, resource)`;
- `lessons`: testable statements and lifecycle state;
- `evaluations`: pass/fail scores and distinct context hashes;
- `revision`: monotonic optimistic-concurrency marker.

Lesson states:

```text
candidate -> active -> quarantined -> retired
     |          |            |
     +----------+------------+-- explicit review may revise into a new candidate
```

No transition grants permissions or starts a model.

## 3. Episode learning

For a successful episode with quality `q` in `[0,1]`, use reward `r=q`. For a
failed episode, use `r=0`. Update Beta routing evidence:

```text
alpha <- alpha + r
beta  <- beta  + (1-r)
quality_mean = alpha / (alpha + beta)
```

Update latency as an online arithmetic mean. Store a context hash rather than raw
task content. Cap episode history so growth remains bounded.

## 4. Resource routing

The caller supplies resources actually available in the current host. For each
candidate, calculate:

```text
quality_ucb = min(1, posterior_mean + exploration_bonus)
capacity    = 1                                      if within latency target
              latency_target / observed_mean_latency otherwise
route_score = quality_ucb * capacity
```

The multiplicative capacity term prevents very low latency from compensating for
bad quality through an additive reward. Exploration is bounded and decreases as
evidence accumulates. Cold candidates remain eligible but never become available
unless the host supplied them.

## 5. Lesson lifecycle

A lesson statement must specify a bounded causal rule and falsifier. Exact
duplicates are deduplicated by normalized fingerprint.

Promotion gates:

- candidate state;
- at least three passing evaluations;
- at least two distinct context hashes;
- zero failed evaluations;
- average score at least `0.80`;
- explicit approval.

Confidence uses a conservative Beta-style posterior over evaluation rewards. A
promotion starts at the shortest review interval; it is not permanent truth.

Relevant active lessons are ranked by task-kind match, tag overlap, confidence,
and review freshness. Limit retrieval to avoid context collapse and instruction
conflict.

## 6. Rehearsal and quarantine

Successful reviews expand on this schedule:

`1, 3, 7, 14, 30, 60, 90 days`

A failure resets the interval to one day. Two consecutive failed evaluations
quarantine the lesson. Quarantined lessons are never injected or used for routing
until a revised candidate passes the full gate.

## 7. Competence backlog

Generate tasks from evidence gaps:

1. due active-lesson rehearsals;
2. quarantined lessons needing root-cause analysis;
3. candidates missing passes or context diversity;
4. task/resource routes with little evidence;
5. recurring failed episodes needing a new skill or test;
6. active lessons not yet compiled into durable skill/test artifacts.

Backlog generation is deterministic. Hosted reasoning may design the exercise or
implementation, but completion must return evidence to the ledger.

## 8. What the algorithm cannot do

EGCSE cannot create omniscience, consciousness, independent goals, hidden model
access, or guaranteed correctness. It cannot make a weak evaluator trustworthy
by repetition. It improves the external learning loop only to the extent that
tasks produce meaningful, independently checkable outcomes.

