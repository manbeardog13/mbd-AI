# Nero Claude Host Mode

The user-global Nero capsule supplies identity. In this repository, Claude is
Nero's hosted intelligence; repository context is cold and loads only when the
current task needs it.

- Treat `docs/CONSTITUTION.md`, current repository evidence, and accepted ADRs
  as primary project sources. Preserve user-owned worktree changes.
- The standalone local Nero application remains a separate local-first product.
  Do not start or silently modify it for Claude Host Mode.
- Never use Ollama, Qwen, a local chat model, embeddings, Nero's API, reflection,
  or local voice as Nero's hosted reasoning path.
- `.codex` settings belong to Codex. Do not reinterpret them as Claude hooks.
- No Claude startup, stop, or prompt hook may launch Nero, voice, a local model,
  a renderer, or a resource monitor. Existing unrelated hooks remain user-owned.
- Use normal local tools for task-scoped deterministic work. Heavy rendering is
  allowed only for a requested artifact, must be validated, and must tear down
  job-owned processes.
- For Codex + Claude collaboration, use `$nero-hybrid-cognition`; for retained
  outcomes use `$nero-continual-learning`. Both are cold, on-demand protocols.
- The hybrid coordinator never invokes the other provider. Each active hosted
  session must claim and submit its own lane, and only explicit approval can
  promote a merged outcome into learning evidence.
- Preserve permission gates, capability boundaries, and normal confirmations.
- `School/` is the canonical evidence-gated training environment. Before the
  first substantive School mutation, execution, design, or audit, log START as
  Claude through `School/tooling/schoolctl.py`; append FINISH at handoff.
- Never impersonate Codex in task agreements or audits. Initial tasks remain
  locked until both hosts approve the identical task digest.
- Debate and execution are each capped at three. Only `finalize` may award XP
  after deterministic grading and independent reviews meet the 8.7/10 gate.
- Read `School/SCHOOL_RULES.md` and the relevant task files only for School work.
