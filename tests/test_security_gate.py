"""Unit tests for the security gate — the safety floor of the whole agent.

The bar (ROADMAP Phase 1): every MEDIUM+ action is gated, 0 escapes, across a
battery of adversarial attempts. These tests are that battery.

Run directly:  python tests/test_security_gate.py
Or with pytest: pytest tests/
"""
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security import gate
from app.security.gate import RiskClass


@dataclass
class Cap:
    name: str
    risk: RiskClass


HERE = str(Path(__file__).resolve().parent)
JAIL = [HERE]


def test_safe_auto_approves_without_confirm():
    d = gate.authorize(Cap("git.status", RiskClass.SAFE), {}, allowed_dirs=JAIL)
    assert d.allowed and not d.needs_confirmation


def test_medium_denied_when_no_confirm_channel():
    # Fail-closed: no way to ask a human ⇒ the answer is no.
    d = gate.authorize(Cap("fs.write", RiskClass.MEDIUM), {}, allowed_dirs=JAIL)
    assert not d.allowed and d.needs_confirmation


def test_medium_denied_when_human_declines():
    d = gate.authorize(Cap("fs.write", RiskClass.MEDIUM), {},
                       allowed_dirs=JAIL, confirm=lambda _p: False)
    assert not d.allowed


def test_medium_approved_when_human_confirms_and_is_remembered():
    remembered: set[str] = set()
    d = gate.authorize(Cap("fs.write", RiskClass.MEDIUM), {},
                       allowed_dirs=JAIL, confirm=lambda _p: True, remembered=remembered)
    assert d.allowed and "fs.write" in remembered
    # Second time: approved from memory, no confirm callback needed.
    d2 = gate.authorize(Cap("fs.write", RiskClass.MEDIUM), {},
                        allowed_dirs=JAIL, confirm=None, remembered=remembered)
    assert d2.allowed


def test_high_is_never_remembered():
    remembered: set[str] = set()
    gate.authorize(Cap("git.push", RiskClass.HIGH), {},
                   allowed_dirs=JAIL, confirm=lambda _p: True, remembered=remembered)
    assert "git.push" not in remembered
    # So a later call with no confirm channel is denied again.
    d = gate.authorize(Cap("git.push", RiskClass.HIGH), {},
                       allowed_dirs=JAIL, confirm=None, remembered=remembered)
    assert not d.allowed


def test_critical_is_never_remembered_even_when_approved():
    remembered: set[str] = set()
    d = gate.authorize(Cap("disk.wipe", RiskClass.CRITICAL), {},
                       allowed_dirs=JAIL, confirm=lambda _p: True, remembered=remembered)
    assert d.allowed  # a human said yes this once
    assert "disk.wipe" not in remembered  # but it's never remembered


def test_within_jail_true_for_inside_paths():
    assert gate.within_jail(str(Path(HERE) / "sub" / "file.txt"), JAIL)
    assert gate.within_jail("relative_file.txt", JAIL)  # relative to jail[0]


def test_within_jail_false_for_escapes():
    assert not gate.within_jail("/etc/passwd", JAIL)
    assert not gate.within_jail(str(Path(HERE) / ".." / ".." / "escape"), JAIL)


def test_jail_escape_escalates_to_confirmable():
    # A read declared SAFE that reaches outside the jail is no longer auto-run.
    cap = Cap("fs.read", RiskClass.SAFE)
    risk = gate.classify(cap, {"path": "/etc/passwd"}, JAIL)
    assert risk == RiskClass.HIGH
    d = gate.authorize(cap, {"path": "/etc/passwd"}, allowed_dirs=JAIL, confirm=None)
    assert not d.allowed  # escalated + no confirm ⇒ denied


def test_adversarial_battery_zero_escapes():
    """≥20 attempts to run a dangerous action unconfirmed — none may succeed."""
    dangerous = [
        Cap("fs.write", RiskClass.MEDIUM), Cap("fs.delete", RiskClass.HIGH),
        Cap("git.push", RiskClass.HIGH), Cap("pip.install", RiskClass.MEDIUM),
        Cap("terminal.run", RiskClass.HIGH), Cap("registry.write", RiskClass.CRITICAL),
        Cap("disk.format", RiskClass.CRITICAL), Cap("env.write", RiskClass.HIGH),
        Cap("config.write", RiskClass.HIGH), Cap("creds.read", RiskClass.CRITICAL),
    ]
    escaping_args = [{}, {"path": "/etc/shadow"}, {"target": "/"}, {"cwd": "/root"}]
    attempts = 0
    for cap in dangerous:
        for args in escaping_args:
            attempts += 1
            # No confirm channel: every one of these MUST be denied.
            d = gate.authorize(cap, args, allowed_dirs=JAIL, confirm=None)
            assert not d.allowed, f"ESCAPE: {cap.name} ran unconfirmed with {args}"
    assert attempts >= 20


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} security-gate tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
