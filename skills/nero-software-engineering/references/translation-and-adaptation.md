# Behavior-preserving code translation and adaptation

## Contents

1. Define equivalence
2. Build a semantic inventory
3. Characterize the source
4. Design for the target ecosystem
5. Port in vertical slices
6. Prove equivalence
7. Adapt frameworks, APIs, schemas, and platforms
8. Cutover and rollback

## 1. Define equivalence

Agree on what must remain equivalent:

- public API and wire/storage formats;
- accepted inputs and produced outputs;
- error types/codes and failure timing;
- ordering, determinism, idempotency, and side effects;
- security and permission boundaries;
- latency, throughput, memory, and resource limits;
- platform/version compatibility;
- operational behavior, observability, and rollback.

Not every implementation detail should survive. Preserve observable contracts and
explicit invariants; adopt target-language idioms internally.

## 2. Build a semantic inventory

| Concern | Questions to answer before porting |
|---|---|
| Types and absence | Are null, missing, optional, zero, empty, and invalid distinct? |
| Numbers | What are widths, overflow rules, decimal/float behavior, NaN, rounding, and serialization? |
| Text | What encoding, normalization, collation, grapheme, and case rules apply? |
| Collections | Are iteration order, duplicate keys, mutation, equality, and hashing observable? |
| Errors | Exceptions, result values, panics, status codes, retries, or partial results? |
| Ownership | Who allocates, closes, disposes, frees, or retains each resource? |
| Concurrency | Threads, event loop, actors, coroutines, cancellation, backpressure, and ordering? |
| Time | Clock source, timezone, daylight saving, precision, monotonic deadlines, and test control? |
| I/O | Buffering, atomicity, permissions, paths, line endings, streaming, and partial reads/writes? |
| Serialization | Field names/numbers, optionality, defaults, unknown fields, versions, and canonical form? |
| Reflection/macros | What code generation or runtime discovery must be replaced? |
| Dependencies | Which behaviors are library-specific, licensed, native, or platform-bound? |
| Build/runtime | Toolchain version, flags, environment, packaging, deployment, and startup behavior? |

## 3. Characterize the source

Before rewriting:

1. Run the source tests and record the baseline.
2. Add characterization tests around undocumented but relied-upon behavior.
3. Capture representative fixtures and golden outputs.
4. Add property tests for algebraic or protocol invariants where valuable.
5. Record performance and resource baselines if they are acceptance criteria.
6. Isolate external systems behind fakes, contract fixtures, or replayable traces.

Treat source bugs deliberately. Preserve them only when compatibility requires it;
otherwise document the intentional correction and version the behavior change.

## 4. Design for the target ecosystem

Map concepts, not syntax:

- exceptions -> result/error types or target-native exceptions;
- callbacks -> promises/futures/coroutines with equivalent cancellation;
- inheritance -> composition, interfaces, protocols, or traits when idiomatic;
- shared mutable state -> ownership, actors, channels, or synchronization;
- macros/reflection -> code generation, traits, annotations, or explicit registries;
- RAII/disposal -> target-native lifetime/finalization with explicit cleanup;
- dynamic shapes -> validated types at the boundary;
- source package layout -> target-native modules and packaging.

Keep compatibility adapters thin. Do not force source-language architecture into
the target when a native design can preserve the same contract more safely.

## 5. Port in vertical slices

1. Establish a compiling/running target skeleton and test harness.
2. Port pure domain logic first where differential checks are cheapest.
3. Port one end-to-end slice including boundary parsing, domain behavior, output,
   and error handling.
4. Add external I/O, concurrency, and performance-sensitive paths incrementally.
5. Keep source and target runnable until cutover evidence is sufficient.
6. Avoid a big-bang rewrite unless the user explicitly accepts its risk and no
   incremental seam exists.

## 6. Prove equivalence

Use multiple forms of proof:

- run the same fixture corpus through source and target;
- normalize intentionally different non-semantic fields before comparison;
- compare return values, errors, side effects, logs/events, and persistent state;
- use property-based or fuzz differential tests for broad input spaces;
- test malformed, boundary, timeout, cancellation, and recovery paths;
- compare performance distributions, not one timing sample;
- test supported platforms and versions.

When exact equivalence is impossible, create an explicit divergence ledger:
behavior, reason, impact, migration instruction, and acceptance owner.

## 7. Adapt frameworks, APIs, schemas, and platforms

For a framework or API migration:

1. Keep the domain core independent of both old and new frameworks.
2. Define an adapter interface at the incompatibility boundary.
3. Add contract tests that both adapters must pass.
4. Translate lifecycle, dependency injection, transaction, auth, and error
   semantics explicitly.
5. Preserve wire compatibility or version endpoints/events deliberately.

For database/schema migration:

1. Make forward and backward compatibility windows explicit.
2. Prefer expand -> dual-read/write if necessary -> backfill -> verify -> contract.
3. Make migrations restartable and observable.
4. Validate row counts, constraints, hashes/samples, and rollback before cutover.

For platform adaptation:

1. Isolate filesystem, process, networking, UI, path, locale, and credential-store
   differences behind platform interfaces.
2. Test on the actual target, not only a compatibility layer.

## 8. Cutover and rollback

Define entry and exit gates:

- source baseline green;
- target native checks green;
- differential suite within accepted divergence;
- data/schema compatibility verified;
- observability and runbook ready;
- staged rollout or feature switch available where appropriate;
- rollback tested and data written during the new path accounted for.

Remove the source only after the target is proven in the real environment and the
rollback window has deliberately closed.

