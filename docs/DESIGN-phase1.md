---
id: docs.design-phase1
title: "Technical Design — Phase 1: The Hands"
layer: operational
type: plan
status: active
owner: shared
created: 2026-07-12
updated: 2026-07-17
---

# Technical Design — Phase 1: The Hands

*Design-before-code for the foundational phase. Scope: agent/tool loop, the
**Capability Registry**, **Executive Memory** (working-state register), security
gate, observability, human-in-the-loop terminal. Later phases are designed
just-in-time (Constitution: no half-finished experiments carried forward).
Governed by ADR-0001/0003/0005/0007/0008.*

## 1. Goal & non-goals
**Goal:** give Nero the ability to *take one verified action* and build on the
result — the single primitive every "hands" capability depends on — with a
security gate that makes it safe from the first tool, capabilities discovered
through one registry, and a working-state register that keeps the loop on task
and makes *"Continue."* cheap.

**Non-goals (Phase 1):** browser, full Workspace, planner, skills, voice, vision,
MCP, autonomous/unconfirmed execution. No event bus, no new process. (The
Capability Registry and Executive Memory ship in Phase 1 as the *seams* MCP,
Skills, Workspace and Planner later plug into — the seams, not those features.)

## 2. Module layout (in the existing monolith)
New packages under `app/`, each behind a typed interface (ADR-0001):

```
app/agent/      loop.py        # the reason→tool→observe cycle
                state.py       # Executive Memory: the working-state register (ADR-0008)
app/capabilities/ registry.py  # Capability interface + registration + dispatch (ADR-0007)
                  builtin/     # fs_read.py, git_status.py, terminal.py, … (the built-in provider)
app/security/   gate.py        # risk classification + confirmation + jail
app/obs/        metrics.py     # timing/counters (extends today's METRICS dict)
```
`app/main.py` gains an agent-mode chat path; nothing existing is deleted until the
new path is verified (strangler-fig). The registry is the **only** path from the
loop to an implementation — every dispatch goes through it, so the security gate
and metrics wrap one place (ADR-0007).

## 3. Interfaces (the contracts modules depend on — not implementations)

```python
# app/capabilities/registry.py
class Capability(Protocol):
    name: str                       # "fs.read", "git.status", "terminal.run"
    description: str                # shown to the model — it reasons over THIS
    args_schema: dict               # JSON Schema for arguments
    risk: RiskClass                 # SAFE | MEDIUM | HIGH | CRITICAL
    provider: str                   # "builtin" now; "mcp:<server>" / "skill:<id>" later
    def execute(self, args: dict, ctx: Context) -> Result: ...

class Registry(Protocol):
    def register(self, cap: Capability) -> None: ...
    def specs(self) -> list[dict]: ...          # → the prompt's tool list, built fresh each turn
    def dispatch(self, name: str, args: dict, ctx) -> Result: ...
    #   dispatch() is the ONE choke point: gate.authorize() + metrics wrap it,
    #   so no provider (builtin/MCP/skill) can bypass either (ADR-0007).

@dataclass
class Result:
    ok: bool
    output: str                     # fed back to the model (bounded/truncated)
    data: dict | None = None        # structured extras (exit code, paths, …)

# app/agent/state.py  — Executive Memory (ADR-0008)
@dataclass
class WorkingState:
    goal: str | None
    project: str | None             # observed from cwd/repo — not reasoned
    branch: str | None              # observed from git — not reasoned
    task: str | None
    blocker: str | None
    next_action: str | None
    # read() observes deterministic fields; update() summarizes intent fields
    # only when they change (Principle of Least Intelligence).

# app/security/gate.py
class SecurityGate(Protocol):
    def classify(self, cap: Capability, args: dict) -> RiskClass: ...
    # returns an approval decision; SAFE auto-approves, MEDIUM+ awaits the human
    def authorize(self, cap: Capability, args: dict, ctx) -> Decision: ...
```

`Context` carries the project-directory jail, the conversation id, the current
`WorkingState`, a metrics handle, and a `confirm(prompt) -> bool` callback wired
to the UI.

## 4. The agent loop (data flow)

```
user turn ─▶ retrieve memory + world + working-state (Exec Mem) ─▶ build prompt
        │                                    WITH registry.specs() (fresh each turn)
        ▼
        ┌───────────────────────────────────────────────┐
        ▼                                                │ observation
   model call (resident generalist) ──▶ tool call? ──yes─┤ fed back
        │ no                                             │ via registry.dispatch()
        ▼                                    ┌───────────┴───────────┐
   stream final answer                       │ gate.authorize()      │
        │                                    │  SAFE → run            │
        ▼                                    │  MEDIUM+ → confirm(UI) │
   persist + reflect + world update          │   approved → run      │
   + working-state update (Exec Mem)         │   denied → tell model │
   (existing background tasks)               └───────────────────────┘
```
- **Working-state (Executive Memory)** is read at turn start (deterministic
  fields observed fresh from git/cwd) and updated at turn/task boundaries — it
  keeps the objective in front of the loop and is what *"Continue."* reads later.
