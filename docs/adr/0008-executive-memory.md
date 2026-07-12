# ADR-0008 — Executive Memory (the working-state register)

**Status:** Accepted (2026-07-12, Toni)

## Context
Nero already has two forms of memory:
- **Long-term memory** — layered, typed facts and episodes accumulated over time
  (append-heavy, retrieved on demand).
- **World Model** — continuity about Toni and the world: what is *true out there*
  and what threads are ongoing.

Neither answers the meta-cognitive question **"what am *I* doing right now, and
where?"** — the current goal, the active project and git branch, the task in
progress, what is blocking it, and the intended next action. Without an explicit,
always-current representation of that:
- *"Continue."* forces expensive, lossy reconstruction from history;
- a multi-step agent-loop task has no durable notion of its own objective and
  drifts across steps;
- the Phase-2 Workspace and Executive Planner would have nothing concrete to read.

## Decision
Add **Executive Memory** — a small, structured, always-current register of the
AI's own working state, kept **distinct** from long-term memory and the World
Model.

- **Fields (bounded, typed):** `goal`, `project`, `branch`, `task`, `blocker`,
  `next_action`. Deliberately small — this is a *register*, not a log. Extendable
  later, but every new field must earn its place.
- **Three stores, three jobs — kept separate on purpose:**
  | Store | Answers | Lifecycle |
  |---|---|---|
  | Long-term memory | "What do I know?" | grows over time, retrieved |
  | World Model | "What's true about Toni / the world?" | persists, continuity |
  | **Executive Memory** | **"What am I doing now, and where?"** | **resets per goal** |
- **Maintained deterministically wherever possible** (Principle of Least
  Intelligence, Constitution §3): `project`, `branch`, and `cwd` are **observed**
  from git and the filesystem — *knowable, never reasoned, never hallucinated.*
  Only the intent fields (`goal`, `blocker`, `next_action`) may use light LLM
  summarization, and only when they actually change.
- **A single current record, persisted**, updated at agent-loop boundaries (turn
  start/end, task transitions). It is injected into the prompt as "current working
  state" and surfaced in the UI.
- It is the **foundation the Phase-2 Workspace and Executive Planner consume.**
  Building the register now — small and cheap — means those later features *read*
  state instead of reconstructing it.

## Consequences
- ✅ *"Continue."* resolves from the register, not from replaying history — the
  Phase-2 continuity criterion becomes reachable.
- ✅ The agent loop carries a durable objective across a multi-step task, reducing
  drift on long tasks.
- ✅ Deterministic fields cost nothing and can't hallucinate — the branch is
  *read*, not guessed.
- ⚠️ Another store to keep consistent. Mitigation: it is a **single row with a
  tiny typed schema**; stale-after-crash is acceptable because the deterministic
  fields are simply re-observed on the next turn.

## Alternatives considered
- **Fold working-state into the World Model** — rejected: conflates "state of the
  world" with "state of my own task." Different lifecycles (the world persists;
  working state resets per goal) and different maintainers (observed vs.
  continuity-tracked). Muddies both.
- **Reconstruct working-state from long-term memory each time** — rejected: slow,
  lossy, and exactly the reconstruction *"Continue."* exists to avoid.
- **No explicit working-state** — rejected: the loop drifts on long tasks and
  cross-session continuity is impossible.
