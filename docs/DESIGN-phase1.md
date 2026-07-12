# Technical Design — Phase 1: The Hands

*Design-before-code for the foundational phase. Scope: agent/tool loop, tool
registry, security gate, observability, human-in-the-loop terminal. Later phases
are designed just-in-time (Constitution: no half-finished experiments carried
forward). Governed by ADR-0001/0003/0005.*

## 1. Goal & non-goals
**Goal:** give Nero the ability to *take one verified action* and build on the
result — the single primitive every "hands" capability depends on — with a
security gate that makes it safe from the first tool.

**Non-goals (Phase 1):** browser, workspace, planner, skills, voice, vision, MCP,
autonomous/unconfirmed execution. No event bus, no new process.

## 2. Module layout (in the existing monolith)
New packages under `app/`, each behind a typed interface (ADR-0001):

```
app/agent/      loop.py        # the reason→tool→observe cycle
app/tools/      registry.py    # Tool interface + registration + dispatch
                builtin/       # fs_read.py, git_status.py, terminal.py, …
app/security/   gate.py        # risk classification + confirmation + jail
app/obs/        metrics.py     # timing/counters (extends today's METRICS dict)
```
`app/main.py` gains an agent-mode chat path; nothing existing is deleted until the
new path is verified (strangler-fig).

## 3. Interfaces (the contracts modules depend on — not implementations)

```python
# app/tools/registry.py
class Tool(Protocol):
    name: str                       # "fs.read", "git.status", "terminal.run"
    description: str                # shown to the model
    args_schema: dict               # JSON Schema for arguments
    risk: RiskClass                 # SAFE | MEDIUM | HIGH | CRITICAL
    def execute(self, args: dict, ctx: ToolContext) -> ToolResult: ...

@dataclass
class ToolResult:
    ok: bool
    output: str                     # fed back to the model (bounded/truncated)
    data: dict | None = None        # structured extras (exit code, paths, …)

# app/security/gate.py
class SecurityGate(Protocol):
    def classify(self, tool: Tool, args: dict) -> RiskClass: ...
    # returns an approval decision; SAFE auto-approves, MEDIUM+ awaits the human
    def authorize(self, tool: Tool, args: dict, ctx) -> Decision: ...
```

`ToolContext` carries the project-directory jail, the conversation id, a metrics
handle, and a `confirm(prompt) -> bool` callback wired to the UI.

## 4. The agent loop (data flow)

```
user turn ─▶ retrieve memory + world (existing) ─▶ build prompt WITH tool specs
        ┌───────────────────────────────────────────────┐
        ▼                                                │ observation
   model call (resident generalist) ──▶ tool call? ──yes─┤ fed back
        │ no                                             │
        ▼                                    ┌───────────┴───────────┐
   stream final answer                       │ security.authorize()  │
        │                                    │  SAFE → run            │
        ▼                                    │  MEDIUM+ → confirm(UI) │
   persist + reflect + world update          │   approved → run      │
   (existing background tasks)               │   denied → tell model │
                                             └───────────────────────┘
```
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

## 6. Phase-1 tools (ship in this order, one PR each)
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

## 11. Why this design (vs. alternatives)
- **In-process loop over an external agent framework** — debuggable, owned, fits
  the monolith (ADR-0003).
- **Security gate before tools, not after** — the only order that's safe
  (ADR-0005).
- **Deterministic tools first** — "don't reason when you can know" (Constitution)
  makes the common case instant and reduces the small model's chances to err.
