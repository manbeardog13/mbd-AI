"""The security gate — where every capability's risk is judged.

Nero can act (ADR-0003); the moment she can, she can also cause harm. So the gate
is a *dependency of the capability system*, built before the powerful tools, not
a feature bolted on after (ADR-0005). The rule is simple and absolute:

  * `SAFE` (read / list / status) runs freely.
  * `MEDIUM`+ (create, install, delete, push, config, …) waits for a human — no
    exceptions. Destructive actions are never performed silently.

Filesystem/terminal capabilities are also scoped to an allow-listed **project
jail**; a path that escapes the jail is itself escalated to a confirmable action.
This module is pure, synchronous, and has no dependency on the registry — it only
reads a capability's `name` and `risk`, so there's no import cycle.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol


class RiskClass(str, Enum):
    """How much blast radius an action has. Order matters — see `rank`."""

    SAFE = "safe"          # read / list / status — auto-approved
    MEDIUM = "medium"      # create files, install deps — needs confirmation
    HIGH = "high"          # delete, git push, change config — needs confirmation
    CRITICAL = "critical"  # mass delete, disk/registry, credentials — always confirmed, never remembered

    @property
    def rank(self) -> int:
        return _ORDER[self]


_ORDER = {
    RiskClass.SAFE: 0,
    RiskClass.MEDIUM: 1,
    RiskClass.HIGH: 2,
    RiskClass.CRITICAL: 3,
}

# Anything at or above MEDIUM needs a human. SAFE is the only frictionless class.
NEEDS_CONFIRM = {RiskClass.MEDIUM, RiskClass.HIGH, RiskClass.CRITICAL}
# Only MEDIUM approvals may be remembered within a session; HIGH/CRITICAL never.
REMEMBERABLE = {RiskClass.MEDIUM}
# Argument keys we treat as filesystem paths for jail checking.
_PATH_KEYS = ("path", "file", "filename", "dir", "directory", "cwd", "target", "dest")


class Classifiable(Protocol):
    """The only surface the gate needs from a capability (structural — no import)."""

    name: str
    risk: "RiskClass"


@dataclass
class Decision:
    """The gate's verdict on one attempted action."""

    allowed: bool
    risk: RiskClass
    needs_confirmation: bool
    reason: str = ""


def _higher(a: RiskClass, b: RiskClass) -> RiskClass:
    return a if a.rank >= b.rank else b


# --------------------------------------------------------------------------
# The project jail
# --------------------------------------------------------------------------

def _resolve(path: str, allowed_dirs: list[str]) -> Path | None:
    """Resolve `path` (absolute, or relative to the first allowed dir)."""
    try:
        p = Path(path)
        if not p.is_absolute():
            base = Path(allowed_dirs[0]) if allowed_dirs else Path.cwd()
            p = base / p
        return p.resolve()
    except Exception:  # noqa: BLE001 - a bad path is simply "not in the jail"
        return None


def within_jail(path: str, allowed_dirs: list[str]) -> bool:
    """True if `path` resolves inside one of the allow-listed directories.

    A `..` escape or a symlink out of the jail resolves to a real path outside
    the allowed set and is rejected — the check is on the *resolved* location,
    not the spelling.
    """
    resolved = _resolve(path, allowed_dirs)
    if resolved is None:
        return False
    for d in allowed_dirs or []:
        try:
            base = Path(d).resolve()
        except Exception:  # noqa: BLE001
            continue
        if resolved == base or base in resolved.parents:
            return True
    return False


def _jail_escapes(args: dict, allowed_dirs: list[str]) -> list[str]:
    """Return any path-like argument values that fall outside the jail."""
    escapes: list[str] = []
    for key in _PATH_KEYS:
        val = args.get(key)
        if isinstance(val, str) and val.strip() and not within_jail(val, allowed_dirs):
            escapes.append(val)
    return escapes


# --------------------------------------------------------------------------
# Classification + authorization
# --------------------------------------------------------------------------

def classify(cap: Classifiable, args: dict, allowed_dirs: list[str]) -> RiskClass:
    """The effective risk of running `cap` with `args`.

    Starts from the capability's declared risk and escalates: a path argument
    that escapes the project jail makes the action at least HIGH (a confirmable,
    scoped decision — ADR-0005), whatever the capability declared.
    """
    risk = cap.risk
    if _jail_escapes(args or {}, allowed_dirs):
        risk = _higher(risk, RiskClass.HIGH)
    return risk


def _preview(cap: Classifiable, args: dict, risk: RiskClass) -> str:
    detail = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
    return f"[{risk.value}] {cap.name}({detail})"


def authorize(
    cap: Classifiable,
    args: dict,
    *,
    allowed_dirs: list[str],
    confirm: Callable[[str], bool] | None = None,
    remembered: set[str] | None = None,
) -> Decision:
    """Decide whether `cap(args)` may run.

    `SAFE` auto-approves. `MEDIUM`+ needs a human via the `confirm(preview)`
    callback; with no callback available the action is *denied* (fail-closed —
    never run an unconfirmed dangerous action). A MEDIUM capability whose name is
    in `remembered` is approved without re-prompting (per-session convenience);
    HIGH and CRITICAL are never remembered.
    """
    risk = classify(cap, args or {}, allowed_dirs)

    if risk == RiskClass.SAFE:
        return Decision(True, risk, False, "safe — auto-approved")

    if risk in REMEMBERABLE and remembered and cap.name in remembered:
        return Decision(True, risk, True, "approved (remembered this session)")

    if confirm is None:
        # Fail closed: no way to ask a human means the answer is no.
        return Decision(False, risk, True, "requires confirmation; none available")

    approved = bool(confirm(_preview(cap, args or {}, risk)))
    if approved and risk in REMEMBERABLE and remembered is not None:
        remembered.add(cap.name)
    return Decision(
        approved, risk, True,
        "approved by human" if approved else "denied by human",
    )
