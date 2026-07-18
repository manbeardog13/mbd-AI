#!/usr/bin/env python3
"""Deterministically verify the Review Inbox CLI (scripts/inboxctl.py) v1.4.

Uses fixture policy registries so the check stays green across the registry's
real lifecycle (review finding: never assert against the live registry)."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "inboxctl.py"
SPEC = importlib.util.spec_from_file_location("nero_inbox_verify", CLI)
assert SPEC and SPEC.loader
INBOX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INBOX)

REGISTRY_HEAD = "---\nversion: 9.9.9\n---\n"
POLICY_FIELDS = (
    "level: 0\nevent_class: automatic-approval\n"
    "categories: automatic-approval\nsource_kinds: policy\nrisks: low\n"
    "evidence_required: true\nscope: exact fixture act\n"
    "evidence: verifier path\nrollback: remove the fixture record\n"
    "approved_by: toni\napproved_at: 2026-07-17\n"
)
DRAFT = REGISTRY_HEAD + "## policy: p-one\nstatus: draft\n" + POLICY_FIELDS
APPROVED = REGISTRY_HEAD + "## policy: p-one\nstatus: approved\n" + POLICY_FIELDS
SPOOF = (REGISTRY_HEAD + "## policy: p-two\nstatus: draft\n```\n"
         "status: approved\n```\n" + POLICY_FIELDS)


def run(*args, state=None, policies=None, stdin=""):
    cmd = [sys.executable, str(CLI)]
    if state:
        state = Path(state)
        if policies is None:
            policies = state.parent / "default-policies.md"
            if not policies.exists():
                policies.write_text(REGISTRY_HEAD, encoding="utf-8")
        cmd += ["--state", str(state)]
    if policies: cmd += ["--policies", str(policies)]
    cmd += list(args)
    env = os.environ.copy()
    if state:
        env["NERO_INBOX_TEST_ROOT"] = str(state.parent)
    return subprocess.run(cmd, capture_output=True, text=True, input=stdin,
                          timeout=30, env=env)


def output(result):
    return result.stdout + result.stderr


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
                    "--source-kind", "adr", "--source-ref", "docs/t1.md",
                    state=state)
            assert r.returncode == 0, r.stdout + r.stderr
            r = run("list", "--group", state=state)
            assert "Pending Reviews (1)" in r.stdout
            return "add + grouped list"
        check("store round-trip", round_trip)

        def l3_immovable():
            r = run("add", "--title", "t2", "--category", "publication",
                    "--level", "2", "--source-kind", "git", "--source-ref",
                    "feature/t2", state=state)
            assert r.returncode != 0 and "cannot be demoted" in output(r)
            return "publication@L2 refused"
        check("L3 non-demotion", l3_immovable)

        def canonical_event_routing():
            r = run("status", state=state)
            status = json.loads(r.stdout)
            assert status["catalog_version"] == 1
            expected = {
                "routine-read": 0, "green-verifier": 0,
                "automatic-approval": 0, "index-regeneration": 0,
                "completed-task": 1, "preapproved-promotion": 1,
                "archived-item": 1, "lexicon-observation": 1,
                "documentation-update": 2, "completed-skill": 2,
                "dhef-gate-ready": 2, "architectural-decision": 2,
                "generic-review": 2, "human-decision-required": 3,
                "unresolved-conflict": 3, "architectural-milestone": 3,
                "repeated-failure": 3, "security-safety": 3,
                "session-ready-for-review": 3,
            }
            assert status["event_defaults"] == expected
            assert set(status["legacy_l3_aliases"]) == {
                "security-gate", "publication", "identity-change", "deletion",
                "purchase", "xp-finalization"}
            before = state.read_bytes()
            r = run("add", "--title", "unknown", "--category", "made-up-event",
                    "--source-kind", "adr", "--source-ref", "docs/unknown.md",
                    state=state)
            assert r.returncode != 0 and state.read_bytes() == before
            r = run("add", "--title", "bad promotion", "--category",
                    "documentation-update", "--level", "3", "--source-kind",
                    "adr", "--source-ref", "docs/promote.md", state=state)
            assert r.returncode != 0 and state.read_bytes() == before
            r = run("add", "--title", "valid promotion", "--category",
                    "documentation-update", "--level", "3", "--level-reason",
                    "Toni must decide now", "--l3-trigger",
                    "human-decision-required", "--source-kind", "adr",
                    "--source-ref", "docs/promote.md", "--paused-context",
                    "review inbox verification", "--resume-hint",
                    "continue canonical routing check", state=state)
            promoted = json.loads(r.stdout)
            assert promoted["default_level"] == 2 and promoted["level"] == 3
            assert promoted["l3_trigger"] == "human-decision-required"
            r = run("add", "--title", "publication", "--category", "publication",
                    "--source-kind", "git", "--source-ref", "feature/publish",
                    "--paused-context", "publication verification",
                    "--resume-hint", "continue after Toni decides",
                    state=state)
            aliased = json.loads(r.stdout)
            assert aliased["event_class"] == "human-decision-required"
            assert aliased["level"] == 3 and aliased["default_level"] == 3
            return "catalog defaults, exact triggers, aliases, and overrides enforced"
        check("canonical event routing", canonical_event_routing)

        def policy_draft_denied():
            r = run("add", "--title", "t3", "--category", "automatic-approval",
                    "--level", "0", "--policy", "p-one", "--evidence", "x.md",
                    "--rollback", "remove x", "--source-kind", "policy",
                    state=state, policies=pol_draft)
            assert r.returncode != 0 and "not an approved" in output(r)
            return "draft denied"
        check("self-decision gate (draft)", policy_draft_denied)

        def policy_approved_allowed():
            r = run("add", "--title", "t4", "--category", "automatic-approval",
                    "--level", "0", "--policy", "p-one", "--evidence", "x.md",
                    "--rollback", "remove x", "--source-kind", "policy",
                    state=state, policies=pol_ok)
            out = json.loads(r.stdout)
            assert r.returncode == 0 and out["status"] == "approved"
            assert "self-approved" in out["decision_note"]
            return "approved policy self-approves with evidence"
        check("self-decision gate (approved)", policy_approved_allowed)

        def policy_scope_and_provenance():
            saved = json.loads(state.read_text(encoding="utf-8"))
            approved_entry = next(e for e in saved["entries"] if e.get("policy") == "p-one")
            provenance = approved_entry["policy_provenance"]
            assert provenance["verified"] is True
            assert provenance["registry_version"] == "9.9.9"
            assert provenance["registry_sha256"] == __import__("hashlib").sha256(
                pol_ok.read_bytes()).hexdigest()
            assert provenance["approved_by"] == "toni"
            before = state.read_bytes()
            denied = [
                ("--category", "green-verifier", "--source-kind", "policy"),
                ("--category", "automatic-approval", "--source-kind", "dhef",
                 "--source-ref", "PACKET-SCOPE"),
                ("--category", "automatic-approval", "--source-kind", "policy",
                 "--risk", "high"),
            ]
            for extra in denied:
                r = run("add", "--title", "scope mismatch", "--policy", "p-one",
                        "--evidence", "x.md", "--rollback", "remove x",
                        *extra, state=state, policies=pol_ok)
                assert r.returncode != 0 and state.read_bytes() == before
            r = run("add", "--title", "no rollback", "--category",
                    "automatic-approval", "--policy", "p-one", "--evidence", "x.md",
                    "--source-kind", "policy", state=state, policies=pol_ok)
            assert r.returncode != 0 and state.read_bytes() == before
            forged = td / "forged.md"
            forged.write_text(APPROVED.replace("approved_by: toni",
                                               "approved_by: mallory"), encoding="utf-8")
            r = run("add", "--title", "forged", "--category", "automatic-approval",
                    "--policy", "p-one", "--evidence", "x.md", "--rollback",
                    "remove x", "--source-kind", "policy", state=state,
                    policies=forged)
            assert r.returncode != 0 and state.read_bytes() == before
            raised_policy = td / "raised-policy.md"
            raised_policy.write_text(APPROVED.replace("level: 0", "level: 1"),
                                     encoding="utf-8")
            r = run("add", "--title", "brief instead of silent", "--category",
                    "automatic-approval", "--level", "1", "--level-reason",
                    "surface in daily brief", "--policy", "p-one", "--evidence",
                    "x.md", "--rollback", "remove x", "--source-kind", "policy",
                    state=state, policies=raised_policy)
            assert r.returncode == 0 and json.loads(r.stdout)["level"] == 1
            return "scope, source, risk, rollback, approver, and provenance enforced"
        check("policy scope and provenance", policy_scope_and_provenance)

        def spoof_blocked():
            r = run("add", "--title", "t5", "--category", "automatic-approval",
                    "--level", "0", "--policy", "p-two", "--evidence", "x.md",
                    "--rollback", "remove x", "--source-kind", "policy",
                    state=state, policies=pol_spoof)
            assert r.returncode != 0
            return "fenced-block status ignored"
        check("policy spoof resistance", spoof_blocked)

        def evidence_required():
            r = run("add", "--title", "t6", "--category", "automatic-approval",
                    "--level", "0", "--policy", "p-one", "--rollback", "remove x",
                    "--source-kind", "policy", state=state,
                    policies=pol_ok)
            assert r.returncode != 0 and "evidence" in output(r)
            return "L0 without evidence refused"
        check("evidence gate", evidence_required)

        def injection_blocked():
            r = run("add", "--title", "t7", "--category", "architectural-decision",
                    "--level", "2", "--source-kind", "dhef",
                    "--source-ref", "x; rm -rf /", state=state)
            assert r.returncode != 0 and "source-ref" in output(r)
            return "dhef ref injection refused at add"
        check("gate-command injection", injection_blocked)

        def escalate_pins():
            r = run("add", "--title", "needs toni", "--category",
                    "architectural-decision", "--source-kind", "adr",
                    "--source-ref", "docs/needs-toni.md", state=state)
            eid = json.loads(r.stdout)["id"][:8]
            r = run("escalate", "--id", eid, "--note", "raising",
                    "--l3-trigger", "human-decision-required",
                    "--paused-context", "escalation verification",
                    "--resume-hint", "return to verifier", state=state)
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
            action = out["gate_action"]
            assert action["adapter"] == "dhef"
            assert action["operation"] == "dhef.approve_task"
            assert action["arguments"]["task_id"] == "PACKET-1"
            assert "print-only" in out["gate_action_note"]
            return "structured gate action persisted, never executed"
        check("view-not-authority", approve_drives)

        def all_source_adapters():
            refs = {
                "dhef": "PACKET-2",
                "school": "school-task-2",
                "adr": "docs/adr/0021-review-inbox.md",
                "git": "feature/review-inbox-safe",
                "skill": "skills/example/SKILL.md",
                "policy": "docs/canon/STANDING_POLICIES.md",
            }
            for kind, ref in refs.items():
                r = run("add", "--title", f"{kind} action", "--category",
                        "architectural-decision", "--level", "2",
                        "--source-kind", kind, "--source-ref", ref, state=state)
                assert r.returncode == 0, output(r)
                eid = json.loads(r.stdout)["id"][:8]
                r = run("approve", "--id", eid, state=state)
                assert r.returncode == 0, output(r)
                action = json.loads(r.stdout)["gate_action"]
                assert action["adapter"] == kind and action["render_version"] == 1
            return "all six adapters emit structured print-only actions"
        check("all source adapters", all_source_adapters)

        def all_source_injection_blocked():
            bad = {
                "dhef": "x;echo",
                "school": "x|echo",
                "adr": "../docs/adr/x.md",
                "git": "feature/../../main",
                "skill": "skills/x/../../evil.md",
                "policy": "docs/canon/STANDING_POLICIES.md;echo",
            }
            before = state.read_bytes()
            for kind, ref in bad.items():
                r = run("add", "--title", "bad ref", "--category",
                        "architectural-decision", "--level", "2",
                        "--source-kind", kind, "--source-ref", ref, state=state)
                assert r.returncode != 0 and r.stdout == "", output(r)
                assert json.loads(r.stderr)["ok"] is False
                assert state.read_bytes() == before
            return "all source kinds reject unsafe refs without mutation"
        check("all-source injection and failure honesty", all_source_injection_blocked)

        def raw_refs_are_not_normalized():
            bad_refs = {
                "dhef": "SAFE-ID\nignored",
                "school": "A" * 128 + ";ignored",
                "adr": "docs/adr/safe.md\x1b[31m",
                "git": "feature/safe\nmain",
                "skill": "skills/safe/SKILL.md\tignored",
                "policy": "docs/canon/STANDING_POLICIES.md\nignored",
            }
            before = state.read_bytes()
            for kind, ref in bad_refs.items():
                r = run("add", "--title", "raw ref", "--category",
                        "architectural-decision", "--level", "2",
                        "--source-kind", kind, "--source-ref", ref, state=state)
                assert r.returncode != 0 and "source-ref" in r.stderr
                assert state.read_bytes() == before
            return "control/suffix input is rejected before normalization"
        check("raw source-ref rejection", raw_refs_are_not_normalized)

        def semantic_source_roots():
            bad_refs = {"adr": "data/review-inbox.json",
                        "skill": "docs/skill.md",
                        "policy": "docs/canon/OTHER.md"}
            before = state.read_bytes()
            for kind, ref in bad_refs.items():
                r = run("add", "--title", "wrong root", "--category",
                        "architectural-decision", "--level", "2",
                        "--source-kind", kind, "--source-ref", ref, state=state)
                assert r.returncode != 0 and state.read_bytes() == before
            return "repository source kinds enforce semantic roots"
        check("semantic source roots", semantic_source_roots)

        def authority_paths_are_canonical():
            rogue = td / "rogue.json"
            cmd = [sys.executable, str(CLI), "--state", str(rogue),
                   "--policies", str(pol_ok), "status"]
            env = os.environ.copy(); env.pop("NERO_INBOX_TEST_ROOT", None)
            r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
            assert r.returncode == 2 and "production authority is fixed" in r.stderr
            assert not rogue.exists()
            outside = td.parent / f"escape-{os.getpid()}.json"
            env["NERO_INBOX_TEST_ROOT"] = str(td)
            cmd[cmd.index(str(rogue))] = str(outside)
            r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
            assert r.returncode == 2 and "escapes" in r.stderr
            assert not outside.exists()
            env["NERO_INBOX_TEST_ROOT"] = str(ROOT.parent)
            canonical_cmd = [sys.executable, str(CLI), "status"]
            r = subprocess.run(canonical_cmd, capture_output=True, text=True,
                               env=env, timeout=30)
            assert r.returncode == 2 and "test authority root" in r.stderr
            return "production overrides and test-root escapes fail closed"
        check("canonical authority paths", authority_paths_are_canonical)

        def legacy_familiar_surface_removed():
            target = td / "must-not-be-written.txt"
            r = run("familiar", "--familiar-file", str(target), state=state)
            assert r.returncode == 2 and r.stdout == "", output(r)
            assert json.loads(r.stderr)["ok"] is False
            assert not target.exists()
            source = CLI.read_text(encoding="utf-8")
            assert "cmd_familiar" not in source and "--familiar-file" not in source
            return "legacy arbitrary-path Familiar writer is absent from parser and source"
        check("Familiar write surface removed", legacy_familiar_surface_removed)

        def explicit_schema_migration():
            stamp = "2026-07-17T10:00:00Z"
            base_entry = {
                "id": "11111111-1111-4111-8111-111111111111",
                "created_at": stamp, "level": 3, "category": "publication",
                "blocking": True, "risk": "medium", "title": "legacy publish",
                "source": {"kind": "git", "ref": "feature/legacy"},
                "evidence": [], "requested_by": "claude-lane",
                "status": "pending", "decided_at": None,
                "decision_note": None, "policy": None,
            }
            approved = copy.deepcopy(base_entry)
            approved.update({
                "id": "22222222-2222-4222-8222-222222222222", "level": 2,
                "category": "documentation-update", "blocking": False,
                "title": "legacy approved", "source": {"kind": "adr",
                "ref": "docs/legacy.md"}, "status": "approved",
                "decided_at": "2026-07-17T10:01:00Z",
            })
            automatic = copy.deepcopy(base_entry)
            automatic.update({
                "id": "33333333-3333-4333-8333-333333333333", "level": 0,
                "category": "automatic-approval", "blocking": False,
                "risk": "low", "title": "legacy automatic",
                "source": {"kind": "policy", "ref": ""},
                "evidence": ["x.md"], "status": "approved",
                "decided_at": "2026-07-17T10:01:00Z", "policy": "old-policy",
            })
            legacy_state = {
                "schema_version": 1, "revision": 3,
                "updated_at": "2026-07-17T10:02:00Z", "last_brief_at": None,
                "entries": [base_entry, approved, automatic],
            }
            legacy = td / "legacy.json"
            original = (json.dumps(legacy_state, indent=2) + "\n").encode()
            legacy.write_bytes(original)
            r = run("migrate", state=legacy)
            preview = json.loads(r.stdout)
            assert preview["dry_run"] is True and preview["entries"] == 3
            assert legacy.read_bytes() == original
            r = run("migrate", "--apply", state=legacy)
            assert r.returncode == 0, output(r)
            migrated = json.loads(legacy.read_text(encoding="utf-8"))
            assert migrated["schema_version"] == 3 and migrated["catalog_version"] == 1
            assert migrated["pending_brief"] is None and migrated["feed_receipts"] == []
            assert Path(f"{legacy}.v1.bak").read_bytes() == original
            assert migrated["entries"][0]["l3_trigger"] == "human-decision-required"
            assert migrated["entries"][1]["gate_state"] == "legacy_unknown"
            assert migrated["entries"][2]["policy_provenance"]["verified"] is False
            r = run("migrate", state=legacy)
            assert json.loads(r.stdout)["already_current"] is True

            ambiguous = td / "ambiguous.json"
            bad = copy.deepcopy(legacy_state)
            bad["entries"] = [copy.deepcopy(approved)]
            bad["entries"][0].update({"status": "pending", "decided_at": None,
                                      "level": 3, "blocking": True})
            ambiguous.write_text(json.dumps(bad), encoding="utf-8")
            before = ambiguous.read_bytes()
            r = run("migrate", state=ambiguous)
            assert r.returncode != 0 and "cannot infer L3 trigger" in r.stderr
            assert ambiguous.read_bytes() == before
            return "dry-run, backup, explicit apply, legacy marking, ambiguity refusal"
        check("explicit schema migration", explicit_schema_migration)

        def invalid_approval_is_atomic():
            before = state.read_bytes()
            r = run("add", "--title", "local policy question", "--category",
                    "architectural-decision", "--level", "2",
                    "--source-kind", "policy", state=state)
            assert r.returncode != 0 and "source-ref" in r.stderr
            assert state.read_bytes() == before
            return "dead-end policy review is refused without mutation"
        check("review source atomicity", invalid_approval_is_atomic)

        def escalated_items_remain_decidable():
            for verb in ("approve", "reject"):
                r = run("add", "--title", f"escalate then {verb}", "--category",
                        "architectural-decision", "--level", "2",
                        "--source-kind", "dhef", "--source-ref", f"ESC-{verb}",
                        state=state)
                eid = json.loads(r.stdout)["id"][:8]
                r = run("escalate", "--id", eid, "--l3-trigger",
                        "human-decision-required", "--paused-context",
                        "decision verification", "--resume-hint",
                        "continue verifier", state=state)
                assert r.returncode == 0, output(r)
                r = run(verb, "--id", eid, state=state)
                assert r.returncode == 0, output(r)
                entry = json.loads(r.stdout)["entry"]
                assert entry["status"] == ("approved" if verb == "approve" else "rejected")
                assert entry["level"] == 3 and entry.get("escalated_at")
            return "escalation history survives both terminal decisions"
        check("escalated item decisions", escalated_items_remain_decidable)

        def approval_is_idempotent():
            r = run("add", "--title", "retryable gate", "--category",
                    "architectural-decision", "--level", "2",
                    "--source-kind", "dhef", "--source-ref", "PACKET-RETRY",
                    state=state)
            eid = json.loads(r.stdout)["id"][:8]
            first = run("approve", "--id", eid, state=state)
            first_out = json.loads(first.stdout)
            revision = json.loads(state.read_text(encoding="utf-8"))["revision"]
            second = run("approve", "--id", eid, state=state)
            second_out = json.loads(second.stdout)
            assert first_out["gate_action"] == second_out["gate_action"]
            assert second_out["idempotent"] is True
            assert json.loads(state.read_text(encoding="utf-8"))["revision"] == revision
            return "retry returns the exact stored action without mutation"
        check("idempotent approval recovery", approval_is_idempotent)

        def corruption_fails_closed():
            base = json.loads(state.read_text(encoding="utf-8"))
            cases = []
            bad = copy.deepcopy(base); bad["revision"] = True; cases.append(bad)
            bad = copy.deepcopy(base); bad["updated_at"] = "not-a-time"; cases.append(bad)
            bad = copy.deepcopy(base); bad["entries"][0]["created_at"] = "bad"; cases.append(bad)
            bad = copy.deepcopy(base); bad["entries"].append(copy.deepcopy(bad["entries"][0])); cases.append(bad)
            bad = copy.deepcopy(base); bad["entries"][0]["category"] = "publication"; cases.append(bad)
            bad = copy.deepcopy(base); bad["entries"][0]["source"]["ref"] = "../escape"; cases.append(bad)
            approved = next(e for e in base["entries"] if e.get("gate_action"))
            bad = copy.deepcopy(base)
            target = next(e for e in bad["entries"] if e["id"] == approved["id"])
            target["gate_action"]["arguments"]["approved"] = False
            cases.append(bad)
            bad = copy.deepcopy(base); bad["entries"][0]["policy"] = "unexpected"; cases.append(bad)
            bad = copy.deepcopy(base); bad["entries"][0]["event_class"] = "generic-review"; cases.append(bad)
            bad = copy.deepcopy(base); bad["entries"][0]["default_level"] = 1; cases.append(bad)
            promoted = next(e for e in base["entries"] if e.get("level_reason"))
            bad = copy.deepcopy(base)
            next(e for e in bad["entries"] if e["id"] == promoted["id"])["l3_trigger"] = None
            cases.append(bad)
            policy_entry = next(e for e in base["entries"]
                                if (e.get("policy_provenance") or {}).get("verified"))
            bad = copy.deepcopy(base)
            next(e for e in bad["entries"] if e["id"] == policy_entry["id"])[
                "policy_provenance"]["registry_sha256"] = "0" * 64
            cases.append(bad)
            for index, candidate in enumerate(cases):
                corrupt = td / f"corrupt-{index}.json"
                corrupt.write_text(json.dumps(candidate), encoding="utf-8")
                before = corrupt.read_bytes()
                r = run("status", state=corrupt)
                assert r.returncode != 0 and r.stdout == "" and "corrupt" in r.stderr, (
                    index, output(r))
                assert corrupt.read_bytes() == before, index
            return f"{len(cases)} malformed-state variants refused unchanged"
        check("schema corruption matrix", corruption_fails_closed)

        def state_size_bound():
            oversized = td / "oversized.json"
            oversized.write_bytes(b" " * (5 * 1024 * 1024 + 1))
            before = oversized.stat().st_size
            r = run("status", state=oversized)
            assert r.returncode != 0 and "exceeds" in r.stderr
            assert oversized.stat().st_size == before
            non_regular = td / "non-regular.json"
            non_regular.mkdir()
            r = run("status", state=non_regular)
            assert r.returncode == 2 and "regular non-link file" in r.stderr
            return "oversized state is rejected before JSON parsing"
        check("state size bound", state_size_bound)

        def concurrent_adds():
            concurrent = td / "concurrent.json"
            procs = []
            env = os.environ.copy()
            env["NERO_INBOX_TEST_ROOT"] = str(td)
            for index in range(12):
                cmd = [sys.executable, str(CLI), "--state", str(concurrent),
                       "--policies", str(td / "default-policies.md"),
                       "add", "--title", f"concurrent-{index}", "--category",
                       "documentation-update", "--level", "2", "--source-kind",
                       "adr", "--source-ref", f"docs/concurrent-{index}.md"]
                procs.append(subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, env=env))
            results = [proc.communicate(timeout=30) + (proc.returncode,) for proc in procs]
            assert all(code == 0 for _out, _err, code in results), results
            saved = json.loads(concurrent.read_text(encoding="utf-8"))
            assert saved["revision"] == 12 and len(saved["entries"]) == 12
            assert Path(f"{concurrent}.lock").exists()
            assert not list(td.glob("concurrent.json.lock.stale.*"))
            return "12 concurrent writers, no lost update; lock path persists"
        check("kernel-lock concurrency", concurrent_adds)

        def crash_releases_lock():
            recovery = td / "recovery.json"
            code = (
                "import sys,time; sys.path.insert(0,sys.argv[1]); "
                "import inboxctl; s=inboxctl.Store(sys.argv[2]); "
                "c=s.lock(); c.__enter__(); print('locked',flush=True); time.sleep(60)"
            )
            holder = subprocess.Popen(
                [sys.executable, "-B", "-c", code, str(CLI.parent), str(recovery)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert holder.stdout.readline().strip() == "locked"
            holder.terminate(); holder.wait(timeout=10)
            started = time.monotonic()
            r = run("add", "--title", "after crash", "--category",
                    "documentation-update", "--level", "2", "--source-kind",
                    "adr", "--source-ref", "docs/recovery.md", state=recovery)
            assert r.returncode == 0, output(r)
            assert time.monotonic() - started < 2.0
            return "process death releases the persistent advisory lock immediately"
        check("crash lock recovery", crash_releases_lock)

        def no_shell_out_path():
            source = CLI.read_text(encoding="utf-8")
            forbidden = ("import subprocess", "os.system(", "shell=True",
                         "subprocess.", "GATE_COMMANDS")
            assert not any(token in source for token in forbidden)
            return "static source contains no shell/subprocess gate path"
        check("queue-view never authority", no_shell_out_path)

        def cli_input_honesty():
            r = run("brief", "--daypart", "morning\nINJECTED", state=state)
            assert r.returncode == 2 and r.stdout == ""
            assert json.loads(r.stderr)["ok"] is False
            r = run("reject", "--id", "0000", state=state, stdin="x" * 2001)
            assert r.returncode == 2 and "exceeds 2000" in r.stderr
            base = {
                "v": 1, "provider": "adr", "event": "proposed",
                "id": "ADR-typed", "title": "typed feed",
                "source_ref": "docs/adr/typed.md",
            }
            before = state.read_bytes()
            for field, invalid in (("v", True), ("source_ref", 7),
                                   ("policy", []), ("risk", False)):
                envelope = dict(base)
                envelope[field] = invalid
                r = run("feed", state=state, stdin=json.dumps(envelope))
                assert r.returncode == 2 and r.stdout == "", (field, output(r))
                assert json.loads(r.stderr)["ok"] is False
                assert "Traceback" not in r.stderr and state.read_bytes() == before
            return "argument/feed type errors are JSON and stdin notes are bounded"
        check("CLI input failure honesty", cli_input_honesty)

        def failed_backup_is_cleaned():
            target = td / "backup-cleanup.json"
            original_fsync = INBOX.os.fsync
            INBOX.os.fsync = lambda _fd: (_ for _ in ()).throw(OSError("disk full"))
            try:
                try:
                    INBOX._write_backup(target, b"legacy bytes", 1)
                except OSError:
                    pass
                else:
                    raise AssertionError("simulated backup failure unexpectedly succeeded")
            finally:
                INBOX.os.fsync = original_fsync
            assert not Path(f"{target}.v1.bak").exists()
            return "failed migration backup leaves no blocking partial file"
        check("migration backup cleanup", failed_backup_is_cleaned)

        def brief_delivery_ack():
            before = json.loads(state.read_text(encoding="utf-8"))
            r = run("brief", state=state)
            assert "reading time" in r.stdout.lower()
            assert "Today's summary:" in r.stdout and "Brief ID:" in r.stdout
            first, after_render = r.stdout, json.loads(state.read_text(encoding="utf-8"))
            assert after_render["last_brief_at"] == before["last_brief_at"]
            brief_id = after_render["pending_brief"]["id"]
            r = run("brief", state=state)
            assert r.stdout == first
            after_replay = json.loads(state.read_text(encoding="utf-8"))
            assert after_replay["revision"] == after_render["revision"]
            r = run("brief", "--ack", brief_id, state=state)
            ack = json.loads(r.stdout)
            after_ack = json.loads(state.read_text(encoding="utf-8"))
            assert ack["acknowledged"] == brief_id
            assert after_ack["pending_brief"] is None
            assert after_ack["last_brief_at"] == after_render["pending_brief"]["through_at"]
            return "render replays byte-for-byte; explicit receipt advances watermark"
        check("delivery-safe brief acknowledgement", brief_delivery_ack)

        def adaptive_brief_modes():
            expected = {
                "highlights": "Today's highlights:",
                "minimum": "I'll keep this brief.",
                "detailed": "Today's summary:",
            }
            for mode, marker in expected.items():
                r = run("brief", "--mode", mode, state=state)
                assert r.returncode == 0 and marker in r.stdout
                assert r.stdout.rstrip().splitlines()[-1].startswith(
                    "Estimated reading time:")
                pending = json.loads(state.read_text(encoding="utf-8"))["pending_brief"]
                r = run("brief", "--ack", pending["id"], state=state)
                assert r.returncode == 0
            return "explicit detailed/highlights/minimum modes retain honest reading time"
        check("adaptive brief modes", adaptive_brief_modes)

        def cold_feed_idempotency():
            envelope = json.dumps({
                "v": 1, "provider": "adr", "event": "proposed",
                "id": "ADR-0999:v1", "title": "ADR-0999 awaits review",
                "source_ref": "docs/adr/0999-example.md",
                "evidence": ["docs/adr/0999-example.md"],
            })
            r = run("feed", state=state, stdin=envelope)
            assert r.returncode == 0, output(r)
            first = json.loads(r.stdout)
            before = state.read_bytes()
            r = run("feed", state=state, stdin=envelope)
            again = json.loads(r.stdout)
            assert again["idempotent"] is True
            assert again["entry"]["id"] == first["entry"]["id"]
            assert state.read_bytes() == before
            return "versioned ADR feed is cold, routed, and byte-idempotent"
        check("cold feed idempotency", cold_feed_idempotency)

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
