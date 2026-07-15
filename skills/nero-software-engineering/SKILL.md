---
name: nero-software-engineering
description: Universal software engineering, code implementation, refactoring, debugging, testing, architecture, documentation, performance tuning, secure code review, repository auditing, and behavior-preserving translation or adaptation between programming languages, frameworks, platforms, APIs, and data models. Use for any task that creates, changes, explains, diagnoses, reviews, audits, migrates, ports, modernizes, or validates source code in any language, especially polyglot repositories and unfamiliar stacks.
---

# Nero Software Engineering

Engineer from evidence, not from claims of memorized mastery. Treat language
expertise as a repeatable process: discover the stack, recover the behavioral
contract, select native tools and specialist skills, make the smallest coherent
change, and prove the result in the target ecosystem.

## Start with the repository contract

1. Read the active instruction files and preserve user-owned changes.
2. Run `python scripts/detect_stack.py <root> --pretty` when the stack is not
   already obvious. Inspect the reported manifests, then read only the relevant
   build, dependency, test, lint, formatter, CI, and deployment files.
3. Identify the task mode: implement, diagnose, audit, refactor, optimize,
   document, migrate, translate, or adapt.
4. State the behavioral contract: inputs, outputs, invariants, compatibility,
   error semantics, performance limits, security boundaries, and acceptance
   checks. Infer missing details from tests and callers before inventing them.
5. Discover the smallest relevant installed specialist skill, plugin capability,
   MCP tool, or connector. Read a selected skill's complete instructions before
   use and keep this skill as the verification envelope. See
   `references/specialist-routing.md` and `references/host-resource-routing.md`.

## Route language knowledge on demand

Read `references/language-routing.md` for the detected language family and its
native proof tools. Do not load every language section. For a niche, new, or
version-sensitive language feature, verify against the language specification,
official compiler/runtime documentation, or primary project documentation.

Prefer, in order:

1. Repository tests and locked toolchain configuration.
2. Compiler, interpreter, type checker, linter, formatter, package manager, and
   language server output.
3. Official specifications and primary documentation.
4. Minimal isolated experiments.
5. General reasoning only where deterministic evidence cannot decide.

Never fabricate a flag, API, package version, language rule, or successful test.

## Implement and refactor

1. Trace the existing control flow, data flow, ownership, and public interface.
2. Add or identify a failing acceptance check for behavior-changing work.
3. Change the narrowest layer that owns the behavior. Preserve unrelated style,
   compatibility, generated files, lockfiles, and public APIs unless the request
   requires them to change.
4. Use idioms of the target language rather than transliterating syntax from a
   familiar language.
5. Run focused checks first, then the broader relevant suite. Build or type-check
   every affected target. Distinguish failures caused by the change from existing
   failures and report both honestly.

## Diagnose and debug

Reproduce before theorizing. Reduce the failure, inspect logs and state at the
boundary where expected and actual behavior diverge, and test one causal
hypothesis at a time. When the request is diagnosis-only, explain the root cause
and do not implement a fix. When a fix is requested, add a regression check and
verify the narrow and broad paths.

## Audit and review

Remain read-only unless the user also requests fixes. Read
`references/audit-playbook.md` and review the actual diff plus affected callers,
tests, configuration, schemas, and trust boundaries.

Report only actionable findings with:

- severity and confidence;
- exact file and tight line location;
- violated invariant or concrete failure mode;
- triggering input or execution path;
- impact;
- smallest sound remediation;
- missing test that would expose the issue.

Do not inflate style preferences into defects. If no material finding survives
attempted falsification, say so and name the residual risks or untested areas.

## Translate and adapt code

Read `references/translation-and-adaptation.md`. Translation means preserving a
behavioral contract while adopting the target ecosystem; it is not line-by-line
syntax replacement.

Before porting, inventory observable behavior, types, numeric rules, error
semantics, concurrency, ordering, resource ownership, serialization, time,
Unicode, platform assumptions, dependencies, and performance constraints. Build
characterization or golden tests around the source. Port in vertical slices,
then run differential tests against source and target where feasible.

For framework, API, schema, or platform adaptation, isolate incompatibilities
behind an adapter and preserve the domain model. Document intentional semantic
changes and provide a rollback or compatibility path for risky migrations.

## Verify proportionally to risk

Use the target ecosystem's native commands. A credible completion normally
includes the relevant subset of:

- format/lint;
- parse/compile/type-check;
- focused unit tests;
- integration or contract tests;
- security/static analysis;
- package/build validation;
- performance or allocation measurement;
- cross-platform or version matrix checks;
- differential tests for ports;
- documentation and example validation.

Never claim universal coverage or “grandmaster” quality from a single passing
test. Report what was actually proved, what was not run, and why.

## Preserve Host Mode boundaries

Use the hosted Codex or Claude model for Nero's reasoning. Local compilers,
interpreters, test runners, analyzers, databases, containers, and renderers are
execution tools, not Nero's mind. Never start Ollama, Qwen, a local conversational
model, or Nero's local API for this skill. Do not add startup daemons or warmups.

Use a local heavy renderer only when the requested artifact requires it and
follow the applicable render-orchestration skill. Preserve normal permissions;
do not bypass confirmation for destructive or consequential actions.

## Reference index

- `references/language-routing.md` - language families, semantic hazards, and
  native verification routes.
- `references/audit-playbook.md` - evidence-based correctness, security,
  reliability, and maintainability audit.
- `references/translation-and-adaptation.md` - behavior-preserving ports,
  migrations, and adapters.
- `references/specialist-routing.md` - selecting installed engineering skills,
  connectors, and deterministic tools without context bloat.
- `references/host-resource-routing.md` - combining Codex/Claude skills, plugins,
  MCP tools, GitHub, Hugging Face, browser/computer control, Visualize, GitKraken,
  and Ruflo without unnecessary startup work.

