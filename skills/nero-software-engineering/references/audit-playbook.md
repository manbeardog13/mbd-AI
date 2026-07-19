# Evidence-based code audit playbook

## Contents

1. Audit contract
2. Inspection order
3. Finding classes
4. Security threat surfaces
5. Severity and confidence
6. Falsification and evidence
7. Report format

## 1. Audit contract

Confirm scope, revision/diff, supported platforms, threat model, and whether the
request is read-only review or includes remediation. Never edit during a review-
only request. Preserve unrelated worktree changes.

Review behavior, not aesthetics. A finding must identify a reachable failure,
violated invariant, exploitable trust boundary, compatibility break, or material
operational risk.

## 2. Inspection order

1. Active instructions and architecture/decision records.
2. Diff and changed public interfaces.
3. Callers, callees, schemas, migrations, configuration, and generated boundaries.
4. Tests covering changed and failure paths.
5. Authentication, authorization, input, output, secrets, and external I/O.
6. Concurrency, transactions, retries, cancellation, cleanup, and recovery.
7. Build, package, deploy, observability, and rollback paths.
8. Native static analysis and narrowly relevant dynamic checks.

## 3. Finding classes

### Correctness

- wrong branch, boundary, state transition, ordering, or default;
- type/shape mismatch, truncation, overflow, precision, null/missing handling;
- partial update, stale cache, lost write, duplicate processing, non-idempotence;
- incorrect error propagation, retry, timeout, or cancellation behavior;
- resource leaks and cleanup failures;
- compatibility break in API, ABI, schema, storage, or serialization.

### Security and privacy

- authentication or authorization bypass;
- injection in command, SQL, template, path, URL, deserialization, or code-loading
  boundaries;
- secret exposure, unsafe logging, overly broad data collection, or unintended
  egress;
- path traversal, symlink/race abuse, unsafe archive extraction, or file-permission
  errors;
- request forgery, cross-site scripting, cross-site request forgery, origin/CORS
  errors, and unsafe redirects;
- cryptographic misuse, weak randomness, replay, signature/certificate errors;
- supply-chain, plugin, dependency, or update trust failures;
- unsafe defaults, disabled validation, or confirmation/security-gate bypass.

### Concurrency and distributed behavior

- data races, deadlocks, lost wakeups, unsafe publication, and mutable shared state;
- message reordering, at-least-once duplication, split-brain assumptions, and
  missing idempotency;
- transaction isolation, lock duration, retry storms, thundering herds, and
  unbounded queues;
- timeout/cancellation leaks and work continuing after the caller abandoned it.

### Reliability and operations

- startup/shutdown ordering, health/readiness lies, migration sequencing;
- unbounded memory/disk/network growth or expensive work on hot paths;
- destructive or irreversible deploy without backup/rollback;
- misleading metrics, swallowed errors, missing correlation, alert noise;
- platform, locale, timezone, encoding, filesystem, or case-sensitivity failures.

### Tests and maintainability

- a changed invariant has no regression check;
- a test asserts implementation detail while missing observable behavior;
- nondeterministic time/random/network dependence;
- generated or vendored code edited at the wrong source;
- duplication or abstraction that creates a concrete divergence risk.

## 4. Security threat surfaces

Trace every path from an untrusted source to a sensitive sink:

- HTTP/RPC/message input -> parser -> validation -> authorization -> state change;
- user/repository text -> shell, SQL, template, browser DOM, path, or interpreter;
- uploaded/archive content -> storage/extraction -> execution or serving;
- credentials/tokens -> process environment/config/logs -> external connector;
- model/tool output -> capability invocation -> confirmation/security gate;
- dependency/update/plugin -> provenance/verification -> execution.

Check both direct exploitation and confused-deputy behavior where trusted code
acts with more authority than the requester.

## 5. Severity and confidence

Use impact plus likelihood, not drama:

- **P0 Critical:** immediate catastrophic compromise, irreversible broad data loss,
  or active production emergency.
- **P1 High:** reachable security boundary bypass, corruption, major outage, or
  severe compatibility break under realistic conditions.
- **P2 Medium:** material correctness, reliability, privacy, or performance defect
  with bounded impact or additional preconditions.
- **P3 Low:** real but limited defect, hardening gap, or maintainability issue with
  a demonstrated future failure path.

State confidence as high, medium, or low. Omit speculative findings that cannot
identify a plausible trigger and impact; place important unknowns under residual
risk instead.

## 6. Falsification and evidence

Before reporting a suspected issue:

1. Trace the complete path and search for an existing guard.
2. Confirm language/runtime semantics with native tools or primary documentation.
3. Construct a minimal reproducer or reasoned execution trace.
4. Check whether tests intentionally establish the disputed behavior.
5. Distinguish pre-existing issues from regressions in the requested change.
6. Tighten the file/line anchor to the smallest responsible location.

Do not report a concern merely because a dangerous API name appears. Prove that
untrusted or invalid state can reach it without an adequate guard.

## 7. Report format

Lead with findings, ordered by severity. For each:

```text
[P1] Short imperative title
Location: path:line
Confidence: high
Invariant: what must remain true
Trigger: concrete input/state/path
Impact: observable failure or security consequence
Evidence: trace, tool result, or minimal reproduction
Remediation: smallest sound fix
Missing test: check that would have caught it
```

Then list assumptions, checks run, and residual risks. If no material findings
remain, say so plainly; do not invent filler.

