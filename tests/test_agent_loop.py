"""Unit tests for the agent loop — reason → tool → observe → repeat (ADR-0003).

The model call is injected, so the whole loop is exercised offline with a
scripted model — no Ollama. Covers the happy path, bounds (max_steps / timeout),
the denied-tool path, and defensive parsing.

Run directly:  python tests/test_agent_loop.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import loop
from app.capabilities import Context, Registry, Result
from app.security.gate import RiskClass


class Echo:
    name = "echo"
    description = "Echo."
    args_schema = {"type": "object", "properties": {}}
    risk = RiskClass.SAFE
    provider = "test"

    def execute(self, args, ctx):
        return Result(True, f"echoed {args.get('msg', '')}")


class Danger:
    name = "danger"
    description = "Dangerous."
    args_schema = {"type": "object", "properties": {}}
    risk = RiskClass.HIGH
    provider = "test"
    ran = False

    def execute(self, args, ctx):
        Danger.ran = True
        return Result(True, "ran")


def _reg(*caps):
    reg = Registry()
    for c in caps:
        reg.register(c)
    return reg


def _scripted(*replies):
    it = iter(replies)
    return lambda messages: next(it)


CTX = Context(allowed_dirs=["."])


def test_tool_then_final():
    reg = _reg(Echo())
    model = _scripted('{"tool":"echo","args":{"msg":"hi"}}', '{"final":"all done"}')
    run = loop.run(None, reg, CTX, "task", model_call=model, max_steps=5)
    assert run.stopped_reason == "final" and run.answer == "all done"
    assert len(run.steps) == 1 and run.steps[0]["observation"] == "echoed hi"


def test_immediate_final_no_tool():
    run = loop.run(None, _reg(Echo()), CTX, "hi",
                   model_call=_scripted('{"final":"hello"}'), max_steps=3)
    assert run.answer == "hello" and run.steps == []


def test_max_steps_bound_returns_partial():
    # A model that never finalizes must still terminate gracefully.
    reg = _reg(Echo())
    model = lambda messages: '{"tool":"echo","args":{"msg":"loop"}}'
    run = loop.run(None, reg, CTX, "task", model_call=model, max_steps=3)
    assert run.stopped_reason == "max_steps" and len(run.steps) == 3
    assert run.answer  # non-empty graceful partial


def test_timeout_bound():
    reg = _reg(Echo())
    run = loop.run(None, reg, CTX, "task",
                   model_call=_scripted('{"final":"x"}'),
                   max_steps=5, max_seconds=-1.0)  # already "over time"
    assert run.stopped_reason == "timeout"


def test_denied_tool_is_observed_not_executed():
    Danger.ran = False
    reg = _reg(Danger())
    # First the model tries the dangerous tool (no confirm ⇒ denied), then answers.
    model = _scripted('{"tool":"danger","args":{}}', '{"final":"gave up on that"}')
    run = loop.run(None, reg, Context(allowed_dirs=["."], confirm=None),
                   "do danger", model_call=model, max_steps=5)
    assert Danger.ran is False
    assert "Denied" in run.steps[0]["observation"]
    assert run.answer == "gave up on that"


def test_parse_step_tool():
    s = loop.parse_step('{"tool":"git.status","args":{"a":1}}')
    assert s.tool == "git.status" and s.args == {"a": 1} and not s.is_final()


def test_parse_step_final_and_think_and_fences():
    assert loop.parse_step('{"final":"done"}').final == "done"
    assert loop.parse_step('<think>hmm {x}</think>{"final":"ok"}').final == "ok"
    assert loop.parse_step('```json\n{"tool":"git.status"}\n```').tool == "git.status"


def test_parse_step_prose_becomes_final():
    s = loop.parse_step("I think the answer is 42.")
    assert s.is_final() and "42" in s.final


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} agent-loop tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
