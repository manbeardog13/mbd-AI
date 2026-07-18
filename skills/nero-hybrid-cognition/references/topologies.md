# Collaboration topologies

## Decision table

| Situation | Topology | Why |
|---|---|---|
| Diagnosis, architecture, threat model, independent research | `parallel-analysis` | Independent views expose blind spots without file collisions. |
| One coherent code path or overlapping files | `build-review` | The reviewer sees a stable implementation and evidence. |
| Clearly separable modules or test/docs split | `disjoint-build` | Both hosts can write concurrently inside non-overlapping scopes. |

## Parallel analysis

Both lanes may claim immediately. Repository writes are prohibited. Each lane
submits a bounded conclusion, primary evidence references, proposed changes,
tests to run, and risks. A later approved implementation is a separate task.

## Build-review

The declared builder claims first, implements, tests, and submits. The reviewer
becomes eligible only after the builder submission. The reviewer must record a
verdict of `pass`, `changes-requested`, or `blocked`. Only `pass` opens the merge
gate. A changed implementation requires a new builder submission and review.

## Disjoint build

Both lanes may claim immediately. Every touched path must fall within that
lane's declared scope, and scopes must not be equal or ancestor/descendant paths.
Shared manifests, lockfiles, generated indexes, and global configuration should
remain in a single integration lane after the parallel tasks.

## When not to parallelize

Use one host when the task is small, has a single sequential bottleneck, depends
on one unavailable connector, or would require copying sensitive data between
providers. Coordination overhead is a real latency cost.

