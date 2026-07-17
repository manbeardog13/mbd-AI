#!/usr/bin/env python3
"""Review Inbox - the operator attention surface (ADR-0021, review-inbox.spec).

v1.1 after dual independent review: injection-guarded gate commands, one-winner
stale-lock breaking with ownership tokens, fenced-block-proof policy parsing,
state shape validation, sanitized rendering, escalate-pins-not-hides,
watermarked briefs, audit filters. Cold, stdlib-only, run-and-exit. The inbox
is a queue-view over authoritative gates, never a second authority.
"""
from __future__ import annotations

import argparse
import contextlib
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
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "data" / "review-inbox.json"
DEFAULT_POLICIES = ROOT / "docs" / "canon" / "STANDING_POLICIES.md"
SCHEMA_VERSION = 1

L3_CLASSES = ("security-gate", "publication", "identity-change", "deletion",
              "purchase", "xp-finalization")
STATUSES = ("pending", "approved", "rejected")
CATEGORY_RE = re.compile(r"^[a-z0-9-]{1,40}$")
DHEF_REF_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
GATE_COMMANDS = {
    "dhef": ("python skills/nero-hybrid-cognition/scripts/hybrid_brain.py "
             "--state data/hybrid-brain.json approve --task-id {ref} "
             "--approved --quality 0.9 --decision-note approved-via-inbox"),
    "school": "python School/tooling/schoolctl.py finalize --task {ref}",
    "adr": "flip the Status line of {ref} and commit (publication gate applies)",
    "git": "merge {ref} after review (publication gate applies)",
    "skill": "update lifecycle frontmatter of {ref} per docs/specs/skill-lifecycle.spec.md",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def printable(text: str, limit: int) -> str:
    clean = "".join(ch for ch in text if ch.isprintable() or ch == " ")
    return " ".join(clean.split())[:limit]


def blank() -> dict:
    return {"schema_version": SCHEMA_VERSION, "revision": 0,
            "updated_at": None, "last_brief_at": None, "entries": []}


def validate_state(state, path: Path) -> dict:
    if not isinstance(state, dict) or not isinstance(state.get("entries"), list):
        raise ValueError(f"corrupt inbox state {path}: bad top-level shape")
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported inbox schema in {path}")
    for e in state["entries"]:
        if not isinstance(e, dict) or not isinstance(e.get("source"), dict):
            raise ValueError(f"corrupt inbox state {path}: bad entry shape")
        for field in ("id", "status", "level", "category", "created_at"):
            if field not in e:
                raise ValueError(f"corrupt inbox state {path}: entry missing {field}")
        if e["status"] not in STATUSES:
            raise ValueError(f"corrupt inbox state {path}: bad status {e['status']!r}")
    return state


class Store:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser().resolve()
        self.lock_path = Path(f"{self.path}.lock")

    @contextlib.contextmanager
    def lock(self, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        token = f"{os.getpid()}-{uuid.uuid4().hex[:10]}"
        acquired = False
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                acquired = True
                try:
                    os.write(fd, token.encode("ascii"))
                finally:
                    os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - self.lock_path.stat().st_mtime > 300:
                        stale = Path(f"{self.lock_path}.stale.{os.getpid()}")
                        try:
                            os.replace(self.lock_path, stale)  # one winner
                        except FileNotFoundError:
                            continue
                        with contextlib.suppress(FileNotFoundError):
                            os.unlink(stale)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"inbox is locked: {self.lock_path}")
                time.sleep(0.05)
            except BaseException:
                if acquired:
                    with contextlib.suppress(FileNotFoundError):
                        self.lock_path.unlink()
                raise
        try:
            yield
        finally:
            try:  # ownership check: only the token holder releases
                if self.lock_path.read_text(encoding="ascii") == token:
                    self.lock_path.unlink()
            except (FileNotFoundError, OSError):
                pass

    def load(self) -> dict:
        if not self.path.exists():
            return blank()
        state = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError(f"corrupt inbox state {self.path}: bad top-level shape")
        state.setdefault("last_brief_at", None)
        return validate_state(state, self.path)

    def save(self, state: dict) -> None:
        state["revision"] = int(state.get("revision", 0)) + 1
        state["updated_at"] = now()
        fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp",
                                   dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as h:
                json.dump(state, h, indent=2, ensure_ascii=False, sort_keys=True)
                h.write("\n")
                h.flush()
                os.fsync(h.fileno())
            for attempt in range(5):
                try:
                    os.replace(tmp, self.path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)

    def mutate(self, op):
        with self.lock():
            state = self.load()
            result = op(state)
            self.save(state)
            return result


def parse_policies(path: Path):
    """Return (approved: set, malformed: set). Fenced blocks stripped;
    exactly one status line per section or the section is malformed."""
    if not path.exists():
        return set(), set()
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    approved, malformed = set(), set()
    for m in re.finditer(r"^## policy: ([\w-]+)\s*$(.*?)(?=^## |\Z)", text, re.M | re.S):
        name, body = m.group(1), m.group(2)
        statuses = re.findall(r"^status: (\w+)\s*$", body, re.M)
        if len(statuses) != 1:
            malformed.add(name)
        elif statuses[0] == "approved":
            approved.add(name)
    return approved, malformed


def entry_by_id(state: dict, prefix: str) -> dict:
    if len(prefix) < 4:
        raise ValueError("id prefix must be at least 4 characters")
    hits = [e for e in state["entries"] if e["id"].startswith(prefix)]
    if not hits:
        raise KeyError(f"no entry matches {prefix}")
    if len(hits) > 1:
        raise KeyError(f"ambiguous id prefix {prefix}")
    return hits[0]


def cmd_add(store: Store, args, policies_path: Path) -> dict:
    level = args.level
    category = args.category.strip().lower()
    if not CATEGORY_RE.match(category):
        raise ValueError("category must be a slug: [a-z0-9-]{1,40}")
    if category in L3_CLASSES and level != 3:
        raise ValueError(f"category {category} is an interrupt class; "
                         "level 3 is immovable")
    if args.source_kind == "dhef" and not DHEF_REF_RE.match(args.source_ref or ""):
        raise ValueError("dhef source-ref must match [A-Za-z0-9._-]{1,64}")
    if level >= 2 and args.policy:
        raise ValueError("--policy is only meaningful for self-approval "
                         "levels 0/1; reject to keep the audit trail honest")
    evidence = [e.strip() for e in (args.evidence or "").split(",") if e.strip()]
    if level in (0, 1):
        if not args.policy:
            raise ValueError("level 0/1 requires --policy (self-decision rule)")
        approved, malformed = parse_policies(policies_path)
        if args.policy in malformed:
            raise ValueError(f"policy {args.policy!r} is malformed in the "
                             "registry; fail closed")
        if args.policy not in approved:
            raise ValueError(f"policy {args.policy!r} is not an approved "
                             "standing policy; self-approval denied")
        if not evidence:
            raise ValueError("self-approval requires non-empty --evidence "
                             "(self-decision rule, third condition)")
    entry = {
        "id": str(uuid.uuid4()), "created_at": now(),
        "level": level, "category": category,
        "blocking": level == 3, "risk": args.risk,
        "title": printable(args.title, 200),
        "source": {"kind": args.source_kind,
                   "ref": printable(args.source_ref or "", 200)},
        "evidence": evidence,
        "requested_by": args.requested_by,
        "status": "pending", "decided_at": None, "decision_note": None,
        "policy": args.policy,
    }
    if level in (0, 1):
        entry["status"] = "approved"
        entry["decided_at"] = now()
        entry["decision_note"] = f"self-approved under policy {args.policy}"

    def op(state):
        state["entries"].append(entry)
        return entry

    return store.mutate(op)


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
    esc = [e for e in pending if e.get("escalated_at")]
    blocking = [e for e in pending if e["blocking"] and e not in esc]
    for e in esc:
        lines.append(f"! ESCALATED - {e['title']} [{e['category']}] ({e['id'][:8]})")
    for e in blocking:
        lines.append(f"! BLOCKING - {e['title']} [{e['category']}] ({e['id'][:8]})")
    if esc or blocking:
        lines.append("")
    by_cat = {}
    for e in pending:
        if not e["blocking"]:
            by_cat.setdefault(e["category"], []).append(e)
    for cat in sorted(by_cat):
        lines.append(f"- {len(by_cat[cat]):>2} {cat}")
    audited = [e for e in state["entries"]
               if e["status"] == "approved" and e.get("policy")
               and e["level"] in (0, 1)]
    if audited:
        lines.append(f"- {len(audited):>2} automatic approvals "
                     f"(audit trail: list --status approved)")
    return "\n".join(lines)


def cmd_brief(store: Store, args) -> str:
    def op(state):
        mark = state.get("last_brief_at") or "1970-01-01T00:00:00Z"
        done = [e for e in state["entries"]
                if e.get("decided_at") and e["decided_at"] > mark]
        pending = [e for e in state["entries"] if e["status"] == "pending"]
        blocking = [e for e in pending if e["blocking"]]
        l2 = [e for e in pending if e["level"] == 2]
        stale_cut = time.time() - 3 * 86400
        longrun = [e for e in pending
                   if datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
                   .timestamp() < stale_cut]
        lines = [f"Good {args.daypart}.", "Since your last brief:"]
        by_cat = {}
        for e in done:
            by_cat.setdefault(e["category"], []).append(e)
        for cat in sorted(by_cat):
            lines.append(f"- {len(by_cat[cat])} {cat} decided")
        if not done:
            lines.append("- nothing decided")
        for e in blocking:
            lines.append(f"- BLOCKING: {e['title']} ({e['id'][:8]})")
        if not blocking:
            lines.append("- Blocking items: none")
        if l2:
            lines.append(f"- Waiting ({len(l2)}): " + " / ".join(
                f"{e['title']} ({e['id'][:8]})" for e in l2[:6]))
        if longrun:
            lines.append(f"- Long-running (>3 days): {len(longrun)}")
        words = len(" ".join(lines).split())
        seconds = max(15, int(math.ceil(words / 200 * 60 / 15)) * 15)
        est = (f"{seconds} seconds" if seconds < 90
               else f"{math.ceil(seconds / 60)} minutes")
        lines.append(f"Estimated reading time: {est}.")
        state["last_brief_at"] = now()
        return "\n".join(lines)

    return store.mutate(op)


def cmd_decide(store: Store, args, status: str) -> dict:
    note = printable(args.note, 2000) if args.note else (
        "" if sys.stdin.isatty() else printable(sys.stdin.read(), 2000))

    def op(state):
        e = entry_by_id(state, args.id)
        if e["status"] != "pending":
            raise ValueError(f"entry already {e['status']}")
        if status == "escalate":
            # Escalation raises, never hides: pin at interrupt, stay pending.
            e["level"] = 3
            e["blocking"] = True
            e["escalated_at"] = now()
            e["decision_note"] = note or e.get("decision_note")
            return e
        e["status"] = status
        e["decided_at"] = now()
        e["decision_note"] = note or None
        return e

    e = store.mutate(op)
    out = {"entry": e}
    if status == "approved":
        kind, ref = e["source"]["kind"], e["source"]["ref"]
        template = GATE_COMMANDS.get(kind)
        if template and ref:
            if kind == "dhef" and not DHEF_REF_RE.match(ref):
                out["drives_gate_error"] = ("source ref failed validation; "
                                            "refusing to print a gate command")
            else:
                out["drives_gate"] = template.format(ref=ref)
                out["drives_gate_note"] = ("the inbox never drives gates itself - "
                                           "run the command to drive the real one")
    return out


def cmd_prune(store: Store, args) -> dict:
    if args.days < 1:
        raise ValueError("--days must be >= 1 (the audit trail is not a typo away)")
    cutoff = time.time() - args.days * 86400

    def op(state):
        keep, dropped = [], 0
        for e in state["entries"]:
            ts = e.get("decided_at") or e["created_at"]
            t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            if e["status"] == "pending" or t >= cutoff:
                keep.append(e)
            else:
                dropped += 1
        state["entries"] = keep
        return {"dropped": dropped, "kept": len(keep)}

    return store.mutate(op)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state", default=str(DEFAULT_STATE),
                   help="inbox store path (default data/review-inbox.json)")
    p.add_argument("--policies", default=str(DEFAULT_POLICIES),
                   help="standing-policies registry path")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="file an item at a level")
    a.add_argument("--title", required=True, help="one line, printable")
    a.add_argument("--category", required=True, help="slug; L3 classes force level 3")
    a.add_argument("--level", type=int, choices=(0, 1, 2, 3), required=True,
                   help="0 silent / 1 brief / 2 review / 3 interrupt")
    a.add_argument("--risk", choices=("low", "medium", "high"), default="low")
    a.add_argument("--source-kind", default="policy",
                   choices=("dhef", "school", "adr", "git", "skill", "policy"))
    a.add_argument("--source-ref", default="", help="gate reference (validated for dhef)")
    a.add_argument("--evidence", default="", help="comma-separated paths; required for L0/1")
    a.add_argument("--requested-by", default="claude-lane")
    a.add_argument("--policy", help="approved standing policy (L0/1 only)")
    l = sub.add_parser("list", help="list entries")
    l.add_argument("--group", action="store_true", help="grouped operator view")
    l.add_argument("--status", default="pending",
                   choices=("pending", "approved", "rejected", "all"),
                   help="audit filter")
    s = sub.add_parser("show", help="one entry by id prefix (>=4 chars)")
    s.add_argument("--id", required=True)
    for name, hlp in (("approve", "approve; prints the real gate command"),
                      ("reject", "reject with note"),
                      ("escalate", "raise to interrupt - pins, never hides")):
        d = sub.add_parser(name, help=hlp)
        d.add_argument("--id", required=True)
        d.add_argument("--note", help="decision note (or pipe via stdin)")
    b = sub.add_parser("brief", help="watermarked daily brief; advances last_brief_at")
    b.add_argument("--daypart", default="evening")
    pr = sub.add_parser("prune", help="drop decided entries older than --days")
    pr.add_argument("--days", type=int, default=30)
    sub.add_parser("status", help="counts + L3 classes")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(Path(args.state))
    try:
        if args.cmd == "add":
            print(json.dumps(cmd_add(store, args, Path(args.policies)),
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
            print(cmd_brief(store, args))
        elif args.cmd == "prune":
            print(json.dumps(cmd_prune(store, args), ensure_ascii=False))
        else:
            st = store.load()
            counts = {}
            for e in st["entries"]:
                counts[e["status"]] = counts.get(e["status"], 0) + 1
            print(json.dumps({"revision": st["revision"], "counts": counts,
                              "l3_classes": list(L3_CLASSES)}, ensure_ascii=False))
        return 0
    except (KeyError, ValueError, TimeoutError, OSError) as exc:
        msg = exc.args[0] if isinstance(exc, KeyError) and exc.args else str(exc)
        print(json.dumps({"ok": False, "error": str(msg)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
