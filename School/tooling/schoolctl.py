#!/usr/bin/env python3
"""Deterministic control plane for Nero School.

No model or network calls occur here. The tool manages evidence, task agreement,
bounded attempts, deterministic grading, dual-host audits, and experience XP.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHOOL = Path(__file__).resolve().parents[1]
EXPERIENCE = SCHOOL / "experience.json"
DEBATE = SCHOOL / "DEBATE CC"
LOG = DEBATE / "LOG.txt"
SIGNALS = DEBATE / ".signals"
ACTORS = {"codex", "claude"}
MAX_DEBATE_ROUNDS = 3
MAX_ATTEMPTS = 3
PASS_GRADE = 8.7
MAX_XP = 10_000


def utc_stamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


@contextlib.contextmanager
def file_lock(target: Path, timeout: float = 5.0):
    lock = Path(f"{target}.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}".encode("ascii"))
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 300:
                    lock.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"School state is locked: {lock}")
            time.sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def clean(value: str, name: str, maximum: int = 1600) -> str:
    result = " ".join(value.strip().split())
    if not result:
        raise ValueError(f"{name} must not be empty")
    if len(result) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    return result


def resolve_task(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    school = SCHOOL.resolve()
    if school not in path.parents or not (path / "task.json").exists():
        raise ValueError("task must be a Nero School task folder")
    return path


def task_digest(task: Path) -> str:
    selected = ("task.json", "TASK.md", "context.md", "TOOLS.md")
    data = bytearray()
    for name in selected:
        path = task / name
        if not path.exists():
            raise ValueError(f"task is missing {name}")
        data.extend(name.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return digest_bytes(bytes(data))


def entry_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ENTRY "):
            entries.append(json.loads(line[6:]))
    return entries


def verify_chain(path: Path) -> list[dict[str, Any]]:
    previous = "0" * 64
    entries = entry_lines(path)
    for index, row in enumerate(entries, 1):
        supplied = row.get("entry_hash")
        payload = {key: value for key, value in row.items() if key != "entry_hash"}
        if payload.get("prev_hash") != previous:
            raise ValueError(f"broken hash chain in {path} entry {index}")
        expected = digest_bytes(canonical(payload))
        if supplied != expected:
            raise ValueError(f"altered entry in {path} entry {index}")
        previous = supplied
    return entries


def append_entry(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    with file_lock(path):
        entries = verify_chain(path)
        payload = dict(payload)
        payload["prev_hash"] = entries[-1]["entry_hash"] if entries else "0" * 64
        payload["entry_hash"] = digest_bytes(canonical(payload))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("ENTRY " + json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return payload


def agreement_state(task: Path) -> dict[str, Any]:
    entries = verify_chain(task / "Task_agreement.txt")
    current_digest = task_digest(task)
    by_round: dict[int, dict[str, dict[str, Any]]] = {}
    for row in entries:
        by_round.setdefault(int(row["round"]), {})[row["actor"]] = row
    if not by_round:
        return {"status": "PENDING", "round": 0, "task_digest": current_digest}
    latest_round = max(by_round)
    latest = by_round[latest_round]
    if any(row["decision"] == "BLOCK" for row in latest.values()):
        status = "BLOCKED"
    elif set(latest) == ACTORS and all(row["decision"] == "APPROVE" for row in latest.values()):
        digests = {row["task_digest"] for row in latest.values()}
        status = "AGREED" if digests == {current_digest} else "STALE"
    else:
        status = "PENDING"
    return {"status": status, "round": latest_round, "task_digest": current_digest, "entries": latest}


def command_agree(args) -> dict[str, Any]:
    task = resolve_task(args.task)
    actor = args.actor.lower()
    if actor not in ACTORS:
        raise ValueError("actor must be codex or claude")
    if not 1 <= args.round <= MAX_DEBATE_ROUNDS:
        raise ValueError("debate round must be 1, 2, or 3")
    entries = verify_chain(task / "Task_agreement.txt")
    if any(row["actor"] == actor and int(row["round"]) == args.round for row in entries):
        raise ValueError(f"{actor} already submitted round {args.round}")
    if entries and args.round > max(int(row["round"]) for row in entries) + 1:
        raise ValueError("debate rounds cannot be skipped")
    entry = append_entry(
        task / "Task_agreement.txt",
        {
            "type": "agreement",
            "actor": actor,
            "round": args.round,
            "decision": args.decision.upper(),
            "note": clean(args.note, "agreement note"),
            "task_digest": task_digest(task),
            "timestamp": utc_stamp(),
        },
    )
    return {"entry": entry, "agreement": agreement_state(task)}


def next_attempt(task: Path) -> int:
    runs = task / "runs"
    attempts = [int(path.name.split("_")[-1]) for path in runs.glob("attempt_*") if path.is_dir()]
    return max(attempts, default=0) + 1


def latest_run(task: Path) -> Path:
    runs = sorted((task / "runs").glob("attempt_*"))
    if not runs:
        raise ValueError("no prepared attempt exists")
    return runs[-1]


def command_prepare(args) -> dict[str, Any]:
    task = resolve_task(args.task)
    with file_lock(task / ".attempts"):
        agreement = agreement_state(task)
        if agreement["status"] != "AGREED":
            raise ValueError(f"task cannot run until Codex and Claude agree: {agreement['status']}")
        attempt = next_attempt(task)
        if attempt > MAX_ATTEMPTS:
            raise ValueError("three attempts exhausted; stop and redesign the task with Toni")
        run = task / "runs" / f"attempt_{attempt:03d}"
        work = run / "work"
        if run.exists():
            raise ValueError("attempt already exists")
        shutil.copytree(task / "starter", work)
        run_record = {
            "run_id": f"{load_json(task / 'task.json')['id']}:attempt-{attempt}",
            "attempt": attempt,
            "task_digest": agreement["task_digest"],
            "status": "PREPARED",
            "created_at": utc_stamp(),
        }
        atomic_json(run / "run.json", run_record)
        return {"run": str(run), "work": str(work), **run_record}


def get_path(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def normalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, list):
        return [normalize(row) for row in value]
    return value


def run_checks(task: Path, run: Path) -> dict[str, Any]:
    spec = load_json(task / "task.json")
    work = run / "work"
    outcomes = []
    earned = 0.0
    possible = 0.0
    json_cache: dict[str, Any] = {}
    for check in spec["checks"]:
        weight = float(check.get("weight", 1.0))
        possible += weight
        kind = check["type"]
        passed = False
        detail = ""
        target = work / check.get("file", "submission.json")
        try:
            if kind == "file_exists":
                passed = target.is_file()
                detail = str(target)
            elif kind.startswith("json_"):
                key = str(target)
                if key not in json_cache:
                    json_cache[key] = load_json(target)
                actual = get_path(json_cache[key], check["path"])
                if kind == "json_equals":
                    passed = normalize(actual) == normalize(check["expected"])
                elif kind == "json_contains_all":
                    actual_values = {normalize(row) for row in actual}
                    passed = all(normalize(row) in actual_values for row in check["expected"])
                elif kind == "json_excludes_all":
                    actual_values = {normalize(row) for row in actual}
                    passed = all(normalize(row) not in actual_values for row in check["expected"])
                elif kind == "json_number":
                    passed = abs(float(actual) - float(check["expected"])) <= float(check.get("tolerance", 0))
                elif kind == "json_max":
                    passed = float(actual) <= float(check["expected"])
                detail = f"{check['path']}={actual!r}"
            elif kind == "text_contains":
                content = target.read_text(encoding="utf-8").casefold()
                passed = all(str(row).casefold() in content for row in check["expected"])
                detail = str(target)
            elif kind == "python_unittest":
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py", "-q"],
                    cwd=work,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                passed = result.returncode == 0
                detail = (result.stdout + result.stderr)[-1200:]
            else:
                raise ValueError(f"unsupported check type: {kind}")
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
        if passed:
            earned += weight
        outcomes.append({"id": check["id"], "type": kind, "passed": passed, "weight": weight, "detail": detail})
    score = round(10.0 * earned / possible, 3) if possible else 0.0
    return {
        "task_id": spec["id"],
        "run_id": load_json(run / "run.json")["run_id"],
        "objective_score": score,
        "earned_weight": earned,
        "possible_weight": possible,
        "checks": outcomes,
        "graded_at": utc_stamp(),
    }


def command_grade(args) -> dict[str, Any]:
    task = resolve_task(args.task)
    run = Path(args.run).resolve() if args.run else latest_run(task)
    if task not in run.parents or not (run / "run.json").exists():
        raise ValueError("run does not belong to task")
    result = run_checks(task, run)
    atomic_json(run / "grader_result.json", result)
    run_record = load_json(run / "run.json")
    run_record["status"] = "GRADED"
    run_record["objective_score"] = result["objective_score"]
    atomic_json(run / "run.json", run_record)
    return result


def command_audit(args) -> dict[str, Any]:
    task = resolve_task(args.task)
    reviewer = args.reviewer.lower()
    if reviewer not in ACTORS:
        raise ValueError("reviewer must be codex or claude")
    run = Path(args.run).resolve() if args.run else latest_run(task)
    grader = load_json(run / "grader_result.json")
    scores = {
        "objective": float(grader["objective_score"]),
        "process": float(args.process),
        "safety": float(args.safety),
        "efficiency": float(args.efficiency),
        "communication": float(args.communication),
    }
    if any(not 0.0 <= value <= 10.0 for value in scores.values()):
        raise ValueError("audit scores must be between 0 and 10")
    grade = round(
        scores["objective"] * 0.50
        + scores["process"] * 0.20
        + scores["safety"] * 0.15
        + scores["efficiency"] * 0.10
        + scores["communication"] * 0.05,
        3,
    )
    existing = verify_chain(task / "AUDIT.txt")
    if any(row["reviewer"] == reviewer and row["run_id"] == grader["run_id"] for row in existing):
        raise ValueError(f"{reviewer} already audited {grader['run_id']}")
    entry = append_entry(
        task / "AUDIT.txt",
        {
            "type": "audit",
            "reviewer": reviewer,
            "run_id": grader["run_id"],
            "grade": grade,
            "scores": scores,
            "observations": clean(args.observations, "observations"),
            "evidence": clean(args.evidence, "evidence"),
            "grader_digest": digest_bytes(canonical(grader)),
            "timestamp": utc_stamp(),
        },
    )
    return entry


def update_experience(task: Path, run_id: str, grade: float) -> dict[str, Any]:
    with file_lock(EXPERIENCE):
        state = load_json(EXPERIENCE)
        if run_id in state["awards"]:
            return {"awarded": False, "reason": "run already awarded"}
        spec = load_json(task / "task.json")
        base = float(spec["difficulty"]) * 100.0 * (grade / 10.0)
        award = {}
        for virtue, weight in spec["virtue_weights"].items():
            amount = round(base * float(weight))
            if virtue not in state["virtues"]:
                raise ValueError(f"unknown virtue in task: {virtue}")
            row = state["virtues"][virtue]
            row["xp"] = min(MAX_XP, int(row["xp"]) + amount)
            row["evidence_count"] = int(row.get("evidence_count", 0)) + 1
            row["last_updated"] = utc_stamp()
            award[virtue] = amount
        state["awards"][run_id] = {"task_id": spec["id"], "grade": grade, "xp": award, "timestamp": utc_stamp()}
        state["updated_at"] = utc_stamp()
        atomic_json(EXPERIENCE, state)
        return {"awarded": True, "xp": award}


def command_finalize(args) -> dict[str, Any]:
    task = resolve_task(args.task)
    run = Path(args.run).resolve() if args.run else latest_run(task)
    grader = load_json(run / "grader_result.json")
    audits = [row for row in verify_chain(task / "AUDIT.txt") if row["run_id"] == grader["run_id"]]
    latest = {row["reviewer"]: row for row in audits}
    if set(latest) != ACTORS:
        raise ValueError("both Codex and Claude audits are required")
    grades = [latest[actor]["grade"] for actor in sorted(ACTORS)]
    overall = round(sum(grades) / len(grades), 3)
    passed = grader["objective_score"] >= PASS_GRADE and overall >= PASS_GRADE and min(grades) >= 8.0
    run_record = load_json(run / "run.json")
    attempt = int(run_record["attempt"])
    if passed:
        status = "PASSED"
        award = update_experience(task, grader["run_id"], overall)
    elif attempt >= MAX_ATTEMPTS:
        status = "BLOCKED_AFTER_THREE_ATTEMPTS"
        award = {"awarded": False, "reason": "threshold not met"}
    else:
        status = "REMEDIATION_REQUIRED"
        award = {"awarded": False, "reason": "threshold not met"}
    run_record.update({"status": status, "overall_grade": overall, "finalized_at": utc_stamp()})
    atomic_json(run / "run.json", run_record)
    return {
        "run_id": grader["run_id"],
        "status": status,
        "objective_score": grader["objective_score"],
        "reviewer_grades": latest,
        "overall_grade": overall,
        "threshold": PASS_GRADE,
        "experience": award,
    }


def level_for_xp(xp: int) -> int:
    return max(1, min(100, round(100 * math.sqrt(max(0, xp) / MAX_XP))))


def render_dashboard() -> str:
    state = load_json(EXPERIENCE)
    width = 28
    rows = [
        "NERO EXPERIENCE - EVIDENCE-BASED ESTIMATES",
        f"Updated: {state['updated_at']}   Scale: 1 rookie, 100 master   Pass gate: {PASS_GRADE}/10",
        "Scores are experience estimates, not guarantees of correctness.",
        "",
    ]
    ordered = sorted(state["virtues"].items(), key=lambda item: item[1]["name"])
    for key, item in ordered:
        level = level_for_xp(int(item["xp"]))
        filled = round(width * level / 100)
        bar = "#" * filled + "-" * (width - filled)
        rows.append(
            f"{item['name'][:30]:30} [{bar}] {level:3d}%  evidence={item.get('evidence_count', 0):2d}  confidence={item['confidence']}"
        )
    rows.extend(["", "Only a finalized dual-audited run can award XP."])
    return "\n".join(rows)


def command_dashboard(args) -> None:
    if not args.watch:
        print(render_dashboard())
        return
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print(render_dashboard(), flush=True)
            time.sleep(max(0.5, args.interval))
    except KeyboardInterrupt:
        pass


def emit_signal(source_actor: str, reason: str) -> Path:
    target = "claude" if source_actor == "codex" else "codex"
    path = SIGNALS / f"{target}.pending.json"
    atomic_json(path, {"target": target, "source": source_actor, "reason": reason, "timestamp": utc_stamp()})
    return path


def command_log(args) -> dict[str, Any]:
    actor = args.actor.lower()
    if actor not in ACTORS:
        raise ValueError("actor must be codex or claude")
    grade = None if args.grade is None else float(args.grade)
    if grade is not None and not 0 <= grade <= 10:
        raise ValueError("grade must be between 0 and 10")
    entry = append_entry(
        LOG,
        {
            "type": "work-log",
            "actor": actor,
            "event": args.event.upper(),
            "task": clean(args.task, "task", 300),
            "grade": grade,
            "note": clean(args.note, "note", 1000),
            "timestamp": utc_stamp(),
        },
    )
    signal = emit_signal(actor, f"LOG.txt changed: {args.event.upper()} {args.task}")
    return {"entry": entry, "signal": str(signal)}


def command_ack(args) -> dict[str, Any]:
    actor = args.actor.lower()
    if actor not in ACTORS:
        raise ValueError("actor must be codex or claude")
    path = SIGNALS / f"{actor}.pending.json"
    if not path.exists():
        return {"acknowledged": False, "reason": "no pending signal"}
    signal = json.loads(path.read_text(encoding="utf-8-sig"))
    archive = SIGNALS / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    safe_time = utc_stamp().replace(":", "-")
    destination = archive / f"{safe_time}-{actor}.json"
    os.replace(path, destination)
    return {"acknowledged": True, "signal": signal, "archived": str(destination)}


def command_verify(_args) -> dict[str, Any]:
    errors = []
    try:
        verify_chain(LOG)
    except Exception as exc:
        errors.append(str(exc))
    task_count = 0
    for task_json in SCHOOL.glob("[0-9][0-9]_*/*/task.json"):
        task = task_json.parent
        task_count += 1
        for required in (
            "README.md",
            "TASK.md",
            "context.md",
            "TOOLS.md",
            "Task_agreement.txt",
            "AUDIT.txt",
            "RUN_TASK.bat",
            "GRADE_LATEST.bat",
        ):
            if not (task / required).exists():
                errors.append(f"{task}: missing {required}")
        for ledger in ("Task_agreement.txt", "AUDIT.txt"):
            try:
                verify_chain(task / ledger)
            except Exception as exc:
                errors.append(str(exc))
        try:
            task_digest(task)
        except Exception as exc:
            errors.append(str(exc))
    experience = load_json(EXPERIENCE)
    if experience.get("schema_version") != 1 or len(experience.get("virtues", {})) < 15:
        errors.append("experience.json schema or virtue catalog is incomplete")
    return {"ok": not errors, "errors": errors, "tasks": task_count, "virtues": len(experience["virtues"])}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    dashboard = commands.add_parser("dashboard")
    dashboard.add_argument("--watch", action="store_true")
    dashboard.add_argument("--interval", type=float, default=2.0)
    agree = commands.add_parser("agree")
    agree.add_argument("--task", required=True)
    agree.add_argument("--actor", choices=sorted(ACTORS), required=True)
    agree.add_argument("--round", type=int, required=True)
    agree.add_argument("--decision", choices=("APPROVE", "REVISE", "BLOCK"), required=True)
    agree.add_argument("--note", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--task", required=True)
    grade = commands.add_parser("grade")
    grade.add_argument("--task", required=True)
    grade.add_argument("--run")
    audit = commands.add_parser("audit")
    audit.add_argument("--task", required=True)
    audit.add_argument("--run")
    audit.add_argument("--reviewer", choices=sorted(ACTORS), required=True)
    audit.add_argument("--process", type=float, required=True)
    audit.add_argument("--safety", type=float, required=True)
    audit.add_argument("--efficiency", type=float, required=True)
    audit.add_argument("--communication", type=float, required=True)
    audit.add_argument("--observations", required=True)
    audit.add_argument("--evidence", required=True)
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--task", required=True)
    finalize.add_argument("--run")
    log = commands.add_parser("log")
    log.add_argument("--actor", choices=sorted(ACTORS), required=True)
    log.add_argument("--event", choices=("START", "FINISH", "NOTE"), required=True)
    log.add_argument("--task", required=True)
    log.add_argument("--grade", type=float)
    log.add_argument("--note", required=True)
    ack = commands.add_parser("ack")
    ack.add_argument("--actor", choices=sorted(ACTORS), required=True)
    commands.add_parser("verify")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "dashboard":
            command_dashboard(args)
            return 0
        handlers = {
            "agree": command_agree,
            "prepare": command_prepare,
            "grade": command_grade,
            "audit": command_audit,
            "finalize": command_finalize,
            "log": command_log,
            "ack": command_ack,
            "verify": command_verify,
        }
        output = handlers[args.command](args)
        print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if output.get("ok", True) else 1
    except (FileNotFoundError, KeyError, PermissionError, TimeoutError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
