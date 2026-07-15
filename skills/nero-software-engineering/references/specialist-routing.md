# Specialist skill and tool routing

## Contents

1. Routing principle
2. Capability map
3. Composition rules
4. Tool preference

## 1. Routing principle

Use this skill as the engineering and verification envelope. Add the smallest
installed specialist skill that materially improves the current task. Discover
skills at runtime because installed catalogs change; never assume a named plugin
or connector is available.

Before using a specialist skill, read its complete `SKILL.md`. If its instructions
conflict with the user's current request or repository rules, follow the higher-
priority instruction and preserve the useful non-conflicting workflow.

## 2. Capability map

| Task | Specialist capability to seek |
|---|---|
| Architecture or system decomposition | architecture/design decision workflow |
| Pull request or patch review | code-review workflow plus Git/GitHub connector when private PR context is needed |
| Reproduction and root-cause analysis | debug/debugging workflow |
| Test plan or coverage design | testing-strategy and error-handling workflow |
| API design or reference material | API-documentation workflow and official provider docs |
| Performance bottleneck | performance-tuning/profiling workflow and native profiler |
| Security review | security-focused scanner/review workflow plus the audit playbook |
| Platform/framework migration | migration workflow plus translation-and-adaptation reference |
| Deployment/release | deploy checklist for the actual provider/runtime |
| Documentation | code/documentation workflow after behavior is verified |
| GitHub issues, PRs, actions, releases | authenticated GitHub connector rather than public web scraping |
| Browser UI behavior | supported browser/computer-use tool plus native component/e2e tests |
| Rendered visual/code asset | render-orchestration or visualization skill, not a local reasoning model |

Examples of useful installed capabilities may include architecture, code review,
debugging, testing strategy, API documentation, performance tuning, platform
migration, deployment checklists, GitHub, browser control, and visualization.
Treat these as categories, not permanent names.

## 3. Composition rules

- Use one lead skill and at most the few specialists genuinely required.
- Do not preload unrelated skills “just in case.”
- Let the domain specialist choose process details; keep this skill responsible
  for repository contract, native verification, truthful evidence, and Host Mode
  boundaries.
- Prefer parallel read-only discovery only when the host supports it and results
  are independent. Preserve one coherent implementation owner.
- Never use another model merely to duplicate an answer. Use additional review
  only when it provides an independent, auditable perspective requested by the
  user or warranted by risk.

## 4. Tool preference

Prefer this order:

1. Existing repository commands and native language tools.
2. Purpose-built authenticated connector or MCP tool.
3. Deterministic filesystem, Git, database, compiler, analyzer, and test tools.
4. Supported browser automation for UI-only surfaces.
5. General web search using primary sources for unstable technical facts.

Never copy connector credentials into code, logs, prompts, or artifacts. Follow
normal confirmation rules for writes, publishing, deployment, purchases,
messages, credential access, and destructive operations.

