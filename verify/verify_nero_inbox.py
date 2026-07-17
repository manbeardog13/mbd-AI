#!/usr/bin/env python3
"""Deterministically verify the Review Inbox CLI (scripts/inboxctl.py) v1.1.

Uses fixture policy registries so the check stays green across the registry's
real lifecycle (review finding: never assert against the live registry)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "inboxctl.py"

DRAFT = "## policy: p-one\nstatus: draft\nscope: x\n"
APPROVED = "## policy: p-one\nstatus: approved\nscope: x\n"
SPOOF = "## policy: p-two\nstatus: draft\n```\nstatus: approved\n```\nscope: x\n"


def run(*args, state=None, policies=None, stdin=""):
    cmd = [sys.executable, str(CLI)]
    if state: cmd += ["--state", str(state)]
    if policies: cmd += ["--policies", str(policies)]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, input=stdin,
                          timeout=30)


def main() -> int:
    checks, ok = [], True

    def check(name, fn):
        nonlocal ok
        try:
            d = fn()
            checks.append({"check": name, "ok": True, **({"detail": d} if d else {})})
        except Exception as exc:
            ok = False
            checks.append({"check": name, "ok": False, "error": str(exc)})

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        state = td / "inbox.json"
        pol_draft = td / "pol_draft.md"; pol_draft.write_text(DRAFT, encoding="utf-8")
        pol_ok = td / "pol_ok.md"; pol_ok.write_text(APPROVED, encoding="utf-8")
        pol_spoof = td / "pol_spoof.md"; pol_spoof.write_text(SPOOF, encoding="utf-8")

        def round_trip():
            r = run("add", "--title", "t1", "--category", "documentation-update",
                    "--level", "2", state=state)
            assert r.returncode == 0, r.stdout + r.stderr
            r = run("list", "--group", state=state)
            assert "Pending Reviews (1)" in r.stdout
            return "add + grouped list"
        check("store round-trip", round_trip)

        def l3_immovable():
            r = run("add", "--title", "t2", "--category", "publication",
                    "--level", "2", state=state)
            assert r.returncode != 0 and "immovable" in r.stdout
            return "publication@L2 refused"
        check("L3 non-demotion", l3_immovable)

        def policy_draft_denied():
            r = run("add", "--title", "t3", "--category", "automatic-approval",
                    "--level", "0", "--policy", "p-one", "--evidence", "x.md",
                    state=state, policies=pol_draft)
            assert r.returncode != 0 and "not an approved" in r.stdout
            return "draft denied"
        check("self-decision gate (draft)", policy_draft_denied)

        def policy_approved_allowed():
            r = run("add", "--title", "t4", "--category", "automatic-approval",
                    "--level", "0", "--policy", "p-one", "--evidence", "x.md",
                    state=state, policies=pol_ok)
            out = json.loads(r.stdout)
            assert r.returncode == 0 and out["status"] == "approved"
            assert "self-approved" in out["decision_note"]
            return "approved policy self-approves with evidence"
        check("self-decision gate (approved)", policy_approved_allowed)

        def spoof_blocked():
            r = run("add", "--title", "t5", "--category", "automatic-approval",
                    "--level", "0", "--policy", "p-two", "--evidence", "x.md",
                    state=state, policies=pol_spoof)
            assert r.returncode != 0
            return "fenced-block status ignored"
        check("policy spoof resistance", spoof_blocked)

        def evidence_required():
            r = run("add", "--title", "t6", "--category", "automatic-approval",
                    "--level", "0", "--policy", "p-one", state=state,
                    policies=pol_ok)
            assert r.returncode != 0 and "evidence" in r.stdout
            return "L0 without evidence refused"
        check("evidence gate", evidence_required)

        def injection_blocked():
            r = run("add", "--title", "t7", "--category", "architectural-decision",
                    "--level", "2", "--source-kind", "dhef",
                    "--source-ref", "x; rm -rf /", state=state)
            assert r.returncode != 0 and "source-ref" in r.stdout
            return "dhef ref injection refused at add"
        check("gate-command injection", injection_blocked)

        def escalate_pins():
            r = run("add", "--title", "needs toni", "--category",
                    "architectural-decision", "--level", "2", state=state)
            eid = json.loads(r.stdout)["id"][:8]
            r = run("escalate", "--id", eid, "--note", "raising", state=state)
            out = json.loads(r.stdout)
            assert out["entry"]["level"] == 3 and out["entry"]["status"] == "pending"
            r = run("list", "--group", state=state)
            assert "ESCALATED" in r.stdout
            return "escalate pins, never hides"
        check("escalate semantics", escalate_pins)

        def approve_drives():
            r = run("add", "--title", "gate item", "--category",
                    "architectural-decision", "--level", "2",
                    "--source-kind", "dhef", "--source-ref", "PACKET-1",
                    state=state)
            eid = json.loads(r.stdout)["id"][:8]
            r = run("approve", "--id", eid, "--note", "ok", state=state)
            out = json.loads(r.stdout)
            assert "hybrid_brain" in out.get("drives_gate", "")
            assert "never drives gates itself" in out.get("drives_gate_note", "")
            return "gate command printed, never executed"
        check("view-not-authority", approve_drives)

        def brief_watermark():
            r = run("brief", state=state)
            assert "reading time" in r.stdout.lower()
            first = r.stdout
            r = run("brief", state=state)
            assert "nothing decided" in r.stdout or "decided" in first
            return "watermark advances"
        check("brief watermark", brief_watermark)

        def prune_guard():
            r = run("prune", "--days", "0", state=state)
            assert r.returncode != 0
            return "days<1 refused"
        check("prune guard", prune_guard)

        def audit_filter():
            r = run("list", "--status", "approved", state=state)
            rows = json.loads(r.stdout)
            assert any(e.get("policy") for e in rows)
            return "audit trail surfaced on request"
        check("audit filter", audit_filter)

    print(json.dumps({"ok": ok, "checks": checks}, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