- **`registry.specs()`** builds the tool list the model sees *from the registry's
  live contents* — capabilities are never hard-coded into the prompt (ADR-0007).
- **Bounds:** `max_steps` (default 8), `max_seconds`, and cancellable. Hitting a
  bound returns a graceful partial answer, never a hang.
- **Tool specs** are offered via Ollama's tool-calling (`tools=[…]`); parsing is
  defensive (reuse the existing balanced-JSON + `<think>`-stripping robustness).
- **Streaming:** interim "using `git.status`…" status surfaces to the UI (turns
  the existing "thinking…" state into a live tool trace).

## 5. Confirmation UX
When `authorize()` needs a human, the stream emits a structured
`{"confirm": {tool, args, risk, preview}}` event; the composer shows an
**Approve / Deny** card (with a diff/command preview where available). Approve
resumes the loop; Deny feeds "user denied" back to the model. `SAFE` never
prompts; `CRITICAL` always prompts and is never remembered. Per-session
"remember this command pattern" is allowed for `MEDIUM` only.

## 6. Phase-1 capabilities (built-in provider; ship in this order, one PR each)
Each registers with the Capability Registry; the first PR builds the registry +
security gate + Executive Memory register together, then adds `git.status` as the
first capability through them.
1. `fs.read` (SAFE, jailed) — read a file in the project dir.
2. `git.status` / `git.log` (SAFE) — repo state.
3. `fs.list` (SAFE, jailed).
4. `terminal.run` (risk = **classified per command**, default MEDIUM; a denylist
   → HIGH/CRITICAL) — via ConPTY/pywinpty, persistent session, streams
   stdout/stderr/exit/cwd. **Human-in-the-loop.**
5. `fs.write` (MEDIUM, jailed, shows a diff preview).

## 7. Observability (Phase-1 slice)
Extend the existing `METRICS` dict + `/api/metrics`: per-turn step count, per-tool
call count + duration, confirmation rate, denial rate, loop wall-clock, and
scaffolding overhead (excl. inference). A tiny dev panel renders it. This is the
"data-driven" substrate every later optimization needs.

## 8. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Small model loops badly (wrong tool / won't stop) | Tight arg schemas; step/time budgets; start with 2 read-only tools; deterministic tools that *know* |
| Prompt-injection via tool output (e.g. a file says "run rm -rf") | Tool output is *data*, never elevated to instructions; MEDIUM+ still needs human approval regardless of what the model "decided" |
| Terminal blast radius | Security gate + project jail + human-in-the-loop; no unattended loop in Phase 1 (ADR-0005) |
| Loop latency (multi-step = multiple inferences, serialized on one GPU) | Keep single-flight; avoid the LLM when a deterministic tool answers; cap steps; stream progress so it *feels* alive |
| Windows ConPTY quirks | Wrap pywinpty; degrade to one-shot `subprocess` if a persistent PTY fails; `verify_terminal.py` covers it |
| Scope creep into Phase 2 | Design doc boundary is law; browser/workspace/planner are out |

## 9. Dependencies
- New Python deps (optional, lazy): `pywinpty` (terminal). Playwright etc. are
  Phase 2. Everything degrades gracefully if a dep is missing (existing pattern).
- Model must support tool-calling in Ollama (qwen3 does). If a chosen model
  doesn't, fall back to a structured-JSON tool protocol we parse ourselves.

## 10. Exit criteria (must all pass on the PC before Phase 2)
See ROADMAP "Phase 1 success criteria" — agent completes a real 3-step task, 100%
of MEDIUM+ actions gated (≥20 adversarial prompts, 0 escapes), terminal
round-trip works, metrics emitted, `verify_agent/security/terminal.py` green.
Additionally:
- **Capability Registry:** the model's tool list is generated from the registry
  (no hard-coded prompt list); a capability registered at runtime is callable
  without touching the loop; **every** dispatch passes through the gate + metrics
  (proven by a test that a capability cannot execute without authorization).
  `verify_capabilities.py` green.
- **Executive Memory:** after a multi-step task, the register holds the correct
  `project`/`branch` (observed, verified against `git`), and a fresh session reads
  `goal`/`task`/`next_action` from the register instead of reconstructing them.
  `verify_executive_memory.py` green.

## 11. Why this design (vs. alternatives)
- **In-process loop over an external agent framework** — debuggable, owned, fits
  the monolith (ADR-0003).
- **Security gate before tools, not after** — the only order that's safe
  (ADR-0005).
- **Deterministic tools first** — "don't reason when you can know" (Constitution)
  makes the common case instant and reduces the small model's chances to err.
