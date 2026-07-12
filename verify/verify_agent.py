#!/usr/bin/env python3
"""Self-test for the agent loop — reason → tool → observe → repeat (ADR-0003).

The offline checks (scripted model, no Ollama) run on any machine: the happy
path, the max-steps bound, and the denied-tool path. If Ollama is reachable, a
final **live** check runs a real 3-part task end-to-end — the model is asked
about the repo, must call git.status, and answer from the observation. That live
path is what proves the primitive on the real PC. Exit 0 = pass.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import loop  # noqa: E402
from app.capabilities import Context, Registry, Result  # noqa: E402
from app.capabilities.builtin import register_builtins  # noqa: E402
from app.config import load_config  # noqa: E402
from app.security.gate import RiskClass  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


def server_up(host: str) -> bool:
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


class Echo:
    name = "echo"
    description = "Echo."
    args_schema = {"type": "object", "properties": {}}
    risk = RiskClass.SAFE
    provider = "verify"

    def execute(self, args, ctx):
        return Result(True, f"echoed {args.get('msg', '')}")


def _scripted(*replies):
    it = iter(replies)
    return lambda messages: next(it)


def live_check() -> None:
    """End-to-end with the real model: ask about the repo → git.status → answer."""
    cfg = load_config()
    if not getattr(cfg, "agent_enabled", True):
        print("  . live run skipped — agent_enabled is false.")
        return
    if not server_up(cfg.ollama_host):
        print("  . live run skipped — Ollama not reachable (see verify_ollama).")
        return
    reg = Registry()
    register_builtins(reg)
    repo = str(Path(__file__).resolve().parent.parent)
    ctx = Context(allowed_dirs=[repo])
    run = loop.run(
        cfg, reg, ctx,
        "What git branch is this project on, and is the working tree clean? "
        "Use a tool to check, then tell me.",
    )
    used_git = any(s["tool"] == "git.status" for s in run.steps)
    check(f"live run produced an answer (stopped={run.stopped_reason})", bool(run.answer))
    check("live run used the git.status capability", used_git)
    print(f"     -> {run.answer[:160]}")
    if not used_git:
        model = cfg.model
        print(f"     HINT: {model} answered without calling the tool. If it never emits")
        print("     the JSON tool object, update Ollama so structured-output `format` is honored.")


def main() -> int:
    reg = Registry()
    reg.register(Echo())

    run = loop.run(None, reg, Context(allowed_dirs=["."]), "task",
                   model_call=_scripted('{"tool":"echo","args":{"msg":"hi"}}',
                                        '{"final":"done"}'), max_steps=5)
    check("happy path: tool then final",
          run.stopped_reason == "final" and run.answer == "done"
          and run.steps[0]["observation"] == "echoed hi")

    never = loop.run(None, reg, Context(allowed_dirs=["."]), "task",
                     model_call=lambda m: '{"tool":"echo","args":{}}', max_steps=3)
    check("max-steps bound terminates gracefully",
          never.stopped_reason == "max_steps" and bool(never.answer))

    class Danger:
        name = "danger"; description = "d"; args_schema = {"type": "object"}
        risk = RiskClass.HIGH; provider = "verify"; ran = False
        def execute(self, args, ctx):  # noqa: E301
            Danger.ran = True
            return Result(True, "ran")

    reg2 = Registry()
    reg2.register(Danger())
    denied = loop.run(None, reg2, Context(allowed_dirs=["."], confirm=None), "do danger",
                      model_call=_scripted('{"tool":"danger","args":{}}',
                                           '{"final":"could not"}'), max_steps=4)
    check("denied tool is observed, never executed",
          Danger.ran is False and "Denied" in denied.steps[0]["observation"])

    live_check()

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Agent loop verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
