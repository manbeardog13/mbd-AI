"""Unit tests for the Capability Registry — the single guarded dispatch seam.

The bar (ROADMAP Phase 1): the model's tool list comes from the registry, a
capability registered at runtime is callable with no loop change, and **every**
dispatch passes the gate — a dangerous capability cannot execute without
authorization.

Run directly:  python tests/test_capabilities.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capabilities import Context, Registry, Result
from app.security.gate import RiskClass


class Echo:
    name = "test.echo"
    description = "Echo the message back."
    args_schema = {"type": "object", "properties": {"msg": {"type": "string"}}}
    risk = RiskClass.SAFE
    provider = "test"

    def execute(self, args, ctx):
        return Result(True, f"echo: {args.get('msg', '')}")


class Destroyer:
    """A HIGH-risk capability that MUST NOT run without confirmation."""
    name = "test.destroy"
    description = "Pretend to delete everything."
    args_schema = {"type": "object", "properties": {}}
    risk = RiskClass.HIGH
    provider = "test"
    ran = False

    def execute(self, args, ctx):
        Destroyer.ran = True
        return Result(True, "destroyed")


class Boom:
    name = "test.boom"
    description = "Raises."
    args_schema = {"type": "object", "properties": {}}
    risk = RiskClass.SAFE
    provider = "test"

    def execute(self, args, ctx):
        raise RuntimeError("kaboom")


CTX = Context(allowed_dirs=["."])


def test_specs_come_from_registry():
    reg = Registry()
    reg.register(Echo())
    specs = reg.specs()
    assert [s["name"] for s in specs] == ["test.echo"]
    assert specs[0]["risk"] == "safe" and specs[0]["provider"] == "test"


def test_runtime_registration_is_callable():
    reg = Registry()
    reg.register(Echo())  # registered at runtime, not hard-coded
    result = reg.dispatch("test.echo", {"msg": "hi"}, CTX)
    assert result.ok and result.output == "echo: hi"


def test_unknown_capability_is_a_failed_result_not_a_crash():
    reg = Registry()
    result = reg.dispatch("nope.missing", {}, CTX)
    assert not result.ok and result.data.get("unknown")


def test_dangerous_capability_cannot_execute_without_authorization():
    reg = Registry()
    reg.register(Destroyer())
    Destroyer.ran = False
    # No confirm channel on the context ⇒ the gate denies it ⇒ execute never runs.
    result = reg.dispatch("test.destroy", {}, Context(allowed_dirs=["."], confirm=None))
    assert not result.ok
    assert result.data.get("denied") and result.data.get("risk") == "high"
    assert Destroyer.ran is False, "HIGH capability executed without authorization!"


def test_confirmed_dangerous_capability_runs():
    reg = Registry()
    reg.register(Destroyer())
    Destroyer.ran = False
    ctx = Context(allowed_dirs=["."], confirm=lambda _p: True)
    result = reg.dispatch("test.destroy", {}, ctx)
    assert result.ok and Destroyer.ran is True


def test_execute_exception_is_contained():
    reg = Registry()
    reg.register(Boom())
    result = reg.dispatch("test.boom", {}, CTX)
    assert not result.ok and "kaboom" in result.output


def test_builtins_register_git_status():
    from app.capabilities.builtin import register_builtins
    reg = Registry()
    register_builtins(reg)
    assert reg.get("git.status") is not None


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} capability-registry tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
