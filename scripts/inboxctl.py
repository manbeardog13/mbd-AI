#!/usr/bin/env python3
"""Review Inbox - the operator attention surface (ADR-0021, review-inbox.spec).

v1.4 Phase 2: delivery-safe replayable briefs, explicit adaptive rendering,
idempotent cold source feeds, and exact operator-facing queue formats.
Cold, stdlib-only, run-and-exit. The inbox is a queue-view over authoritative
gates, never a second authority.
"""
from __future__ import annotations

import argparse
import copy
import contextlib
import errno
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="strict")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "data" / "review-inbox.json"
DEFAULT_POLICIES = ROOT / "docs" / "canon" / "STANDING_POLICIES.md"
SCHEMA_VERSION = 3
EVENT_CATALOG_VERSION = 1
MAX_STATE_BYTES = 5 * 1024 * 1024
MAX_ENTRIES = 10_000
MAX_EVIDENCE_ITEMS = 100
MAX_FEED_RECEIPTS = 10_000
MAX_BRIEF_BYTES = 64 * 1024

L3_TRIGGERS = (
    "human-decision-required",
    "unresolved-conflict",
    "architectural-milestone",
    "repeated-failure",
    "security-safety",
    "session-ready-for-review",
)
EVENT_CATALOG = {
    "routine-read": (0, None),
    "green-verifier": (0, None),
    "automatic-approval": (0, None),
    "index-regeneration": (0, None),
    "completed-task": (1, None),
    "preapproved-promotion": (1, None),
    "archived-item": (1, None),
    "lexicon-observation": (1, None),
    "documentation-update": (2, None),
    "completed-skill": (2, None),
    "dhef-gate-ready": (2, None),
    "architectural-decision": (2, None),
    "generic-review": (2, None),
    "human-decision-required": (3, "human-decision-required"),
    "unresolved-conflict": (3, "unresolved-conflict"),
    "architectural-milestone": (3, "architectural-milestone"),
    "repeated-failure": (3, "repeated-failure"),
    "security-safety": (3, "security-safety"),
    "session-ready-for-review": (3, "session-ready-for-review"),
}
LEGACY_L3_ALIASES = {
    "security-gate": "security-safety",
    "publication": "human-decision-required",
    "identity-change": "architectural-milestone",
    "deletion": "human-decision-required",
    "purchase": "human-decision-required",
    "xp-finalization": "human-decision-required",
}
L3_CLASSES = tuple(LEGACY_L3_ALIASES)
STATUSES = ("pending", "approved", "rejected")
GATE_STATES = ("not_requested", "not_applicable", "awaiting_execution",
               "legacy_unknown")
V1_GATE_STATES = ("not_requested", "not_applicable", "awaiting_execution")
SOURCE_KINDS = ("dhef", "school", "adr", "git", "skill", "policy")
CATEGORY_RE = re.compile(r"^[a-z0-9-]{1,40}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_REPO_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,239}$")
SAFE_GIT_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
POLICY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
RISKS = ("low", "medium", "high")
V1_TOP_LEVEL_FIELDS = {"schema_version", "revision", "updated_at",
                       "last_brief_at", "entries"}
V1_ENTRY_FIELDS = {
    "id", "created_at", "level", "category", "blocking", "risk", "title",
    "source", "evidence", "requested_by", "status", "decided_at",
    "decision_note", "policy", "escalated_at", "gate_state", "gate_action",
}
V2_TOP_LEVEL_FIELDS = {"schema_version", "catalog_version", "revision",
                       "updated_at", "last_brief_at", "migration", "entries"}
V2_ENTRY_FIELDS = V1_ENTRY_FIELDS | {
    "event_class", "default_level", "l3_trigger", "level_reason",
    "policy_provenance", "rollback",
}
TOP_LEVEL_FIELDS = {"schema_version", "catalog_version", "revision",
                    "updated_at", "last_brief_at", "pending_brief",
                    "feed_receipts", "migration", "entries"}
ENTRY_FIELDS = V1_ENTRY_FIELDS | {
    "event_class", "default_level", "l3_trigger", "level_reason",
    "policy_provenance", "rollback", "paused_context", "resume_hint",
}


