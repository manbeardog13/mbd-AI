"""The Capability Registry — the seam between reasoning and implementation.

A **Capability** is a declared ability (name, description the model reads, an
args schema, a risk class, and the provider that runs it) — not a bare function
reference. The agent asks for a capability by name; `Registry.dispatch` is the
one path from intent to execution, and it:

  1. routes the call through the **security gate** (`authorize`), and
  2. records **metrics** (counts + timing),

for *every* provider. New providers (MCP, Skills) register through the same
interface and inherit both, unbypassably (ADR-0007). Pure and synchronous; the
web layer calls it from a worker thread.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from ..security import gate as security
from ..security.gate import RiskClass

METRICS: dict[str, float] = {
    "registered": 0,   # capabilities registered
    "dispatches": 0,   # capabilities actually executed
    "denied": 0,       # blocked by the security gate
    "errors": 0,       # unknown capability or execute() raised
    "seconds": 0.0,    # cumulative execute() wall-clock
}
_lock = threading.RLock()


def _bump(key: str, n: float = 1) -> None:
    with _lock:
        METRICS[key] = METRICS.get(key, 0) + n


@dataclass
class Result:
    """What a capability returns. `output` is fed back to the model (bounded)."""

    ok: bool
    output: str = ""
    data: dict | None = None


@dataclass
class Context:
    """Everything a capability needs from its surroundings, carried per-run.

    `allowed_dirs` is the project jail; `confirm` is the human-in-the-loop
    callback the gate uses for MEDIUM+ actions (None ⇒ those are denied);
    `remembered` holds per-session MEDIUM approvals.
    """

    allowed_dirs: list[str]
    conversation_id: int | None = None
    confirm: Callable[[str], bool] | None = None
    remembered: set[str] = field(default_factory=set)


@runtime_checkable
class Capability(Protocol):
    """The contract every capability satisfies, whatever its provider."""

    name: str
    description: str
    args_schema: dict
    risk: RiskClass
    provider: str

    def execute(self, args: dict, ctx: Context) -> Result: ...


class Registry:
    """Holds the known capabilities and dispatches calls through the gate."""

    def __init__(self) -> None:
        self._caps: dict[str, Capability] = {}

    def register(self, cap: Capability) -> None:
        """Add (or replace) a capability by name."""
        if not getattr(cap, "name", ""):
            raise ValueError("capability has no name")
        self._caps[cap.name] = cap
        _bump("registered")

    def get(self, name: str) -> Capability | None:
        return self._caps.get(name)

    def all(self) -> list[Capability]:
        return list(self._caps.values())

    def specs(self) -> list[dict]:
        """The capability list the model reasons over — built fresh each turn.

        This is the *only* description of tools the prompt ever sees: it comes
        from the live registry, never a hard-coded list (ADR-0007).
        """
        return [
            {
                "name": c.name,
                "description": c.description,
                "args_schema": c.args_schema,
                "risk": c.risk.value,
                "provider": c.provider,
            }
            for c in self._caps.values()
        ]

    def dispatch(self, name: str, args: dict | None, ctx: Context) -> Result:
        """Run a capability by name — the single guarded choke point.

        Order is deliberate: resolve → **authorize (gate)** → execute → measure.
        A denied or unknown call never reaches `execute`, and any exception is
        contained as a failed Result so the agent loop observes it instead of
        crashing.
        """
        cap = self._caps.get(name)
        if cap is None:
            _bump("errors")
            return Result(False, f"No such capability: {name!r}.", {"unknown": True})

        decision = security.authorize(
            cap, args or {},
            allowed_dirs=ctx.allowed_dirs,
            confirm=ctx.confirm,
            remembered=ctx.remembered,
        )
        if not decision.allowed:
            _bump("denied")
            return Result(
                False,
                f"Denied — {cap.name} is {decision.risk.value} and {decision.reason}.",
                {"denied": True, "risk": decision.risk.value},
            )

        t0 = time.perf_counter()
        try:
            result = cap.execute(args or {}, ctx)
        except Exception as exc:  # noqa: BLE001 - contained: the loop observes failures
            _bump("errors")
            return Result(False, f"{cap.name} failed: {exc}")
        finally:
            _bump("dispatches")
            _bump("seconds", time.perf_counter() - t0)
        return result if isinstance(result, Result) else Result(True, str(result))
