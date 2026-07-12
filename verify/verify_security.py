#!/usr/bin/env python3
"""Self-test for the security gate — the safety floor of the agent (ADR-0005).

Fully offline on any machine. Proves the core promise: SAFE runs free, every
MEDIUM+ action is gated, the project jail can't be escaped, and an adversarial
battery of unconfirmed dangerous actions has **0 escapes**. Exit 0 = pass.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security import gate  # noqa: E402
from app.security.gate import RiskClass  # noqa: E402

FAILS: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"  {'OK' if ok else 'XX'} {name}")
    if not ok:
        FAILS.append(name)


@dataclass
class Cap:
    name: str
    risk: RiskClass


def main() -> int:
    here = str(Path(__file__).resolve().parent)
    jail = [here]

    check("SAFE auto-approves without a human",
          gate.authorize(Cap("git.status", RiskClass.SAFE), {}, allowed_dirs=jail).allowed)

    check("MEDIUM with no confirm channel is denied (fail-closed)",
          not gate.authorize(Cap("fs.write", RiskClass.MEDIUM), {}, allowed_dirs=jail).allowed)

    check("MEDIUM approved when a human confirms",
          gate.authorize(Cap("fs.write", RiskClass.MEDIUM), {},
                         allowed_dirs=jail, confirm=lambda _p: True).allowed)

    remembered: set[str] = set()
    gate.authorize(Cap("git.push", RiskClass.HIGH), {},
                   allowed_dirs=jail, confirm=lambda _p: True, remembered=remembered)
    check("HIGH is never remembered", "git.push" not in remembered)

    crit_remembered: set[str] = set()
    approved = gate.authorize(Cap("disk.wipe", RiskClass.CRITICAL), {},
                              allowed_dirs=jail, confirm=lambda _p: True,
                              remembered=crit_remembered)
    check("CRITICAL runs once approved but is never remembered",
          approved.allowed and "disk.wipe" not in crit_remembered)

    check("path inside the jail is allowed",
          gate.within_jail(str(Path(here) / "x.txt"), jail))
    check("absolute path outside the jail is rejected",
          not gate.within_jail("/etc/passwd", jail))
    check("`..` escape is rejected",
          not gate.within_jail(str(Path(here) / ".." / ".." / "esc"), jail))
    check("SAFE read escaping the jail escalates to HIGH",
          gate.classify(Cap("fs.read", RiskClass.SAFE), {"path": "/etc/passwd"}, jail)
          == RiskClass.HIGH)

    # The adversarial battery: many attempts to run something dangerous with no
    # confirm channel. Not one may be allowed.
    dangerous = [
        Cap("fs.write", RiskClass.MEDIUM), Cap("fs.delete", RiskClass.HIGH),
        Cap("git.push", RiskClass.HIGH), Cap("pip.install", RiskClass.MEDIUM),
        Cap("terminal.run", RiskClass.HIGH), Cap("registry.write", RiskClass.CRITICAL),
        Cap("disk.format", RiskClass.CRITICAL), Cap("creds.read", RiskClass.CRITICAL),
    ]
    arg_variants = [{}, {"path": "/etc/shadow"}, {"target": "/"}, {"cwd": "/root"}]
    escapes = 0
    attempts = 0
    for cap in dangerous:
        for args in arg_variants:
            attempts += 1
            if gate.authorize(cap, args, allowed_dirs=jail, confirm=None).allowed:
                escapes += 1
    check(f"adversarial battery: {attempts} unconfirmed attempts, {escapes} escapes",
          escapes == 0 and attempts >= 20)

    print()
    if FAILS:
        print(f"  {len(FAILS)} check(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("  Security gate verified — 0 escapes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
