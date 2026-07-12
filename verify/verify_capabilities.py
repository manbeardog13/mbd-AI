#!/usr/bin/env python3
"""Self-test for the Capability Registry — the guarded dispatch seam (ADR-0007).

Fully offline. Proves: the model's tool list comes from the registry, a runtime
registration is callable with no loop change, every dispatch passes the gate (a
dangerous capability cannot execute without authorization), and failures are
contained as results rather than crashes. Exit 0 = pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capabilities import Context, Registry, Result  # noqa: E402
from app.capabilities.builtin import register_builtins  # noqa: E402
from app.security.gate import RiskClass  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


class SafeEcho:
    name = "verify.echo"
    description = "Echo."
    args_schema = {"type": "object", "properties": {}}
    risk = RiskClass.SAFE
    provider = "verify"

    def execute(self, args, ctx):
        return Result(True, f"echo:{args.get('msg', '')}")


class Dangerous:
    name = "verify.destroy"
    description = "Would delete everything."
    args_schema = {"type": "object", "properties": {}}
    risk = RiskClass.HIGH
    provider = "verify"
    ran = False

    def execute(self, args, ctx):
        Dangerous.ran = True
        return Result(True, "destroyed")


def main() -> int:
    reg = Registry()
    reg.register(SafeEcho())
    check("specs list comes from the registry",
          [s["name"] for s in reg.specs()] == ["verify.echo"])

    check("runtime-registered capability is callable",
          reg.dispatch("verify.echo", {"msg": "hi"}, Context(allowed_dirs=["."])).output
          == "echo:hi")

    check("unknown capability is a failed result, not a crash",
          not reg.dispatch("verify.nope", {}, Context(allowed_dirs=["."])).ok)

    reg.register(Dangerous())
    Dangerous.ran = False
    denied = reg.dispatch("verify.destroy", {}, Context(allowed_dirs=["."], confirm=None))
    check("HIGH capability cannot execute without authorization",
          (not denied.ok) and Dangerous.ran is False and denied.data.get("denied"))

    Dangerous.ran = False
    ok = reg.dispatch("verify.destroy", {}, Context(allowed_dirs=["."], confirm=lambda _p: True))
    check("HIGH capability runs once a human confirms", ok.ok and Dangerous.ran is True)

    builtins = Registry()
    register_builtins(builtins)
    check("built-in provider registers git.status", builtins.get("git.status") is not None)

    # git.status is deterministic — run it against this repo (SAFE, no confirm).
    result = builtins.dispatch("git.status", {},
                               Context(allowed_dirs=[str(Path(__file__).resolve().parent.parent)]))
    check("git.status returns real repo state", result.ok and "branch" in (result.data or {}))
    if result.ok:
        print(f"     -> {result.output.splitlines()[0]}")

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Capability Registry verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
