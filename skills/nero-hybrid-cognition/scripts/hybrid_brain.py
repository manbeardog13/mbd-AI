#!/usr/bin/env python3
"""Cold coordination fabric for independently hosted Codex and Claude lanes.

The coordinator performs no inference and makes no network calls.  It only
stores bounded task/evidence metadata, enforces collision-safe topologies, and
optionally records approved outcome episodes in the sibling learning ledger.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import math
import os
import re
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = 1
HOSTS = ("codex", "claude")
TOPOLOGIES = ("parallel-analysis", "build-review", "disjoint-build")
TASK_STATES = {"open", "active", "awaiting-approval", "completed", "blocked"}
LANE_STATES = {"pending", "claimed", "submitted", "blocked"}
VERDICTS = {"pass", "changes-requested", "blocked"}
SPACE_RE = re.compile(r"\s+")


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime | None = None) -> str:
    return (value or now()).isoformat().replace("+00:00", "Z")


def parse_stamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def clean(value: str, name: str, maximum: int) -> str:
    result = SPACE_RE.sub(" ", value.strip())
    if not result:
        raise ValueError(f"{name} must not be empty")
    if len(result) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    return result


def items(value: str | Iterable[str] | None, *, name: str, maximum: int = 20) -> list[str]:
    if value is None:
        return []
    source = value.split(",") if isinstance(value, str) else value
    result: list[str] = []
    for raw in source:
        item = SPACE_RE.sub(" ", str(raw).strip())
        if not item:
            continue
        if len(item) > 512:
            raise ValueError(f"{name} item exceeds 512 characters")
        if item not in result:
            result.append(item)
    if len(result) > maximum:
        raise ValueError(f"{name} allows at most {maximum} items")
    return result


def tags(value: str | Iterable[str] | None) -> list[str]:
    result = [SPACE_RE.sub("-", row.lower()) for row in items(value, name="tags")]
    if any(len(row) > 64 for row in result):
        raise ValueError("tag exceeds 64 characters")
    return sorted(set(result))


def normal_path(value: str) -> str:
    raw = value.strip().replace("\\", "/")
    if not raw:
        raise ValueError("path must not be empty")
    path = str(PurePosixPath(raw))
    if path in {".", "/"} or ".." in PurePosixPath(path).parts:
        raise ValueError(f"unsafe or overly broad path scope: {value}")
    return path.rstrip("/")


def is_within(path: str, scope: str) -> bool:
    path, scope = normal_path(path), normal_path(scope)
    return path == scope or path.startswith(f"{scope}/")


def scopes_overlap(left: str, right: str) -> bool:
    return is_within(left, right) or is_within(right, left)


def blank_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "updated_at": None,
        "tasks": [],
    }


class Brain:
    def __init__(self, state_path: str | Path):
        self.path = Path(state_path).expanduser().resolve()
        self.lock_path = Path(f"{self.path}.lock")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return blank_state()
        with self.path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported hybrid state schema")
        return state

    @contextlib.contextmanager
    def lock(self, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {time.time()}".encode("ascii"))
                os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - self.lock_path.stat().st_mtime > 300:
                        self.lock_path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"hybrid state is locked: {self.lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            with contextlib.suppress(FileNotFoundError):
                self.lock_path.unlink()

    def save(self, state: dict[str, Any]) -> None:
        state["revision"] = int(state.get("revision", 0)) + 1
        state["updated_at"] = stamp()
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(state, handle, indent=2, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary)

    def mutate(self, operation):
        with self.lock():
            state = self.load()
            result = operation(state)
            self.save(state)
            return result

    @staticmethod
    def task(state: dict[str, Any], task_id: str) -> dict[str, Any]:
        for task in state["tasks"]:
            if task["id"] == task_id:
                return task
        raise KeyError(f"task not found: {task_id}")

    @staticmethod
    def lease_active(lane: dict[str, Any]) -> bool:
        expires = parse_stamp(lane.get("lease_expires_at"))
        return lane["status"] == "claimed" and expires is not None and expires > now()

    @staticmethod
    def refresh(task: dict[str, Any]) -> None:
        for lane in task["lanes"].values():
            if lane["status"] == "claimed" and not Brain.lease_active(lane):
                lane["status"] = "pending"
                lane["claimed_at"] = None
                lane["lease_expires_at"] = None
        if task["topology"] == "build-review":
            builder = task["builder"]
            reviewer = "claude" if builder == "codex" else "codex"
            build_lane = task["lanes"][builder]
            review_lane = task["lanes"][reviewer]
            if build_lane["status"] != "submitted" and review_lane["status"] == "pending":
                review_lane["status"] = "blocked"

    def status(self) -> dict[str, Any]:
        state = self.load()
        counts = {name: 0 for name in sorted(TASK_STATES)}
        for task in state["tasks"]:
            counts[task["status"]] = counts.get(task["status"], 0) + 1
        return {
            "exists": self.path.exists(),
            "path": str(self.path),
            "schema_version": state["schema_version"],
            "revision": state["revision"],
            "tasks": counts,
            "updated_at": state["updated_at"],
        }

    def create(
        self,
        *,
        objective: str,
        acceptance: str,
        topology: str,
        task_kind: str,
        task_tags: str | Iterable[str] | None,
        references: str | Iterable[str] | None,
        builder: str,
        codex_scope: str | None,
        claude_scope: str | None,
    ) -> dict[str, Any]:
        objective = clean(objective, "objective", 1200)
        acceptance = clean(acceptance, "acceptance criteria", 1600)
        task_kind = clean(task_kind, "task kind", 96).lower()
        if topology not in TOPOLOGIES:
            raise ValueError(f"topology must be one of {TOPOLOGIES}")
        if builder not in HOSTS:
            raise ValueError(f"builder must be one of {HOSTS}")
        scope = {"codex": codex_scope, "claude": claude_scope}
        if topology == "disjoint-build":
            if not all(scope.values()):
                raise ValueError("disjoint-build requires both host scopes")
            scope = {host: normal_path(value) for host, value in scope.items()}
            if scopes_overlap(scope["codex"], scope["claude"]):
                raise ValueError("disjoint-build scopes overlap")
        else:
            scope = {host: normal_path(value) if value else None for host, value in scope.items()}
        created = stamp()
        lanes: dict[str, dict[str, Any]] = {}
        for host in HOSTS:
            role = "analyst"
            status = "pending"
            if topology == "build-review":
                role = "builder" if host == builder else "reviewer"
                status = "pending" if role == "builder" else "blocked"
            elif topology == "disjoint-build":
                role = "builder"
            lanes[host] = {
                "host": host,
                "role": role,
                "scope": scope[host],
                "status": status,
                "claimed_at": None,
                "lease_expires_at": None,
                "submission": None,
                "submission_revision": 0,
            }
        task = {
            "id": str(uuid.uuid4()),
            "objective": objective,
            "acceptance": acceptance,
            "task_kind": task_kind,
            "topology": topology,
            "builder": builder if topology == "build-review" else None,
            "tags": tags(task_tags),
            "references": items(references, name="references"),
            "status": "open",
            "lanes": lanes,
            "approval": None,
            "created_at": created,
            "updated_at": created,
        }

        def operation(state):
            state["tasks"].append(task)
            return task

        return self.mutate(operation)

    def claim(self, *, task_id: str, host: str, lease_minutes: int) -> dict[str, Any]:
        if host not in HOSTS:
            raise ValueError(f"host must be one of {HOSTS}")
        if not 1 <= lease_minutes <= 240:
            raise ValueError("lease must be between 1 and 240 minutes")

        def operation(state):
            task = self.task(state, task_id)
            self.refresh(task)
            if task["status"] in {"completed", "blocked"}:
                raise ValueError(f"task is {task['status']}")
            lane = task["lanes"][host]
            if lane["status"] == "blocked":
                raise ValueError("lane is not eligible yet")
            if lane["status"] == "submitted":
                raise ValueError("lane already submitted")
            if self.lease_active(lane):
                raise ValueError("lane already has an active lease")
            claimed = now()
            lane["status"] = "claimed"
            lane["claimed_at"] = stamp(claimed)
            lane["lease_expires_at"] = stamp(claimed + timedelta(minutes=lease_minutes))
            task["status"] = "active"
            task["updated_at"] = stamp()
            return {"task_id": task_id, "lane": lane}

        return self.mutate(operation)

    def submit(
        self,
        *,
        task_id: str,
        host: str,
        summary: str,
        evidence: str | Iterable[str] | None,
        checks: str | Iterable[str] | None,
        risks: str | Iterable[str] | None,
        files: str | Iterable[str] | None,
        verdict: str | None,
    ) -> dict[str, Any]:
        if host not in HOSTS:
            raise ValueError(f"host must be one of {HOSTS}")
        summary = clean(summary, "summary", 1800)
        evidence_rows = items(evidence, name="evidence")
        check_rows = items(checks, name="checks")
        risk_rows = items(risks, name="risks")
        file_rows = [normal_path(row) for row in items(files, name="files")]
        if verdict is not None and verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")

        def operation(state):
            task = self.task(state, task_id)
            self.refresh(task)
            if task["status"] in {"completed", "blocked"}:
                raise ValueError(f"task is {task['status']}")
            lane = task["lanes"][host]
            if lane["status"] != "claimed" or not self.lease_active(lane):
                raise ValueError("host must hold an active lane lease")
            if task["topology"] == "parallel-analysis" and file_rows:
                raise ValueError("parallel-analysis lanes cannot touch repository files")
            if task["topology"] == "build-review" and lane["role"] == "reviewer" and file_rows:
                raise ValueError("build-review reviewer lanes cannot touch repository files")
            if lane["scope"]:
                outside = [row for row in file_rows if not is_within(row, lane["scope"])]
                if outside:
                    raise ValueError(f"files outside {host} scope: {outside}")
            if task["topology"] == "build-review":
                if lane["role"] == "reviewer" and verdict is None:
                    raise ValueError("reviewer submission requires a verdict")
                if lane["role"] == "builder" and verdict is not None:
                    raise ValueError("builder submission cannot set a review verdict")
            elif verdict is not None:
                raise ValueError("verdict is only valid for a build-review reviewer")
            submitted = now()
            claimed = parse_stamp(lane["claimed_at"]) or submitted
            lane["submission_revision"] += 1
            lane["submission"] = {
                "summary": summary,
                "evidence": evidence_rows,
                "checks": check_rows,
                "risks": risk_rows,
                "files": file_rows,
                "verdict": verdict,
                "reviewed_builder_revision": None,
                "elapsed_ms": max(0, round((submitted - claimed).total_seconds() * 1000)),
                "submitted_at": stamp(submitted),
            }
            lane["status"] = "submitted"
            lane["lease_expires_at"] = None
            if task["topology"] == "build-review":
                builder = task["builder"]
                reviewer = "claude" if builder == "codex" else "codex"
                if host == builder:
                    review_lane = task["lanes"][reviewer]
                    review_lane["status"] = "pending"
                    review_lane["submission"] = None
                    review_lane["lease_expires_at"] = None
                else:
                    lane["submission"]["reviewed_builder_revision"] = task["lanes"][builder][
                        "submission_revision"
                    ]
                    if verdict == "changes-requested":
                        task["lanes"][builder]["status"] = "pending"
            task["updated_at"] = stamp()
            gate = self._readiness(task)
            if lane["role"] == "reviewer" and verdict == "blocked":
                task["status"] = "blocked"
            else:
                task["status"] = "awaiting-approval" if gate["ready"] else "active"
            return {"task_id": task_id, "lane": lane, "gate": gate}

        return self.mutate(operation)

    @staticmethod
    def _readiness(task: dict[str, Any]) -> dict[str, Any]:
        missing: list[str] = []
        conflicts: list[str] = []
        if task["topology"] in {"parallel-analysis", "disjoint-build"}:
            for host in HOSTS:
                if task["lanes"][host]["status"] != "submitted":
                    missing.append(f"{host} submission")
        else:
            builder = task["builder"]
            reviewer = "claude" if builder == "codex" else "codex"
            build_lane, review_lane = task["lanes"][builder], task["lanes"][reviewer]
            if build_lane["status"] != "submitted":
                missing.append(f"{builder} builder submission")
            if review_lane["status"] != "submitted":
                missing.append(f"{reviewer} review")
            elif review_lane["submission"]["reviewed_builder_revision"] != build_lane["submission_revision"]:
                missing.append("review of current builder revision")
            elif review_lane["submission"]["verdict"] != "pass":
                conflicts.append(f"review verdict: {review_lane['submission']['verdict']}")
        return {
            "ready": not missing and not conflicts,
            "missing": missing,
            "conflicts": conflicts,
            "requires_explicit_approval": True,
        }

    def ready(self, *, task_id: str) -> dict[str, Any]:
        state = self.load()
        task = self.task(state, task_id)
        gate = self._readiness(task)
        return {"task_id": task_id, "topology": task["topology"], **gate}

    def next(self, *, host: str) -> list[dict[str, Any]]:
        if host not in HOSTS:
            raise ValueError(f"host must be one of {HOSTS}")
        state = self.load()
        result = []
        for task in state["tasks"]:
            self.refresh(task)
            if task["status"] in {"completed", "blocked"}:
                continue
            lane = task["lanes"][host]
            if lane["status"] == "pending" or (
                lane["status"] == "claimed" and not self.lease_active(lane)
            ):
                result.append(
                    {
                        "task_id": task["id"],
                        "objective": task["objective"],
                        "acceptance": task["acceptance"],
                        "topology": task["topology"],
                        "role": lane["role"],
                        "scope": lane["scope"],
                        "tags": task["tags"],
                        "references": task["references"],
                    }
                )
        return result

    def approve(
        self,
        *,
        task_id: str,
        approved: bool,
        quality: float,
        decision_note: str,
        learning_ledger: str | None,
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("explicit approval is required")
        quality = float(quality)
        if not math.isfinite(quality) or not 0.0 <= quality <= 1.0:
            raise ValueError("quality must be between 0 and 1")
        decision_note = clean(decision_note, "decision note", 1000)

        def operation(state):
            task = self.task(state, task_id)
            gate = self._readiness(task)
            if not gate["ready"]:
                raise ValueError(f"merge gate is not ready: {gate}")
            if task["status"] == "completed":
                raise ValueError("task is already completed")
            task["status"] = "completed"
            task["approval"] = {
                "approved": True,
                "quality": quality,
                "decision_note": decision_note,
                "approved_at": stamp(),
            }
            task["updated_at"] = stamp()
            return task

        task = self.mutate(operation)
        learning = None
        if learning_ledger:
            try:
                learning = self._record_learning(task, quality, learning_ledger)
            except Exception as exc:  # task approval is durable even if feedback fails
                learning = {"ok": False, "error": str(exc)}
        return {"task": task, "learning": learning}

    @staticmethod
    def _record_learning(task: dict[str, Any], quality: float, ledger_path: str) -> dict[str, Any]:
        script = Path(__file__).resolve().parents[2] / "nero-continual-learning" / "scripts" / "learning_ledger.py"
        if not script.exists():
            raise FileNotFoundError(f"sibling learning ledger not found: {script}")
        spec = importlib.util.spec_from_file_location("nero_learning_ledger", script)
        if spec is None or spec.loader is None:
            raise ImportError("could not load sibling learning ledger")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ledger = module.Ledger(ledger_path)
        task_kind = task.get("task_kind") or (task["tags"][0] if task["tags"] else "hybrid-task")
        episodes = []
        for host in HOSTS:
            submission = task["lanes"][host].get("submission")
            if submission:
                episodes.append(
                    ledger.record(
                        task_kind=task_kind,
                        resource=f"{host}-hosted",
                        tags=task["tags"],
                        context_label=f"{task['id']}:{host}",
                        success=True,
                        quality=quality,
                        latency_ms=submission["elapsed_ms"],
                        note=f"approved {task['topology']} lane",
                    )
                )
        elapsed = max((row["elapsed_ms"] for row in [task["lanes"][host]["submission"] for host in HOSTS] if row), default=0)
        episodes.append(
            ledger.record(
                task_kind=task_kind,
                resource="codex-claude-hybrid",
                tags=task["tags"],
                context_label=f"{task['id']}:hybrid",
                success=True,
                quality=quality,
                latency_ms=elapsed,
                note=f"approved {task['topology']} aggregate",
            )
        )
        return {"ok": True, "episodes": [row["id"] for row in episodes]}

    def audit(self) -> dict[str, Any]:
        state = self.load()
        errors: list[str] = []
        ids: set[str] = set()
        for task in state.get("tasks", []):
            task_id = task.get("id")
            if task_id in ids:
                errors.append(f"duplicate task id: {task_id}")
            ids.add(task_id)
            if task.get("topology") not in TOPOLOGIES:
                errors.append(f"invalid topology: {task_id}")
            if task.get("status") not in TASK_STATES:
                errors.append(f"invalid task state: {task_id}")
            lanes = task.get("lanes", {})
            if set(lanes) != set(HOSTS):
                errors.append(f"invalid lane set: {task_id}")
                continue
            for host, lane in lanes.items():
                if lane.get("host") != host or lane.get("status") not in LANE_STATES:
                    errors.append(f"invalid {host} lane: {task_id}")
            if task.get("topology") == "disjoint-build":
                left, right = lanes["codex"].get("scope"), lanes["claude"].get("scope")
                if not left or not right or scopes_overlap(left, right):
                    errors.append(f"overlapping disjoint scopes: {task_id}")
                for host, lane in lanes.items():
                    submission = lane.get("submission") or {}
                    if any(not is_within(path, lane["scope"]) for path in submission.get("files", [])):
                        errors.append(f"out-of-scope {host} file: {task_id}")
            if task.get("status") == "completed" and not (task.get("approval") or {}).get("approved"):
                errors.append(f"completed without approval: {task_id}")
        return {
            "ok": not errors,
            "errors": errors,
            "schema_version": state.get("schema_version"),
            "revision": state.get("revision"),
            "tasks": len(state.get("tasks", [])),
        }


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument(
        "--state",
        default=os.environ.get("NERO_HYBRID_STATE", "~/.nero/hybrid-brain.json"),
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("status")

    create = commands.add_parser("create")
    create.add_argument("--objective", required=True)
    create.add_argument("--acceptance", required=True)
    create.add_argument("--topology", choices=TOPOLOGIES, required=True)
    create.add_argument("--task-kind", default="hybrid-task")
    create.add_argument("--tags", default="")
    create.add_argument("--references", default="")
    create.add_argument("--builder", choices=HOSTS, default="codex")
    create.add_argument("--codex-scope")
    create.add_argument("--claude-scope")

    claim = commands.add_parser("claim")
    claim.add_argument("--task-id", required=True)
    claim.add_argument("--host", choices=HOSTS, required=True)
    claim.add_argument("--lease-minutes", type=int, default=30)

    submit = commands.add_parser("submit")
    submit.add_argument("--task-id", required=True)
    submit.add_argument("--host", choices=HOSTS, required=True)
    submit.add_argument("--summary", required=True)
    submit.add_argument("--evidence", default="")
    submit.add_argument("--checks", default="")
    submit.add_argument("--risks", default="")
    submit.add_argument("--files", default="")
    submit.add_argument("--verdict", choices=VERDICTS)

    ready = commands.add_parser("ready")
    ready.add_argument("--task-id", required=True)

    approve = commands.add_parser("approve")
    approve.add_argument("--task-id", required=True)
    approve.add_argument("--approved", action="store_true")
    approve.add_argument("--quality", type=float, required=True)
    approve.add_argument("--decision-note", required=True)
    approve.add_argument("--learning-ledger")

    next_command = commands.add_parser("next")
    next_command.add_argument("--host", choices=HOSTS, required=True)
    commands.add_parser("audit")
    return root


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    brain = Brain(args.state)
    try:
        if args.command == "status":
            output = brain.status()
        elif args.command == "create":
            output = brain.create(
                objective=args.objective,
                acceptance=args.acceptance,
                topology=args.topology,
                task_kind=args.task_kind,
                task_tags=args.tags,
                references=args.references,
                builder=args.builder,
                codex_scope=args.codex_scope,
                claude_scope=args.claude_scope,
            )
        elif args.command == "claim":
            output = brain.claim(task_id=args.task_id, host=args.host, lease_minutes=args.lease_minutes)
        elif args.command == "submit":
            output = brain.submit(
                task_id=args.task_id,
                host=args.host,
                summary=args.summary,
                evidence=args.evidence,
                checks=args.checks,
                risks=args.risks,
                files=args.files,
                verdict=args.verdict,
            )
        elif args.command == "ready":
            output = brain.ready(task_id=args.task_id)
        elif args.command == "approve":
            output = brain.approve(
                task_id=args.task_id,
                approved=args.approved,
                quality=args.quality,
                decision_note=args.decision_note,
                learning_ledger=args.learning_ledger,
            )
        elif args.command == "next":
            output = brain.next(host=args.host)
        else:
            output = brain.audit()
        print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except (KeyError, PermissionError, TimeoutError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
