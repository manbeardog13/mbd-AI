"""The agent loop — reason → choose capability → execute → observe → repeat.

This is the core execution primitive (ADR-0003): every "hands" capability is a
tool behind this one cycle, not a new service. The loop is deliberately small and
owned:

  * **Protocol.** Each step the model emits one JSON object — a tool call
    ``{"tool": name, "args": {...}}`` or a final answer ``{"final": text}``.
    We grammar-force that shape with Ollama's structured output (the same
    mechanism that made reflection/world-model reliable), rather than depend on
    native tool-calling we can't verify on every model. Parsing is defensive
    (tolerates prose / ``<think>`` / fences), reusing the hardened extractors.
  * **Safety.** Tool calls go through ``Registry.dispatch``, so the security gate
    sees every one — the loop cannot route around it (ADR-0005/0007).
  * **Bounds.** ``max_steps`` and ``max_seconds`` cap the loop; hitting either
    returns a graceful partial answer, never a hang.

The model call is injected (``model_call``) so the whole loop is testable offline
with a scripted model — no Ollama required.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field

from ..capabilities.registry import Context, Registry
from ..llm import complete_chat
from ..memory import _first_balanced_json, strip_think

log = logging.getLogger("nero.agent")

METRICS: dict[str, float] = {
    "runs": 0, "steps": 0, "tool_calls": 0, "timeouts": 0, "max_steps_hit": 0,
}
_lock = threading.RLock()


def _bump(key: str, n: float = 1) -> None:
    with _lock:
        METRICS[key] = METRICS.get(key, 0) + n


DEFAULT_MAX_STEPS = 8
DEFAULT_MAX_SECONDS = 60.0
_OBS_LIMIT = 4000  # bound the observation text fed back to the model

# Structured-output grammar (Ollama `format`): one step is exactly a tool call
# or a final answer. `thought` is optional room to reason briefly.
AGENT_FORMAT = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "tool": {"type": "string"},
        "args": {"type": "object"},
        "final": {"type": "string"},
    },
    "additionalProperties": False,
}


@dataclass
class Step:
    thought: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    observation: str = ""
    ok: bool = True
    risk: str = ""
    final: str = ""  # set when the model answered instead of calling a tool

    def is_final(self) -> bool:
        return not self.tool

    def as_dict(self) -> dict:
        return {
            "thought": self.thought, "tool": self.tool, "args": self.args,
            "observation": self.observation, "ok": self.ok, "risk": self.risk,
        }


@dataclass
class AgentRun:
    answer: str
    steps: list[dict] = field(default_factory=list)
    stopped_reason: str = "final"  # final | max_steps | timeout | error


def _system_prompt(specs: list[dict], extra: str) -> str:
    tools = json.dumps(specs, ensure_ascii=False, indent=2)
    base = (
        "You are Nero, working through a task by using tools. On EACH turn, reply "
        "with a SINGLE JSON object and nothing else.\n"
        "- To use a tool: {\"tool\": \"<name>\", \"args\": { ... }}\n"
        "- When you can answer, or no tool is needed: {\"final\": \"<your answer>\"}\n"
        "Use a tool only when it genuinely helps; prefer knowing over guessing. "
        "After each tool you'll receive its result as an observation; use it.\n\n"
        f"Available tools (JSON):\n{tools}"
    )
    return f"{base}\n\n{extra}".strip() if extra else base


def parse_step(raw: str) -> Step:
    """Parse one model turn into a Step (tool call or final). Tolerant of prose."""
    text = strip_think(raw or "")
    data = _first_balanced_json(text, "{", "}")
    if not isinstance(data, dict):
        # No JSON object at all — treat whatever the model said as the answer.
        return Step(final=text.strip())

    thought = str(data.get("thought") or "").strip()
    tool = str(data.get("tool") or "").strip()
    args = data.get("args") if isinstance(data.get("args"), dict) else {}
    step = Step(thought=thought, tool=tool, args=args)
    if not tool:
        final = data.get("final")
        step.final = (final if isinstance(final, str) else
                      "" if final is None else str(final)).strip()
    return step


def _default_model_call(cfg, messages: list[dict]) -> str:
    return complete_chat(
        cfg, messages, temperature=0.0, think=False,
        num_predict=512, response_format=AGENT_FORMAT,
    )


def run(
    cfg,
    registry: Registry,
    ctx: Context,
    user_text: str,
    *,
    system_extra: str = "",
    model_call=None,
    max_steps: int | None = None,
    max_seconds: float | None = None,
) -> AgentRun:
    """Run the loop until a final answer, or a bound is hit. Never raises."""
    max_steps = max_steps or getattr(cfg, "agent_max_steps", DEFAULT_MAX_STEPS)
    max_seconds = max_seconds or getattr(cfg, "agent_max_seconds", DEFAULT_MAX_SECONDS)
    call = model_call or (lambda msgs: _default_model_call(cfg, msgs))

    messages = [
        {"role": "system", "content": _system_prompt(registry.specs(), system_extra)},
        {"role": "user", "content": user_text},
    ]
    steps: list[dict] = []
    _bump("runs")
    started = time.monotonic()

    for _ in range(max_steps):
        if time.monotonic() - started > max_seconds:
            _bump("timeouts")
            return AgentRun(_partial(steps, "I ran out of time on that one."),
                            steps, "timeout")
        try:
            raw = call(messages)
        except Exception as exc:  # noqa: BLE001 - a model hiccup ends gracefully
            log.warning("agent model call failed: %s", exc)
            return AgentRun(_partial(steps, f"My brain hiccuped: {exc}"), steps, "error")

        _bump("steps")
        step = parse_step(raw)

        # A final answer ends the loop.
        if step.is_final():
            return AgentRun(step.final or _partial(steps, ""), steps, "final")

        # Otherwise it's a tool call — dispatch through the guarded registry.
        result = registry.dispatch(step.tool, step.args, ctx)
        _bump("tool_calls")
        obs = (result.output or "")[:_OBS_LIMIT]
        step.observation = obs
        step.ok = result.ok
        step.risk = (result.data or {}).get("risk", "") if result.data else ""
        steps.append(step.as_dict())

        # Feed the model its own action and the observation, then loop.
        messages.append({"role": "assistant", "content": raw})
        messages.append({
            "role": "user",
            "content": f"Observation from {step.tool}: {obs}",
        })

    _bump("max_steps_hit")
    return AgentRun(_partial(steps, "I've taken as many steps as I can on this."),
                    steps, "max_steps")


def _partial(steps: list[dict], fallback: str) -> str:
    """A graceful answer when the loop stops without the model saying `final`."""
    if steps and steps[-1].get("observation"):
        tail = steps[-1]["observation"]
        return (f"{fallback} Here's what I found so far:\n{tail}").strip()
    return fallback or "I couldn't complete that."