class CommittedStateError(OSError):
    """The replace completed, but a later durability step failed."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False),
              file=sys.stderr)
        raise SystemExit(2)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def printable(text: str, limit: int) -> str:
    clean = "".join(ch for ch in text if ch.isprintable() or ch == " ")
    return " ".join(clean.split())[:limit]


def blank() -> dict:
    return {"schema_version": SCHEMA_VERSION,
            "catalog_version": EVENT_CATALOG_VERSION,
            "revision": 0, "updated_at": None, "last_brief_at": None,
            "pending_brief": None, "feed_receipts": [],
            "migration": None, "entries": []}


def _state_error(path: Path, detail: str) -> ValueError:
    return ValueError(f"corrupt inbox state {path}: {detail}")


def _valid_timestamp(value) -> bool:
    if (not isinstance(value, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value)):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0


def _parse_timestamp(value: str) -> datetime:
    if not _valid_timestamp(value):
        raise ValueError(f"invalid canonical UTC timestamp {value!r}")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _valid_date(value) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _valid_text(value, limit: int, *, empty: bool = False) -> bool:
    return (isinstance(value, str) and len(value) <= limit
            and (empty or bool(value)) and all(ch.isprintable() for ch in value))


def event_rule(category: str) -> tuple[str, int, str | None]:
    if category in LEGACY_L3_ALIASES:
        event_class = LEGACY_L3_ALIASES[category]
    elif category in EVENT_CATALOG:
        event_class = category
    else:
        raise ValueError(
            f"unknown event category {category!r}; use a cataloged event class")
    default_level, trigger = EVENT_CATALOG[event_class]
    return event_class, default_level, trigger


def validate_source_ref(kind: str, ref: str) -> None:
    """Validate source identifiers as data, never as shell fragments."""
    if kind not in SOURCE_KINDS:
        raise ValueError(f"unsupported source kind {kind!r}")
    if not isinstance(ref, str):
        raise ValueError("source ref must be a string")
    if kind == "policy" and ref == "":
        return  # Inbox-local pending/self-decision; approval preflight rejects it.
    if kind in ("dhef", "school"):
        if not SAFE_ID_RE.fullmatch(ref):
            raise ValueError(
                f"{kind} source-ref must match [A-Za-z0-9][A-Za-z0-9._-]{{0,127}}")
        return
    if kind == "git":
        parts = ref.split("/")
        if (not SAFE_GIT_REF_RE.fullmatch(ref) or ref.endswith(("/", "."))
                or ".." in ref or "@{" in ref or "//" in ref
                or any(p.startswith(".") or p.endswith(".lock") for p in parts)):
            raise ValueError("git source-ref is not a safe branch/ref name")
        return
    parts = ref.split("/")
    if (not SAFE_REPO_REF_RE.fullmatch(ref) or "//" in ref or ".." in parts
            or "." in parts or any(not p for p in parts)):
        raise ValueError(f"{kind} source-ref must be a safe relative path or slug")
    if kind == "adr" and not (ref.startswith("docs/") and ref.endswith(".md")):
        raise ValueError("adr source-ref must be a Markdown path under docs/")
    if kind == "skill" and not (ref.startswith("skills/") and ref.endswith(".md")):
        raise ValueError("skill source-ref must be a Markdown path under skills/")
    if kind == "policy" and ref != "docs/canon/STANDING_POLICIES.md":
        raise ValueError("policy source-ref must name the canonical registry")


def build_gate_action(kind: str, ref: str) -> dict:
    """Return immutable structured next-action data. This never executes it."""
    validate_source_ref(kind, ref)
    if kind == "policy" and not ref:
        raise ValueError(
            "policy approval requires a concrete canonical-registry source-ref")
    actions = {
        "dhef": ("dhef.approve_task", {
            "script": "skills/nero-hybrid-cognition/scripts/hybrid_brain.py",
            "state": "data/hybrid-brain.json", "task_id": ref,
            "approved": True, "quality": 0.9,
            "decision_note": "approved-via-inbox",
        }),
        "school": ("school.finalize_task", {
            "script": "School/tooling/schoolctl.py", "task": ref,
        }),
        "adr": ("adr.record_decision", {
            "ref": ref, "status": "accepted", "publication_gate_required": True,
        }),
        "git": ("git.merge_after_review", {
            "ref": ref, "publication_gate_required": True,
        }),
        "skill": ("skill.update_lifecycle", {
            "ref": ref,
            "spec": "docs/specs/skill-lifecycle.spec.md",
        }),
        "policy": ("policy.review_registry", {
            "ref": ref or None, "publication_gate_required": True,
        }),
    }
    operation, arguments = actions[kind]
    return {"adapter": kind, "render_version": 1,
            "operation": operation, "arguments": arguments}


def _validate_gate_action(action, kind: str, ref: str) -> None:
    if not isinstance(action, dict) or set(action) != {
            "adapter", "render_version", "operation", "arguments"}:
        raise ValueError("gate_action has an invalid shape")
    operations = {
        "dhef": "dhef.approve_task", "school": "school.finalize_task",
        "adr": "adr.record_decision", "git": "git.merge_after_review",
        "skill": "skill.update_lifecycle", "policy": "policy.review_registry",
    }
    if (action["adapter"] != kind or action["render_version"] != 1
            or action["operation"] != operations[kind]
            or not isinstance(action["arguments"], dict)):
        raise ValueError("gate_action does not match its source and render version")
    args = action["arguments"]
    ref_field = "task_id" if kind == "dhef" else "task" if kind == "school" else "ref"
    if args.get(ref_field) != ref:
        raise ValueError("gate_action reference does not match its source")
    required = {
        "dhef": {"script", "state", "task_id", "approved", "quality",
                 "decision_note"},
        "school": {"script", "task"},
        "adr": {"ref", "status", "publication_gate_required"},
        "git": {"ref", "publication_gate_required"},
        "skill": {"ref", "spec"},
        "policy": {"ref", "publication_gate_required"},
    }[kind]
    if set(args) != required:
        raise ValueError("gate_action arguments have an invalid shape")
    fixed = {
        "dhef": {"script": "skills/nero-hybrid-cognition/scripts/hybrid_brain.py",
                 "state": "data/hybrid-brain.json", "approved": True,
                 "quality": 0.9, "decision_note": "approved-via-inbox"},
        "school": {"script": "School/tooling/schoolctl.py"},
        "adr": {"status": "accepted", "publication_gate_required": True},
        "git": {"publication_gate_required": True},
        "skill": {"spec": "docs/specs/skill-lifecycle.spec.md"},
        "policy": {"publication_gate_required": True},
    }[kind]
    if any(args.get(key) != value for key, value in fixed.items()):
        raise ValueError("gate_action fixed arguments are invalid")


def validate_state_v1(state, path: Path) -> dict:
    if not isinstance(state, dict):
        raise _state_error(path, "bad top-level shape")
    unknown = set(state) - V1_TOP_LEVEL_FIELDS
    missing = V1_TOP_LEVEL_FIELDS - set(state)
    if unknown or missing:
        raise _state_error(path, f"top-level fields missing={sorted(missing)} "
                           f"unknown={sorted(unknown)}")
    if not isinstance(state["entries"], list):
        raise _state_error(path, "entries must be a list")
    if state.get("schema_version") != 1:
        raise ValueError(f"expected schema 1 inbox in {path}")
    if (isinstance(state["revision"], bool)
            or not isinstance(state["revision"], int) or state["revision"] < 0):
        raise _state_error(path, "revision must be a non-negative integer")
    for field in ("updated_at", "last_brief_at"):
        if state[field] is not None and not _valid_timestamp(state[field]):
            raise _state_error(path, f"{field} must be a UTC ISO-8601 timestamp or null")

    ids = set()
    required = V1_ENTRY_FIELDS - {"escalated_at", "gate_state", "gate_action"}
    for index, e in enumerate(state["entries"]):
        where = f"entry {index}"
        if not isinstance(e, dict):
            raise _state_error(path, f"{where} must be an object")
        unknown = set(e) - V1_ENTRY_FIELDS
        missing = required - set(e)
        if unknown or missing:
            raise _state_error(path, f"{where} fields missing={sorted(missing)} "
                               f"unknown={sorted(unknown)}")
        if not isinstance(e["id"], str):
            raise _state_error(path, f"{where} id must be a UUID string")
        try:
            entry_uuid = uuid.UUID(e["id"])
        except (ValueError, AttributeError):
            raise _state_error(path, f"{where} id must be a UUID string") from None
        if str(entry_uuid) != e["id"] or e["id"] in ids:
            raise _state_error(path, f"{where} id is non-canonical or duplicated")
        ids.add(e["id"])
        if not _valid_timestamp(e["created_at"]):
            raise _state_error(path, f"{where} created_at is invalid")
        if isinstance(e["level"], bool) or e["level"] not in (0, 1, 2, 3):
            raise _state_error(path, f"{where} level is invalid")
        if not isinstance(e["blocking"], bool) or e["blocking"] != (e["level"] == 3):
            raise _state_error(path, f"{where} blocking must equal (level == 3)")
        if not isinstance(e["category"], str) or not CATEGORY_RE.fullmatch(e["category"]):
            raise _state_error(path, f"{where} category is invalid")
        try:
            event_rule(e["category"])
        except ValueError as exc:
            raise _state_error(path, f"{where} {exc}") from None
        if e["category"] in L3_CLASSES and e["level"] != 3:
            raise _state_error(path, f"{where} demotes immutable L3 category")
        if e["risk"] not in RISKS:
            raise _state_error(path, f"{where} risk is invalid")
        if not _valid_text(e["title"], 200):
            raise _state_error(path, f"{where} title is invalid")
        if not _valid_text(e["requested_by"], 100):
            raise _state_error(path, f"{where} requested_by is invalid")
        if not isinstance(e["evidence"], list) or any(
                not _valid_text(item, 1000) for item in e["evidence"]):
            raise _state_error(path, f"{where} evidence is invalid")
        if e["policy"] is not None and (
                not isinstance(e["policy"], str) or not POLICY_RE.fullmatch(e["policy"])):
            raise _state_error(path, f"{where} policy is invalid")
        if e["level"] in (0, 1):
            if not e["policy"] or not e["evidence"] or e["status"] != "approved":
                raise _state_error(path, f"{where} self-approval proof is incomplete")
        elif e["policy"] is not None:
            raise _state_error(path, f"{where} policy is forbidden at L2/L3")
        if not isinstance(e["source"], dict) or set(e["source"]) != {"kind", "ref"}:
            raise _state_error(path, f"{where} source shape is invalid")
        try:
            validate_source_ref(e["source"]["kind"], e["source"]["ref"])
        except ValueError as exc:
            raise _state_error(path, f"{where} {exc}") from None
        if e["status"] not in STATUSES:
            raise _state_error(path, f"{where} status is invalid")
        if e["decision_note"] is not None and not _valid_text(
                e["decision_note"], 2000, empty=True):
            raise _state_error(path, f"{where} decision_note is invalid")
        if e["status"] == "pending":
            if e["decided_at"] is not None:
                raise _state_error(path, f"{where} pending item has decided_at")
        elif not _valid_timestamp(e["decided_at"]):
            raise _state_error(path, f"{where} decided item lacks a valid decided_at")
        if "escalated_at" in e and (
                not _valid_timestamp(e["escalated_at"])
                or e["level"] != 3 or not e["blocking"]):
            raise _state_error(path, f"{where} escalation fields are inconsistent")

        has_gate_state = "gate_state" in e
        has_gate_action = "gate_action" in e
        if has_gate_state != has_gate_action:
            raise _state_error(path, f"{where} gate fields must appear together")
        if has_gate_state:
            gate_state, gate_action = e["gate_state"], e["gate_action"]
            if gate_state not in V1_GATE_STATES:
                raise _state_error(path, f"{where} gate_state is invalid")
            if e["status"] == "pending" and (
                    gate_state != "not_requested" or gate_action is not None):
                raise _state_error(path, f"{where} pending gate state is inconsistent")
            if e["status"] == "rejected" and (
                    gate_state != "not_applicable" or gate_action is not None):
                raise _state_error(path, f"{where} rejected gate state is inconsistent")
            if e["status"] == "approved":
                automatic = e["level"] in (0, 1) and bool(e["policy"])
                if automatic:
                    if gate_state != "not_applicable" or gate_action is not None:
                        raise _state_error(path, f"{where} automatic gate state is inconsistent")
                else:
                    if gate_state != "awaiting_execution":
                        raise _state_error(path, f"{where} approved gate is not awaiting execution")
                    try:
                        _validate_gate_action(gate_action, e["source"]["kind"],
                                              e["source"]["ref"])
                    except ValueError as exc:
                        raise _state_error(path, f"{where} {exc}") from None
    return state


def _policy_provenance_digest(provenance: dict) -> str:
    payload = {key: value for key, value in provenance.items()
               if key != "provenance_sha256"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_policy_provenance(provenance, entry: dict, path: Path,
                                where: str, migrated: bool) -> None:
    if not isinstance(provenance, dict):
        raise _state_error(path, f"{where} policy_provenance must be an object")
    if provenance.get("verified") is False:
        if (not migrated or set(provenance) != {"name", "verified", "reason"}
                or provenance.get("name") != entry["policy"]
                or provenance.get("reason") != "migrated-from-schema-v1"):
            raise _state_error(path, f"{where} invalid legacy policy provenance")
        return
    required = {
        "name", "verified", "registry", "registry_version", "registry_sha256",
        "policy_level", "event_class", "categories", "source_kinds", "risks",
        "evidence_required", "rollback", "approved_by", "approved_at",
        "provenance_sha256",
    }
    if set(provenance) != required or provenance.get("verified") is not True:
        raise _state_error(path, f"{where} invalid verified policy provenance shape")
    string_fields = ("name", "registry", "registry_version", "registry_sha256",
                     "event_class", "rollback", "approved_by", "approved_at",
                     "provenance_sha256")
    if any(not isinstance(provenance[field], str) for field in string_fields):
        raise _state_error(path, f"{where} policy provenance types are invalid")
    if (isinstance(provenance["policy_level"], bool)
            or not isinstance(provenance["policy_level"], int)
            or not isinstance(provenance["evidence_required"], bool)):
        raise _state_error(path, f"{where} policy provenance scalar types are invalid")
    if (provenance["name"] != entry["policy"]
            or provenance["registry"] != "docs/canon/STANDING_POLICIES.md"
            or not re.fullmatch(r"\d+\.\d+\.\d+", provenance["registry_version"])
            or not re.fullmatch(r"[0-9a-f]{64}", provenance["registry_sha256"])
            or not re.fullmatch(r"[0-9a-f]{64}", provenance["provenance_sha256"])
            or provenance["provenance_sha256"] != _policy_provenance_digest(provenance)
            or provenance["policy_level"] != entry["level"]
            or provenance["event_class"] != entry["event_class"]
            or provenance["approved_by"] != "toni"
            or not _valid_date(provenance["approved_at"])
            or not _valid_text(provenance["rollback"], 1000)):
        raise _state_error(path, f"{where} policy provenance does not authorize entry")
    for field, allowed in (("categories", {entry["category"]}),
                           ("source_kinds", {entry["source"]["kind"]}),
                           ("risks", {entry["risk"]})):
        values = provenance[field]
        if (not isinstance(values, list) or not values
                or any(not isinstance(item, str) for item in values)
                or not allowed.issubset(set(values))):
            raise _state_error(path, f"{where} policy provenance {field} mismatch")
    try:
        if any(event_rule(category)[0] != provenance["event_class"]
               for category in provenance["categories"]):
            raise _state_error(path, f"{where} provenance category catalog mismatch")
    except ValueError as exc:
        raise _state_error(path, f"{where} {exc}") from None
    if (any(kind not in SOURCE_KINDS for kind in provenance["source_kinds"])
            or any(risk not in RISKS for risk in provenance["risks"])):
        raise _state_error(path, f"{where} provenance domain values are invalid")


def _validate_phase2_state(state: dict, path: Path, *, allow_dirty: bool) -> None:
    receipts = state["feed_receipts"]
    if (not isinstance(receipts, list)
            or len(receipts) > MAX_FEED_RECEIPTS):
        raise _state_error(
            path, f"feed_receipts must be a list of at most {MAX_FEED_RECEIPTS}")
    keys = set()
    for index, receipt in enumerate(receipts):
        if (not isinstance(receipt, dict)
                or set(receipt) != {"key", "entry_id", "at"}):
            raise _state_error(path, f"feed receipt {index} shape is invalid")
        if (not isinstance(receipt["key"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", receipt["key"])
                or receipt["key"] in keys):
            raise _state_error(path, f"feed receipt {index} key is invalid")
        try:
            entry_id = str(uuid.UUID(receipt["entry_id"]))
        except (ValueError, TypeError, AttributeError):
            raise _state_error(path, f"feed receipt {index} entry_id is invalid") from None
        if entry_id != receipt["entry_id"] or not _valid_timestamp(receipt["at"]):
            raise _state_error(path, f"feed receipt {index} fields are invalid")
        if (not allow_dirty and state["updated_at"]
                and _parse_timestamp(receipt["at"]) > _parse_timestamp(state["updated_at"])):
            raise _state_error(path, f"feed receipt {index} is newer than state")
        keys.add(receipt["key"])

    brief = state["pending_brief"]
    if brief is None:
        return
    required = {"id", "created_at", "since_at", "through_at", "mode",
                "content", "sha256"}
    if not isinstance(brief, dict) or set(brief) != required:
        raise _state_error(path, "pending_brief shape is invalid")
    try:
        brief_id = str(uuid.UUID(brief["id"]))
    except (ValueError, TypeError, AttributeError):
        raise _state_error(path, "pending_brief id is invalid") from None
    if brief_id != brief["id"]:
        raise _state_error(path, "pending_brief id is non-canonical")
    if (brief["mode"] not in ("standard", "highlights", "minimum", "detailed")
            or not _valid_timestamp(brief["created_at"])
            or not _valid_timestamp(brief["since_at"])
            or not _valid_timestamp(brief["through_at"])
            or not isinstance(brief["content"], str)
            or not brief["content"]
            or len(brief["content"].encode("utf-8")) > MAX_BRIEF_BYTES
            or not re.fullmatch(r"[0-9a-f]{64}", brief["sha256"])
            or hashlib.sha256(brief["content"].encode("utf-8")).hexdigest()
            != brief["sha256"]):
        raise _state_error(path, "pending_brief fields are invalid")
    since_dt, through_dt = (_parse_timestamp(brief["since_at"]),
                            _parse_timestamp(brief["through_at"]))
    if since_dt > through_dt or _parse_timestamp(brief["created_at"]) < through_dt:
        raise _state_error(path, "pending_brief time window is invalid")
    if state["last_brief_at"] and brief["since_at"] != state["last_brief_at"]:
        raise _state_error(path, "pending_brief does not start at the acknowledged watermark")
    if (not allow_dirty and state["updated_at"]
            and _parse_timestamp(brief["created_at"]) > _parse_timestamp(state["updated_at"])):
        raise _state_error(path, "pending_brief is newer than state")


def validate_state(state, path: Path, *, allow_dirty: bool = False) -> dict:
    if not isinstance(state, dict):
        raise _state_error(path, "bad top-level shape")
    unknown = set(state) - TOP_LEVEL_FIELDS
    missing = TOP_LEVEL_FIELDS - set(state)
    if unknown or missing:
        raise _state_error(path, f"top-level fields missing={sorted(missing)} "
                           f"unknown={sorted(unknown)}")
    if state["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported inbox schema in {path}; run migrate first")
    if (isinstance(state["catalog_version"], bool)
            or state["catalog_version"] != EVENT_CATALOG_VERSION):
        raise ValueError(f"unsupported event catalog in {path}")
    if (isinstance(state["revision"], bool) or not isinstance(state["revision"], int)
            or state["revision"] < 0):
        raise _state_error(path, "revision must be a non-negative integer")
    if not isinstance(state["entries"], list) or len(state["entries"]) > MAX_ENTRIES:
        raise _state_error(path, f"entries must be a list of at most {MAX_ENTRIES}")
    for field in ("updated_at", "last_brief_at"):
        if state[field] is not None and not _valid_timestamp(state[field]):
            raise _state_error(path, f"{field} must be a canonical UTC timestamp or null")
    if state["revision"] > 0 and state["updated_at"] is None:
        raise _state_error(path, "updated_at is required after the first revision")
    if (not allow_dirty and state["last_brief_at"] and state["updated_at"]
            and _parse_timestamp(state["last_brief_at"])
            > _parse_timestamp(state["updated_at"])):
        raise _state_error(path, "last_brief_at cannot be newer than updated_at")
    _validate_phase2_state(state, path, allow_dirty=allow_dirty)
    migration = state["migration"]
    migrated = isinstance(migration, dict) and migration.get("from") == 1
    if migration is not None:
        allowed_shapes = ({"from", "at"}, {"from", "at", "phase2_at"})
        if (not isinstance(migration, dict) or set(migration) not in allowed_shapes
                or isinstance(migration.get("from"), bool)
                or migration.get("from") not in (1, 2)
                or not _valid_timestamp(migration.get("at"))
                or ("phase2_at" in migration
                    and not _valid_timestamp(migration.get("phase2_at")))):
            raise _state_error(path, "invalid migration record")
        if (not allow_dirty and state["updated_at"]
                and _parse_timestamp(migration["at"])
                > _parse_timestamp(state["updated_at"])):
            raise _state_error(path, "migration timestamp is newer than state")

    ids = set()
    required = ENTRY_FIELDS - {"escalated_at"}
    for index, entry in enumerate(state["entries"]):
        where = f"entry {index}"
        if not isinstance(entry, dict):
            raise _state_error(path, f"{where} must be an object")
        unknown = set(entry) - ENTRY_FIELDS
        missing = required - set(entry)
        if unknown or missing:
            raise _state_error(path, f"{where} fields missing={sorted(missing)} "
                               f"unknown={sorted(unknown)}")
        try:
            entry_uuid = uuid.UUID(entry["id"])
        except (ValueError, TypeError, AttributeError):
            raise _state_error(path, f"{where} id must be a UUID string") from None
        if str(entry_uuid) != entry["id"] or entry["id"] in ids:
            raise _state_error(path, f"{where} id is non-canonical or duplicated")
        ids.add(entry["id"])
        if not _valid_timestamp(entry["created_at"]):
            raise _state_error(path, f"{where} created_at is invalid")
        if (not allow_dirty and state["updated_at"] and _parse_timestamp(entry["created_at"])
                > _parse_timestamp(state["updated_at"])):
            raise _state_error(path, f"{where} created_at is newer than state")
        if not isinstance(entry["category"], str) or not CATEGORY_RE.fullmatch(entry["category"]):
            raise _state_error(path, f"{where} category is invalid")
        try:
            expected_class, expected_default, expected_trigger = event_rule(entry["category"])
        except ValueError as exc:
            raise _state_error(path, f"{where} {exc}") from None
        if (entry["event_class"] != expected_class
                or isinstance(entry["default_level"], bool)
                or entry["default_level"] != expected_default):
            raise _state_error(path, f"{where} event routing does not match catalog")
        level = entry["level"]
        if isinstance(level, bool) or level not in (0, 1, 2, 3) or level < expected_default:
            raise _state_error(path, f"{where} level demotes its catalog default")
        if level == expected_default:
            if entry["level_reason"] is not None:
                raise _state_error(path, f"{where} default level cannot have override reason")
        elif not _valid_text(entry["level_reason"], 500):
            raise _state_error(path, f"{where} upward override requires level_reason")
        if level == 3:
            if entry["l3_trigger"] not in L3_TRIGGERS:
                raise _state_error(path, f"{where} L3 requires an exact trigger")
            if expected_default == 3 and entry["l3_trigger"] != expected_trigger:
                raise _state_error(path, f"{where} L3 alias trigger mismatch")
        elif entry["l3_trigger"] is not None:
            raise _state_error(path, f"{where} non-L3 entry has l3_trigger")
        if not isinstance(entry["blocking"], bool) or entry["blocking"] != (level == 3):
            raise _state_error(path, f"{where} blocking must equal (level == 3)")
        if entry["risk"] not in RISKS:
            raise _state_error(path, f"{where} risk is invalid")
        for field, limit in (("title", 200), ("requested_by", 100)):
            if not _valid_text(entry[field], limit):
                raise _state_error(path, f"{where} {field} is invalid")
        for field, limit in (("paused_context", 500), ("resume_hint", 500)):
            if entry[field] is not None and not _valid_text(entry[field], limit):
                raise _state_error(path, f"{where} {field} is invalid")
        if (entry["paused_context"] is None) != (entry["resume_hint"] is None):
            raise _state_error(path, f"{where} interruption context is incomplete")
        if (not isinstance(entry["evidence"], list)
                or len(entry["evidence"]) > MAX_EVIDENCE_ITEMS
                or any(not _valid_text(item, 1000) for item in entry["evidence"])):
            raise _state_error(path, f"{where} evidence is invalid")
        if (not isinstance(entry["source"], dict)
                or set(entry["source"]) != {"kind", "ref"}):
            raise _state_error(path, f"{where} source shape is invalid")
        try:
            validate_source_ref(entry["source"]["kind"], entry["source"]["ref"])
        except ValueError as exc:
            raise _state_error(path, f"{where} {exc}") from None
        if level >= 2 and not entry["source"]["ref"]:
            raise _state_error(path, f"{where} review entries require a source-ref")
        if entry["status"] not in STATUSES:
            raise _state_error(path, f"{where} status is invalid")
        if entry["decision_note"] is not None and not _valid_text(
                entry["decision_note"], 2000, empty=True):
            raise _state_error(path, f"{where} decision_note is invalid")
        if entry["status"] == "pending":
            if entry["decided_at"] is not None:
                raise _state_error(path, f"{where} pending item has decided_at")
        elif not _valid_timestamp(entry["decided_at"]):
            raise _state_error(path, f"{where} decided item lacks decided_at")
        if entry["decided_at"] and _parse_timestamp(entry["decided_at"]) < _parse_timestamp(entry["created_at"]):
            raise _state_error(path, f"{where} decided_at predates creation")
        if (not allow_dirty and entry["decided_at"] and state["updated_at"]
                and _parse_timestamp(entry["decided_at"])
                > _parse_timestamp(state["updated_at"])):
            raise _state_error(path, f"{where} decided_at is newer than state")
        if "escalated_at" in entry:
            if (not _valid_timestamp(entry["escalated_at"])
                    or level != 3 or not entry["blocking"]
                    or _parse_timestamp(entry["escalated_at"])
                    < _parse_timestamp(entry["created_at"])):
                raise _state_error(path, f"{where} escalation fields are inconsistent")
            if (not allow_dirty and state["updated_at"]
                    and _parse_timestamp(entry["escalated_at"])
                    > _parse_timestamp(state["updated_at"])):
                raise _state_error(path, f"{where} escalated_at is newer than state")

        if level in (0, 1):
            if (not isinstance(entry["policy"], str)
                    or not POLICY_RE.fullmatch(entry["policy"])
                    or entry["status"] != "approved" or not entry["evidence"]):
                raise _state_error(path, f"{where} self-approval proof is incomplete")
            _validate_policy_provenance(entry["policy_provenance"], entry,
                                        path, where, migrated)
            verified = entry["policy_provenance"].get("verified") is True
            if verified and not _valid_text(entry["rollback"], 1000):
                raise _state_error(path, f"{where} verified policy requires rollback proof")
            if not verified and entry["rollback"] is not None:
                raise _state_error(path, f"{where} legacy policy rollback must be null")
        elif (entry["policy"] is not None or entry["policy_provenance"] is not None
              or entry["rollback"] is not None):
            raise _state_error(path, f"{where} policy fields are forbidden at L2/L3")

        gate_state, gate_action = entry["gate_state"], entry["gate_action"]
        if gate_state not in GATE_STATES:
            raise _state_error(path, f"{where} gate_state is invalid")
        if entry["status"] == "pending" and (
                gate_state != "not_requested" or gate_action is not None):
            raise _state_error(path, f"{where} pending gate state is inconsistent")
        if entry["status"] == "rejected" and (
                gate_state != "not_applicable" or gate_action is not None):
            raise _state_error(path, f"{where} rejected gate state is inconsistent")
        if entry["status"] == "approved":
            if level in (0, 1):
                if gate_state != "not_applicable" or gate_action is not None:
                    raise _state_error(path, f"{where} automatic gate state is inconsistent")
            elif gate_state == "legacy_unknown":
                if not migrated or gate_action is not None:
                    raise _state_error(path, f"{where} invalid legacy gate state")
            elif gate_state == "awaiting_execution":
                try:
                    _validate_gate_action(gate_action, entry["source"]["kind"],
                                          entry["source"]["ref"])
                except ValueError as exc:
                    raise _state_error(path, f"{where} {exc}") from None
            else:
                raise _state_error(path, f"{where} approved gate state is inconsistent")
    return state


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock_path = Path(f"{self.path}.lock")

    @contextlib.contextmanager
    def lock(self, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        locked = False
        try:
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
                os.fsync(fd)
            while True:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    elif os.name == "posix":
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        raise OSError(
                            f"unsupported advisory-lock platform: {os.name}")
                    locked = True
                    break
                except OSError as exc:
                    retryable = exc.errno in (errno.EACCES, errno.EAGAIN,
                                               errno.EDEADLK)
                    if not retryable:
                        raise
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"inbox is locked: {self.lock_path}") from exc
                    time.sleep(0.05)
            yield
        finally:
            if locked:
                with contextlib.suppress(OSError):
                    os.lseek(fd, 0, os.SEEK_SET)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    elif os.name == "posix":
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def load_raw(self) -> dict:
        if not self.path.exists():
            return blank()
        size = self.path.stat().st_size
        if size > MAX_STATE_BYTES:
            raise ValueError(
                f"inbox state exceeds {MAX_STATE_BYTES} bytes: {self.path}")
        return json.loads(self.path.read_text(encoding="utf-8"))

    def load(self) -> dict:
        return validate_state(self.load_raw(), self.path)

    def save(self, state: dict) -> None:
        state["revision"] += 1
        state["updated_at"] = now()
        validate_state(state, self.path)
        fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp",
                                   dir=self.path.parent)
        replaced = False
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as h:
                json.dump(state, h, indent=2, ensure_ascii=False, sort_keys=True)
                h.write("\n")
                h.flush()
                os.fsync(h.fileno())
            for attempt in range(5):
                try:
                    os.replace(tmp, self.path)
                    replaced = True
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05)
            if os.name == "posix":
                try:
                    dir_fd = os.open(self.path.parent, os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError as exc:
                    raise CommittedStateError(
                        "state replaced but directory durability check failed") from exc
        except OSError as exc:
            if replaced and not isinstance(exc, CommittedStateError):
                raise CommittedStateError(
                    "state replaced but a post-commit operation failed") from exc
            raise
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)

    def mutate(self, op):
        with self.lock():
            state = self.load()
            result = op(state)
            validate_state(state, self.path, allow_dirty=True)
            self.save(state)
            return result


def _csv_field(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items or len(items) != len(set(items)):
        raise ValueError("comma-list must be non-empty and unique")
    return items


def load_policy_registry(path: Path) -> dict:
    if not path.exists() or path.stat().st_size > 1024 * 1024:
        raise ValueError(f"standing-policy registry missing or too large: {path}")
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    version_match = re.search(r"^version:\s*(\d+\.\d+\.\d+)\s*$", text, re.M)
    if not version_match:
        raise ValueError("standing-policy registry lacks a semantic version")
    stripped = re.sub(r"```.*?```", "", text, flags=re.S)
    records, malformed = {}, {}
    required = {
        "status", "level", "event_class", "categories", "source_kinds",
        "risks", "evidence_required", "rollback", "approved_by", "approved_at",
    }
    for match in re.finditer(
            r"^## policy: ([\w-]+)\s*$(.*?)(?=^## |\Z)", stripped, re.M | re.S):
        name, body = match.group(1), match.group(2)
        fields, current = {}, None
        try:
            for line in body.splitlines():
                if not line.strip():
                    continue
                if line[:1].isspace():
                    if current is None:
                        raise ValueError("orphan continuation line")
                    fields[current] = f"{fields[current]} {line.strip()}"
                    continue
                field_match = re.fullmatch(r"([a-z_]+):\s*(.*)", line)
                if not field_match:
                    continue  # Human prose remains permitted inside a section.
                key, value = field_match.groups()
                if key in fields:
                    raise ValueError(f"duplicate field {key}")
                fields[key], current = value.strip(), key
            if fields.get("status") not in ("draft", "approved"):
                raise ValueError("status must be draft or approved")
            if fields["status"] == "draft":
                records[name] = {"name": name, "status": "draft"}
                continue
            missing = required - set(fields)
            if missing:
                raise ValueError(f"missing fields {sorted(missing)}")
            level = int(fields["level"])
            if level not in (0, 1):
                raise ValueError("approved self-decision policy level must be 0 or 1")
            event_class = fields["event_class"]
            if (event_class not in EVENT_CATALOG
                    or EVENT_CATALOG[event_class][0] > level):
                raise ValueError("policy level cannot demote its event_class default")
            categories = _csv_field(fields["categories"])
            if any(event_rule(category)[0] != event_class for category in categories):
                raise ValueError("category does not map to policy event_class")
            source_kinds = _csv_field(fields["source_kinds"])
            if any(kind not in SOURCE_KINDS for kind in source_kinds):
                raise ValueError("unknown source kind")
            risks = _csv_field(fields["risks"])
            if any(risk not in RISKS for risk in risks):
                raise ValueError("unknown risk")
            evidence_required = fields["evidence_required"] == "true"
            if fields["evidence_required"] not in ("true", "false"):
                raise ValueError("evidence_required must be true or false")
            if (fields["approved_by"] != "toni"
                    or not _valid_date(fields["approved_at"])):
                raise ValueError("approved policy requires Toni and an approval date")
            if not _valid_text(fields["rollback"], 1000):
                raise ValueError("approved policy requires a rollback specification")
            records[name] = {
                "name": name, "status": "approved", "level": level,
                "event_class": event_class, "categories": categories,
                "source_kinds": source_kinds, "risks": risks,
                "evidence_required": evidence_required,
                "rollback": fields["rollback"],
                "approved_by": fields["approved_by"],
                "approved_at": fields["approved_at"],
            }
        except (KeyError, TypeError, ValueError) as exc:
            malformed[name] = str(exc)
    return {
        "version": version_match.group(1),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "raw": raw, "records": records, "malformed": malformed,
    }


def authorize_policy(registry: dict, name: str, *, level: int, category: str,
                     event_class: str, source_kind: str, risk: str,
                     evidence: list[str], rollback: str | None) -> dict:
    if name in registry["malformed"]:
        raise ValueError(
            f"policy {name!r} is malformed: {registry['malformed'][name]}")
    record = registry["records"].get(name)
    if not record or record.get("status") != "approved":
        raise ValueError(f"policy {name!r} is not an approved standing policy")
    if (record["level"] != level or record["event_class"] != event_class
            or category not in record["categories"]
            or source_kind not in record["source_kinds"]
            or risk not in record["risks"]):
        raise ValueError(f"policy {name!r} does not authorize this act")
    if record["evidence_required"] and not evidence:
        raise ValueError(f"policy {name!r} requires evidence")
    if not rollback or not _valid_text(rollback, 1000):
        raise ValueError(f"policy {name!r} requires concrete rollback proof")
    provenance = {
        "name": name, "verified": True,
        "registry": "docs/canon/STANDING_POLICIES.md",
        "registry_version": registry["version"],
        "registry_sha256": registry["sha256"],
        "policy_level": level, "event_class": event_class,
        "categories": list(record["categories"]),
        "source_kinds": list(record["source_kinds"]),
        "risks": list(record["risks"]),
        "evidence_required": record["evidence_required"],
        "rollback": record["rollback"],
        "approved_by": record["approved_by"],
        "approved_at": record["approved_at"],
    }
    provenance["provenance_sha256"] = _policy_provenance_digest(provenance)
    return provenance


def entry_by_id(state: dict, prefix: str) -> dict:
    if len(prefix) < 4:
        raise ValueError("id prefix must be at least 4 characters")
    hits = [e for e in state["entries"] if e["id"].startswith(prefix)]
    if not hits:
        raise KeyError(f"no entry matches {prefix}")
    if len(hits) > 1:
        raise KeyError(f"ambiguous id prefix {prefix}")
    return hits[0]


def _build_entry(args, policies_path: Path) -> tuple[dict, dict | None]:
    category = args.category
    if not CATEGORY_RE.fullmatch(category):
        raise ValueError("category must be an exact slug: [a-z0-9-]{1,40}")
    event_class, default_level, catalog_trigger = event_rule(category)
    level = default_level if args.level is None else args.level
    if level < default_level:
        raise ValueError(
            f"category {category} defaults to L{default_level} and cannot be demoted")
    if level == default_level:
        if args.level_reason:
            raise ValueError("--level-reason is only valid for an upward override")
        level_reason = None
    else:
        if not args.level_reason or not _valid_text(args.level_reason, 500):
            raise ValueError("upward level override requires --level-reason")
        level_reason = args.level_reason
    if level == 3:
        if default_level == 3:
            if args.l3_trigger and args.l3_trigger != catalog_trigger:
                raise ValueError("cataloged L3 category has an immutable trigger")
            l3_trigger = catalog_trigger
        else:
            if args.l3_trigger not in L3_TRIGGERS:
                raise ValueError("promotion to L3 requires an exact --l3-trigger")
            l3_trigger = args.l3_trigger
    else:
        if args.l3_trigger:
            raise ValueError("--l3-trigger is only valid at L3")
        l3_trigger = None
    source_ref = args.source_ref or ""
    if len(source_ref) > 240 or printable(source_ref, 240) != source_ref:
        raise ValueError("source-ref must be <=240 printable characters without normalization")
    validate_source_ref(args.source_kind, source_ref)
    if level >= 2 and not source_ref:
        raise ValueError("L2/L3 entries require a concrete --source-ref")
    if level >= 2 and args.policy:
        raise ValueError("--policy is only meaningful for self-approval "
                         "levels 0/1; reject to keep the audit trail honest")
    evidence = [item.strip() for item in (args.evidence or "").split(",")
                if item.strip()]
    if (len(evidence) > MAX_EVIDENCE_ITEMS
            or any(not _valid_text(item, 1000) for item in evidence)):
        raise ValueError("evidence items must be printable and <=1000 characters")
    title, requested_by = args.title, args.requested_by
    if not _valid_text(title, 200):
        raise ValueError("title must be one printable line of <=200 characters")
    if not _valid_text(requested_by, 100):
        raise ValueError("requested-by must be printable and <=100 characters")
    if level in (0, 1):
        if not args.policy:
            raise ValueError("level 0/1 requires --policy (self-decision rule)")
    elif args.rollback:
        raise ValueError("--rollback is only valid for policy self-approval")
    paused_context = getattr(args, "paused_context", None)
    resume_hint = getattr(args, "resume_hint", None)
    if (paused_context is None) != (resume_hint is None):
        raise ValueError("--paused-context and --resume-hint must be supplied together")
    if paused_context is not None:
        if (not _valid_text(paused_context, 500)
                or not _valid_text(resume_hint, 500)):
            raise ValueError("interruption context fields must be printable and <=500 characters")
    if level == 3 and (paused_context is None or resume_hint is None):
        raise ValueError("L3 requires --paused-context and --resume-hint")

    provenance = None
    registry = None
    if level in (0, 1):
        registry = load_policy_registry(policies_path)
        provenance = authorize_policy(
            registry, args.policy, level=level, category=category,
            event_class=event_class, source_kind=args.source_kind,
            risk=args.risk, evidence=evidence, rollback=args.rollback)
    created = now()
    entry = {
        "id": str(uuid.uuid4()), "created_at": created,
        "event_class": event_class, "default_level": default_level,
        "level": level, "level_reason": level_reason,
        "l3_trigger": l3_trigger, "category": category,
        "blocking": level == 3, "risk": args.risk, "title": title,
        "source": {"kind": args.source_kind, "ref": source_ref},
        "evidence": evidence, "requested_by": requested_by,
        "status": "pending", "decided_at": None, "decision_note": None,
        "policy": args.policy, "policy_provenance": provenance,
        "rollback": args.rollback if level in (0, 1) else None,
        "paused_context": paused_context, "resume_hint": resume_hint,
        "gate_state": "not_requested", "gate_action": None,
    }
    if level in (0, 1):
        entry["status"] = "approved"
        entry["decided_at"] = created
        entry["decision_note"] = f"self-approved under policy {args.policy}"
        entry["gate_state"] = "not_applicable"
    return entry, registry


def _recheck_policy_registry(registry: dict | None, policies_path: Path) -> None:
    if registry is None:
        return
    current_digest = hashlib.sha256(policies_path.read_bytes()).hexdigest()
    if current_digest != registry["sha256"]:
        raise ValueError("standing-policy registry changed during authorization")


def cmd_add(store: Store, args, policies_path: Path) -> dict:
    with store.lock():
        state = store.load()
        entry, registry = _build_entry(args, policies_path)
        state["entries"].append(entry)
        _recheck_policy_registry(registry, policies_path)
        validate_state(state, store.path, allow_dirty=True)
        store.save(state)
        return entry


FEED_ROUTES = {
    ("dhef", "gate-ready"): ("dhef-gate-ready", "dhef"),
    ("school", "finalize-ready"): ("xp-finalization", "school"),
    ("adr", "proposed"): ("architectural-decision", "adr"),
    ("git", "awaiting-merge"): ("publication", "git"),
    ("skill", "lifecycle-transition"): ("completed-skill", "skill"),
    ("policy", "executed"): ("automatic-approval", "policy"),
}


def _read_feed_envelope() -> dict:
    if sys.stdin.isatty():
        raise ValueError("feed requires one JSON object on stdin")
    raw = sys.stdin.buffer.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        raise ValueError("feed envelope exceeds 64 KiB")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid feed JSON: {exc}") from None
    required = {"v", "provider", "event", "id", "title", "source_ref"}
    optional = {"evidence", "risk", "requested_by", "policy", "rollback",
                "paused_context", "resume_hint"}
    if not isinstance(payload, dict) or set(payload) - required - optional or required - set(payload):
        raise ValueError("feed envelope fields are invalid")
    if payload["v"] != 1:
        raise ValueError("unsupported feed envelope version")
    for field, limit, pattern in (
            ("provider", 20, r"[a-z][a-z0-9-]*"),
            ("event", 40, r"[a-z][a-z0-9-]*"),
            ("id", 160, r"[A-Za-z0-9][A-Za-z0-9._:/-]*")):
        value = payload[field]
        if (not isinstance(value, str) or len(value) > limit
                or not re.fullmatch(pattern, value)):
            raise ValueError(f"feed {field} is invalid")
    return payload


def cmd_feed(store: Store, policies_path: Path) -> dict:
    payload = _read_feed_envelope()
    route = FEED_ROUTES.get((payload["provider"], payload["event"]))
    if route is None:
        raise ValueError("unsupported feed provider/event pair")
    category, source_kind = route
    evidence = payload.get("evidence", [])
    if (not isinstance(evidence, list)
            or any(not isinstance(item, str) or "," in item for item in evidence)):
        raise ValueError("feed evidence must be a JSON string array without commas")
    args = argparse.Namespace(
        title=payload["title"], category=category, level=None,
        level_reason=None, l3_trigger=None,
        risk=payload.get("risk", "low"), source_kind=source_kind,
        source_ref=payload["source_ref"], evidence=",".join(evidence),
        requested_by=payload.get("requested_by", f"{source_kind}-feed"),
        policy=payload.get("policy"), rollback=payload.get("rollback"),
        paused_context=payload.get("paused_context"),
        resume_hint=payload.get("resume_hint"))
    canonical = json.dumps({
        "provider": payload["provider"], "event": payload["event"],
        "id": payload["id"]}, sort_keys=True, separators=(",", ":"))
    key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with store.lock():
        state = store.load()
        prior = next((receipt for receipt in state["feed_receipts"]
                      if receipt["key"] == key), None)
        if prior is not None:
            entry = next((item for item in state["entries"]
                          if item["id"] == prior["entry_id"]), None)
            return {"entry": entry, "receipt": prior, "idempotent": True}
        entry, registry = _build_entry(args, policies_path)
        receipt = {"key": key, "entry_id": entry["id"], "at": entry["created_at"]}
        state["entries"].append(entry)
        state["feed_receipts"].append(receipt)
        _recheck_policy_registry(registry, policies_path)
        validate_state(state, store.path, allow_dirty=True)
        store.save(state)
        return {"entry": entry, "receipt": receipt, "idempotent": False}


def selected(state: dict, status: str):
    if status == "all":
        return list(state["entries"])
    return [e for e in state["entries"] if e["status"] == status]


def cmd_list(store: Store, args) -> str:
    state = store.load()
    rows = selected(state, args.status)
    if not args.group:
        return json.dumps(rows, indent=2, ensure_ascii=False)
    pending = [e for e in rows if e["status"] == "pending"]
    lines = [f"Pending Reviews ({len(pending)})", ""]
    blocking = sorted((e for e in pending if e["blocking"]),
                      key=lambda e: (not bool(e.get("escalated_at")),
                                     e["created_at"], e["id"]))
    for e in blocking:
        flag = "ESCALATED" if e.get("escalated_at") else "BLOCKING"
        lines.append(f"! {flag} - {e['title']} [{e['category']}] ({e['id'][:8]})")
        if e.get("paused_context"):
            lines.append(f"  Paused: {e['paused_context']}")
            lines.append(f"  Resume: {e['resume_hint']}")
    if blocking:
        lines.append("")
    by_cat = {}
    for e in pending:
        if not e["blocking"]:
            by_cat.setdefault(e["category"], []).append(e)
    for cat in sorted(by_cat):
        lines.append(f"• {len(by_cat[cat]):>2} {cat.replace('-', ' ')}")
    audited = [e for e in state["entries"]
               if e["status"] == "approved" and e.get("policy")
               and e["level"] in (0, 1)
               and e.get("policy_provenance", {}).get("verified") is True]
    if audited:
        lines.append(f"• {len(audited):>2} automatic approvals "
                     f"(L1/L0 audit trail; list --status approved)")
    if len(lines) == 2:
        lines.append("•  0 items waiting")
    return "\n".join(lines)


def _reading_time(lines: list[str]) -> str:
    words = len(" ".join(lines).split())
    seconds = max(15, int(math.ceil(words / 200 * 60 / 15)) * 15)
    return f"{seconds} seconds" if seconds < 90 else f"{math.ceil(seconds / 60)} minutes"


def _render_brief(state: dict, daypart: str, mode: str,
                  since_at: str, through_at: str, brief_id: str) -> str:
    since_dt, through_dt = _parse_timestamp(since_at), _parse_timestamp(through_at)
    done = [e for e in state["entries"] if e.get("decided_at")
            and since_dt < _parse_timestamp(e["decided_at"]) <= through_dt]
    pending = [e for e in state["entries"] if e["status"] == "pending"]
    blocking = sorted((e for e in pending if e["blocking"]),
                      key=lambda e: (e["created_at"], e["id"]))
    waiting = sorted((e for e in pending if e["level"] == 2),
                     key=lambda e: (e["created_at"], e["id"]))
    stale_cut = through_dt.timestamp() - 3 * 86400
    longrun = [e for e in pending
               if _parse_timestamp(e["created_at"]).timestamp() < stale_cut]
    completed = sum(1 for e in done if e["event_class"] == "completed-task")
    promoted = sum(1 for e in done if e["event_class"] in
                   ("preapproved-promotion", "completed-skill"))

    if mode == "minimum":
        lines = ["I'll keep this brief.",
                 f"{len(blocking) + len(waiting)} items need you; the rest can wait until tomorrow."]
        for e in blocking[:2]:
            lines.append(f"• ⚠ BLOCKING: {e['title']} ({e['id'][:8]})")
    else:
        heading = "Today's highlights:" if mode == "highlights" else "Today's summary:"
        lines = [f"Good {daypart}.", heading]
        for e in blocking:
            lines.append(f"• ⚠ BLOCKING: {e['title']} ({e['id'][:8]})")
            if e.get("paused_context"):
                lines.append(f"  Paused: {e['paused_context']}")
                lines.append(f"  Resume: {e['resume_hint']}")
        lines.append(f"• ✅ {completed} tasks completed")
        lines.append(f"• ✅ {promoted} skills promoted")
        lines.append(f"• ⚠ {len(waiting)} review questions waiting")
        lines.append(f"• ⏳ {len(longrun)} long-running items")
        limit = 3 if mode == "highlights" else (20 if mode == "detailed" else 6)
        for e in waiting[:limit]:
            lines.append(f"  ↳ {e['title']} ({e['id'][:8]})")
        if len(waiting) > limit:
            lines.append(f"  ↳ +{len(waiting) - limit} more in inboxctl list --group")
        if mode == "detailed":
            by_cat = {}
            for e in done:
                by_cat[e["category"]] = by_cat.get(e["category"], 0) + 1
            for category in sorted(by_cat):
                lines.append(f"  ↳ {by_cat[category]} {category.replace('-', ' ')} decided")
        elif mode == "standard":
            lines.append("Would you like more technical detail?")
    lines.append(f"Brief ID: {brief_id}")
    lines.append(f"Estimated reading time: {_reading_time(lines)}.")
    return "\n".join(lines)


def cmd_brief(store: Store, args) -> str | dict:
    with store.lock():
        state = store.load()
        if args.ack:
            brief = state["pending_brief"]
            if brief is None:
                raise ValueError("no pending brief to acknowledge")
            if args.ack != brief["id"]:
                raise ValueError("brief acknowledgement id does not match pending delivery")
            state["last_brief_at"] = brief["through_at"]
            state["pending_brief"] = None
            validate_state(state, store.path, allow_dirty=True)
            store.save(state)
            return {"ok": True, "acknowledged": args.ack,
                    "last_brief_at": state["last_brief_at"]}
        if state["pending_brief"] is not None:
            brief = state["pending_brief"]
            if args.mode != brief["mode"]:
                raise ValueError(
                    f"pending brief uses mode {brief['mode']}; acknowledge it before changing mode")
            return brief["content"]
        since_at = state["last_brief_at"] or "1970-01-01T00:00:00Z"
        through_at = now()
        brief_id = str(uuid.uuid4())
        content = _render_brief(state, args.daypart, args.mode,
                                since_at, through_at, brief_id)
        brief = {
            "id": brief_id, "created_at": now(),
            "since_at": since_at, "through_at": through_at,
            "mode": args.mode, "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        state["pending_brief"] = brief
        validate_state(state, store.path, allow_dirty=True)
        store.save(state)
        return content


def cmd_decide(store: Store, args, status: str) -> dict:
    if args.note:
        note = printable(args.note, 2000)
    elif sys.stdin.isatty():
        note = ""
    else:
        raw_note = sys.stdin.read(2001)
        if len(raw_note) > 2000:
            raise ValueError("stdin decision note exceeds 2000 characters")
        note = printable(raw_note, 2000)
    with store.lock():
        state = store.load()
        e = entry_by_id(state, args.id)
        if status == "approved" and e["status"] == "approved":
            if e.get("gate_state") == "awaiting_execution" and e.get("gate_action"):
                return {
                    "entry": e,
                    "gate_action": e["gate_action"],
                    "gate_action_note": (
                        "print-only: the inbox records the decision; "
                        "the source system remains authoritative"),
                    "idempotent": True,
                }
            raise ValueError(
                "entry already approved without a recoverable stored action")
        if e["status"] != "pending":
            raise ValueError(f"entry already {e['status']}")
        if status == "escalate":
            # Escalation raises, never hides: pin at interrupt, stay pending.
            if args.l3_trigger not in L3_TRIGGERS:
                raise ValueError("escalation requires an exact --l3-trigger")
            if e["default_level"] == 3 and args.l3_trigger != e["l3_trigger"]:
                raise ValueError("cataloged L3 trigger is immutable")
            e["level"] = 3
            e["blocking"] = True
            e["l3_trigger"] = args.l3_trigger
            if e["default_level"] < 3:
                e["level_reason"] = note or f"escalated: {args.l3_trigger}"
            paused = args.paused_context or e.get("paused_context")
            resume = args.resume_hint or e.get("resume_hint")
            if not paused or not resume:
                raise ValueError(
                    "escalation requires --paused-context and --resume-hint")
            if (not _valid_text(paused, 500) or not _valid_text(resume, 500)):
                raise ValueError("interruption context fields are invalid")
            e["paused_context"], e["resume_hint"] = paused, resume
            e["escalated_at"] = now()
            e["decision_note"] = note or e.get("decision_note")
            validate_state(state, store.path, allow_dirty=True)
            store.save(state)
            return {"entry": e}
        if status == "rejected":
            e["status"] = "rejected"
            e["decided_at"] = now()
            e["decision_note"] = note or None
            e["gate_state"] = "not_applicable"
            e["gate_action"] = None
            validate_state(state, store.path, allow_dirty=True)
            store.save(state)
            return {"entry": e}

        # Preflight the exact normalized action before changing decision state.
        action = build_gate_action(e["source"]["kind"], e["source"]["ref"])
        e["status"] = "approved"
        e["decided_at"] = now()
        e["decision_note"] = note or None
        e["gate_state"] = "awaiting_execution"
        e["gate_action"] = action
        validate_state(state, store.path, allow_dirty=True)
        store.save(state)
        return {
            "entry": e,
            "gate_action": action,
            "gate_action_note": (
                "print-only: the inbox records the decision; "
                "the source system remains authoritative"),
            "idempotent": False,
        }


def cmd_prune(store: Store, args) -> dict:
    if args.days < 1:
        raise ValueError("--days must be >= 1 (the audit trail is not a typo away)")
    cutoff = time.time() - args.days * 86400

    def op(state):
        keep, dropped = [], 0
        for e in state["entries"]:
            ts = e.get("decided_at") or e["created_at"]
            t = _parse_timestamp(ts).timestamp()
            if e["status"] == "pending" or t >= cutoff:
                keep.append(e)
            else:
                dropped += 1
        state["entries"] = keep
        return {"dropped": dropped, "kept": len(keep)}

    return store.mutate(op)


def migrate_v1_state(state: dict, path: Path) -> dict:
    validate_state_v1(state, path)
    migrated_at = now()
    entries = []
    for old in state["entries"]:
        entry = copy.deepcopy(old)
        event_class, default_level, catalog_trigger = event_rule(entry["category"])
        if entry["level"] < default_level:
            raise ValueError(
                f"cannot migrate demoted category {entry['category']!r}")
        if entry["level"] == default_level:
            level_reason = None
        else:
            level_reason = "migrated legacy upward override"
        if entry["level"] == 3:
            if default_level == 3:
                l3_trigger = catalog_trigger
            elif entry.get("escalated_at"):
                l3_trigger = "human-decision-required"
            else:
                raise ValueError(
                    f"cannot infer L3 trigger for legacy entry {entry['id']}")
        else:
            l3_trigger = None
        entry.update({
            "event_class": event_class,
            "default_level": default_level,
            "level_reason": level_reason,
            "l3_trigger": l3_trigger,
            "policy_provenance": None,
            "rollback": None,
            "paused_context": None,
            "resume_hint": None,
        })
        if entry["level"] in (0, 1):
            entry["policy_provenance"] = {
                "name": entry["policy"], "verified": False,
                "reason": "migrated-from-schema-v1",
            }
        if "gate_state" not in entry:
            if entry["status"] == "pending":
                entry["gate_state"], entry["gate_action"] = "not_requested", None
            elif entry["status"] == "rejected" or entry["level"] in (0, 1):
                entry["gate_state"], entry["gate_action"] = "not_applicable", None
            else:
                entry["gate_state"], entry["gate_action"] = "legacy_unknown", None
        elif (entry["status"] == "approved" and entry["level"] >= 2
              and not entry.get("gate_action")):
            entry["gate_state"] = "legacy_unknown"
        if entry["level"] >= 2 and not entry["source"]["ref"]:
            raise ValueError(
                f"cannot migrate review entry {entry['id']} without source-ref")
        entries.append(entry)
    migrated = {
        "schema_version": SCHEMA_VERSION,
        "catalog_version": EVENT_CATALOG_VERSION,
        "revision": state["revision"],
        "updated_at": migrated_at,
        "last_brief_at": state["last_brief_at"],
        "pending_brief": None,
        "feed_receipts": [],
        "migration": {"from": 1, "at": migrated_at, "phase2_at": migrated_at},
        "entries": entries,
    }
    return validate_state(migrated, path)


def migrate_v2_state(state: dict, path: Path) -> dict:
    if not isinstance(state, dict) or set(state) != V2_TOP_LEVEL_FIELDS:
        raise _state_error(path, "schema-2 top-level shape is invalid")
    migrated_at = now()
    migrated = copy.deepcopy(state)
    for index, entry in enumerate(migrated.get("entries", [])):
        if not isinstance(entry, dict) or set(entry) - V2_ENTRY_FIELDS:
            raise _state_error(path, f"schema-2 entry {index} shape is invalid")
        entry["paused_context"] = None
        entry["resume_hint"] = None
    migrated["schema_version"] = SCHEMA_VERSION
    migrated["updated_at"] = migrated_at
    migrated["pending_brief"] = None
    migrated["feed_receipts"] = []
    if migrated["migration"] is None:
        migrated["migration"] = {"from": 2, "at": migrated_at}
    elif (isinstance(migrated["migration"], dict)
          and set(migrated["migration"]) == {"from", "at"}
          and migrated["migration"].get("from") == 1):
        migrated["migration"]["phase2_at"] = migrated_at
    else:
        raise _state_error(path, "schema-2 migration record is invalid")
    return validate_state(migrated, path)


def _write_backup(path: Path, data: bytes, from_schema: int) -> Path:
    backup = Path(f"{path}.v{from_schema}.bak")
    try:
        fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if backup.read_bytes() != data:
            raise ValueError(f"migration backup already exists with different bytes: {backup}")
        return backup
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return backup


def cmd_migrate(store: Store, args) -> dict:
    with store.lock():
        raw = store.load_raw()
        if raw.get("schema_version") == SCHEMA_VERSION:
            validate_state(raw, store.path)
            return {"ok": True, "already_current": True,
                    "schema_version": SCHEMA_VERSION}
        from_schema = raw.get("schema_version")
        if from_schema == 1:
            migrated = migrate_v1_state(raw, store.path)
        elif from_schema == 2:
            migrated = migrate_v2_state(raw, store.path)
        else:
            raise ValueError("only schema 1 or 2 can migrate to schema 3")
        result = {
            "ok": True, "dry_run": not args.apply,
            "from_schema": from_schema, "to_schema": SCHEMA_VERSION,
            "entries": len(migrated["entries"]),
            "next_revision": migrated["revision"] + 1,
        }
        if not args.apply:
            return result
        original = store.path.read_bytes()
        backup = _write_backup(store.path, original, from_schema)
        store.save(migrated)
        result.update({"dry_run": False, "backup": str(backup),
                       "revision": migrated["revision"]})
        return result


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _reject_link_components(path: Path, root: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError(f"path escapes its authority root: {path}") from None
    current = root
    if current.exists() and _is_link(current):
        raise ValueError(f"authority root cannot be a link: {root}")
    for part in relative.parts:
        current = current / part
        if current.exists() and _is_link(current):
            raise ValueError(f"authority path cannot contain a link: {current}")


def resolve_authority_paths(args) -> tuple[Path, Path]:
    requested_state = Path(os.path.abspath(Path(args.state).expanduser()))
    requested_policies = Path(os.path.abspath(Path(args.policies).expanduser()))
    test_root_raw = os.environ.get("NERO_INBOX_TEST_ROOT")
    if test_root_raw:
        test_root = Path(test_root_raw).expanduser().resolve()
        if (test_root == ROOT or ROOT in test_root.parents
                or test_root in ROOT.parents):
            raise ValueError("test authority root must be outside the repository")
        _reject_link_components(requested_state, test_root)
        _reject_link_components(requested_policies, test_root)
        _reject_link_components(Path(f"{requested_state}.lock"), test_root)
        state = requested_state.resolve()
        policies = requested_policies.resolve()
        if (state == ROOT or ROOT in state.parents
                or policies == ROOT or ROOT in policies.parents):
            raise ValueError("test authority targets must be outside the repository")
        _reject_link_components(state, test_root)
        _reject_link_components(policies, test_root)
        if state.suffix != ".json" or policies.suffix != ".md":
            raise ValueError("test state/policy paths require .json/.md suffixes")
        return state, policies
    default_state = Path(os.path.abspath(DEFAULT_STATE))
    default_policies = Path(os.path.abspath(DEFAULT_POLICIES))
    if requested_state != default_state or requested_policies != default_policies:
        raise ValueError(
            "production authority is fixed to data/review-inbox.json and "
            "docs/canon/STANDING_POLICIES.md")
    _reject_link_components(requested_state, ROOT.resolve())
    _reject_link_components(requested_policies, ROOT.resolve())
    _reject_link_components(Path(f"{requested_state}.lock"), ROOT.resolve())
    state, policies = requested_state.resolve(), requested_policies.resolve()
    _reject_link_components(state, ROOT.resolve())
    _reject_link_components(policies, ROOT.resolve())
    return state, policies


def cmd_familiar(store, args):
    state = store.load()
    pending = [e for e in state['entries'] if e['status'] == 'pending']
    blocking = [e for e in pending if e['blocking']]
    if blocking:
        line = 'review|' + str(len(blocking)) + ' blocking - ' + printable(blocking[0]['title'], 60)
    elif pending:
        line = 'waiting|' + str(len(pending)) + ' in queue, none blocking'
    else:
        line = 'idle'
    out = Path(args.familiar_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(line + chr(10), encoding='utf-8')
    return {'familiar_command': line, 'written_to': str(out)}


def build_parser() -> argparse.ArgumentParser:
    p = JsonArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state", default=str(DEFAULT_STATE),
                   help="canonical state path; override only under NERO_INBOX_TEST_ROOT")
    p.add_argument("--policies", default=str(DEFAULT_POLICIES),
                   help="canonical policy path; override only under NERO_INBOX_TEST_ROOT")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="file a cataloged event at its derived level")
    a.add_argument("--title", required=True, help="one line, printable")
    a.add_argument("--category", required=True,
                   help="canonical event category or sanctioned legacy alias")
    a.add_argument("--level", type=int, choices=(0, 1, 2, 3),
                   help="optional upward override; default derives from category")
    a.add_argument("--level-reason", help="required reason for an upward override")
    a.add_argument("--l3-trigger", choices=L3_TRIGGERS,
                   help="required when a non-L3 event is promoted to L3")
    a.add_argument("--risk", choices=("low", "medium", "high"), default="low")
    a.add_argument("--source-kind", required=True, choices=SOURCE_KINDS)
    a.add_argument("--source-ref", default="",
                   help="gate reference (strictly validated for every source kind)")
    a.add_argument("--evidence", default="", help="comma-separated paths; required for L0/1")
    a.add_argument("--requested-by", default="claude-lane")
    a.add_argument("--policy", help="approved standing policy (L0/1 only)")
    a.add_argument("--rollback", help="concrete rollback proof (L0/1 only)")
    a.add_argument("--paused-context",
                   help="work paused by an L3 interrupt (paired with --resume-hint)")
    a.add_argument("--resume-hint",
                   help="how to return to paused work (paired with --paused-context)")
    l = sub.add_parser("list", help="list entries")
    l.add_argument("--group", action="store_true", help="grouped operator view")
    l.add_argument("--status", default="pending",
                   choices=("pending", "approved", "rejected", "all"),
                   help="audit filter")
    s = sub.add_parser("show", help="one entry by id prefix (>=4 chars)")
    s.add_argument("--id", required=True)
    for name, hlp in (("approve", "approve; persists a print-only source action"),
                      ("reject", "reject with note"),
                      ("escalate", "raise to interrupt - pins, never hides")):
        d = sub.add_parser(name, help=hlp)
        d.add_argument("--id", required=True)
        d.add_argument("--note", help="decision note (or pipe via stdin)")
        if name == "escalate":
            d.add_argument("--l3-trigger", required=True, choices=L3_TRIGGERS)
            d.add_argument("--paused-context", required=True)
            d.add_argument("--resume-hint", required=True)
    b = sub.add_parser(
        "brief", help="delivery-safe daily brief; replay until explicitly acknowledged")
    b.add_argument("--daypart", default="evening",
                    choices=("morning", "afternoon", "evening"))
    b.add_argument("--mode", default="standard",
                   choices=("standard", "highlights", "minimum", "detailed"),
                   help="explicit presentation preference; inference is never persisted")
    b.add_argument("--ack", metavar="BRIEF_ID",
                   help="acknowledge the pending brief and advance its watermark")
    sub.add_parser("feed", help="idempotently ingest one versioned source event from stdin")
    pr = sub.add_parser("prune", help="drop decided entries older than --days")
    pr.add_argument("--days", type=int, default=30)
    mig = sub.add_parser("migrate", help="preview or apply schema 1/2 to 3 migration")
    mig.add_argument("--apply", action="store_true",
                     help="apply migration after a dry-run; writes a .v1.bak backup")
    f = sub.add_parser("familiar", help="sync one semantic state to the desktop Familiar")
    f.add_argument("--familiar-file", default=str(ROOT / "familiar" / "runtime" / "command.txt"))
    sub.add_parser("status", help="counts + canonical event catalog")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        state_path, policies_path = resolve_authority_paths(args)
        store = Store(state_path)
        if args.cmd == "add":
            print(json.dumps(cmd_add(store, args, policies_path),
                             indent=2, ensure_ascii=False))
        elif args.cmd == "feed":
            print(json.dumps(cmd_feed(store, policies_path),
                             indent=2, ensure_ascii=False))
        elif args.cmd == "list":
            print(cmd_list(store, args))
        elif args.cmd == "show":
            print(json.dumps(entry_by_id(store.load(), args.id), indent=2,
                             ensure_ascii=False))
        elif args.cmd in ("approve", "reject", "escalate"):
            status = {"approve": "approved", "reject": "rejected",
                      "escalate": "escalate"}[args.cmd]
            print(json.dumps(cmd_decide(store, args, status), indent=2,
                             ensure_ascii=False))
        elif args.cmd == "brief":
            result = cmd_brief(store, args)
            print(json.dumps(result, indent=2, ensure_ascii=False)
                  if isinstance(result, dict) else result)
        elif args.cmd == "familiar":
            print(json.dumps(cmd_familiar(store, args), indent=2, ensure_ascii=False))
        elif args.cmd == "prune":
            print(json.dumps(cmd_prune(store, args), ensure_ascii=False))
        elif args.cmd == "migrate":
            print(json.dumps(cmd_migrate(store, args), indent=2,
                             ensure_ascii=False))
        else:
            st = store.load()
            counts = {}
            for e in st["entries"]:
                counts[e["status"]] = counts.get(e["status"], 0) + 1
            print(json.dumps({
                "schema_version": st["schema_version"],
                "catalog_version": st["catalog_version"],
                "revision": st["revision"], "counts": counts,
                "pending_brief": (st["pending_brief"] or {}).get("id"),
                "feed_receipts": len(st["feed_receipts"]),
                "event_defaults": {name: rule[0]
                                   for name, rule in EVENT_CATALOG.items()},
                "legacy_l3_aliases": LEGACY_L3_ALIASES,
                "l3_triggers": list(L3_TRIGGERS),
            }, ensure_ascii=False))
        return 0
    except CommittedStateError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "committed": True,
                          "durability_uncertain": True}, ensure_ascii=False),
              file=sys.stderr)
        return 2
    except (KeyError, ValueError, TimeoutError, OSError) as exc:
        msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
        print(json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
