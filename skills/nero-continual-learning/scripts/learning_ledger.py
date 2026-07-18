#!/usr/bin/env python3
"""Cold, deterministic evidence ledger for Nero's hosted learning loop.

This module stores bounded outcome metadata and approved lessons.  It never
calls a model, network service, plugin, or background process.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import re
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
MAX_EPISODES = 2000
MAX_EVALUATIONS = 100
REVIEW_DAYS = (1, 3, 7, 14, 30, 60, 90)
LESSON_STATES = {"candidate", "active", "quarantined", "retired"}
SPACE_RE = re.compile(r"\s+")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def clean_text(value: str, *, name: str, maximum: int) -> str:
    text = SPACE_RE.sub(" ", value.strip())
    if not text:
        raise ValueError(f"{name} must not be empty")
    if len(text) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    return text


def clean_tags(values: Iterable[str] | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = values.split(",")
    result: set[str] = set()
    for raw in values:
        tag = SPACE_RE.sub("-", raw.strip().lower())
        if tag:
            if len(tag) > 64:
                raise ValueError("tag exceeds 64 characters")
            result.add(tag)
    if len(result) > 20:
        raise ValueError("at most 20 tags are allowed")
    return sorted(result)


def bounded_number(value: float, *, name: str, low: float, high: float) -> float:
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def context_key(task_kind: str, tags: list[str], label: str) -> str:
    label = clean_text(label, name="context label", maximum=256)
    material = json.dumps(
        [task_kind.lower(), tags, label.lower()], separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def blank_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "updated_at": None,
        "episodes": [],
        "routes": {},
        "lessons": [],
    }


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.lock_path = Path(f"{self.path}.lock")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return blank_state()
        with self.path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported ledger schema version")
        return state

    @contextlib.contextmanager
    def _lock(self, timeout: float = 5.0):
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
                    raise TimeoutError(f"ledger is locked: {self.lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            with contextlib.suppress(FileNotFoundError):
                self.lock_path.unlink()

    def _save(self, state: dict[str, Any]) -> None:
        state["revision"] = int(state.get("revision", 0)) + 1
        state["updated_at"] = iso_now()
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
        with self._lock():
            state = self.load()
            result = operation(state)
            self._save(state)
            return result

    def status(self) -> dict[str, Any]:
        state = self.load()
        counts = {name: 0 for name in sorted(LESSON_STATES)}
        for lesson in state["lessons"]:
            counts[lesson["status"]] = counts.get(lesson["status"], 0) + 1
        return {
            "exists": self.path.exists(),
            "path": str(self.path),
            "schema_version": state["schema_version"],
            "revision": state["revision"],
            "episodes": len(state["episodes"]),
            "routes": len(state["routes"]),
            "lessons": counts,
            "updated_at": state["updated_at"],
        }

    def record(
        self,
        *,
        task_kind: str,
        resource: str,
        tags: Iterable[str] | str | None,
        context_label: str,
        success: bool,
        quality: float,
        latency_ms: float,
        note: str = "",
    ) -> dict[str, Any]:
        task_kind = clean_text(task_kind, name="task kind", maximum=96).lower()
        resource = clean_text(resource, name="resource", maximum=128)
        tags = clean_tags(tags)
        quality = bounded_number(quality, name="quality", low=0.0, high=1.0)
        latency_ms = bounded_number(latency_ms, name="latency", low=0.0, high=86_400_000.0)
        note = SPACE_RE.sub(" ", note.strip())
        if len(note) > 1000:
            raise ValueError("note exceeds 1000 characters")
        if not success:
            quality = 0.0
        episode = {
            "id": str(uuid.uuid4()),
            "task_kind": task_kind,
            "tags": tags,
            "context_key": context_key(task_kind, tags, context_label),
            "resource": resource,
            "success": bool(success),
            "quality": quality,
            "latency_ms": latency_ms,
            "note": note,
            "created_at": iso_now(),
        }

        def operation(state):
            state["episodes"].append(episode)
            state["episodes"] = state["episodes"][-MAX_EPISODES:]
            route_id = self._route_id(task_kind, resource)
            route = state["routes"].setdefault(
                route_id,
                {
                    "task_kind": task_kind,
                    "resource": resource,
                    "alpha": 1.0,
                    "beta": 1.0,
                    "uses": 0,
                    "mean_latency_ms": 0.0,
                    "updated_at": None,
                },
            )
            reward = quality if success else 0.0
            route["alpha"] += reward
            route["beta"] += 1.0 - reward
            route["uses"] += 1
            route["mean_latency_ms"] += (
                latency_ms - route["mean_latency_ms"]
            ) / route["uses"]
            route["updated_at"] = episode["created_at"]
            return episode

        return self.mutate(operation)

    @staticmethod
    def _route_id(task_kind: str, resource: str) -> str:
        return hashlib.sha256(f"{task_kind}\x1f{resource}".encode("utf-8")).hexdigest()

    def recommend(
        self,
        *,
        task_kind: str,
        candidates: Iterable[str],
        tags: Iterable[str] | str | None = None,
        target_latency_ms: float | None = None,
        exploration: float = 0.15,
    ) -> dict[str, Any]:
        task_kind = clean_text(task_kind, name="task kind", maximum=96).lower()
        tags = clean_tags(tags)
        candidates = sorted(
            {clean_text(item, name="candidate", maximum=128) for item in candidates}
        )
        if not candidates:
            raise ValueError("at least one available candidate is required")
        if target_latency_ms is not None:
            target_latency_ms = bounded_number(
                target_latency_ms, name="target latency", low=1.0, high=86_400_000.0
            )
        exploration = bounded_number(exploration, name="exploration", low=0.0, high=1.0)
        state = self.load()
        route_rows = []
        total_uses = sum(
            int(row["uses"])
            for row in state["routes"].values()
            if row["task_kind"] == task_kind
        )
        for resource in candidates:
            route = state["routes"].get(self._route_id(task_kind, resource))
            if route:
                alpha, beta, uses = route["alpha"], route["beta"], route["uses"]
                latency = route["mean_latency_ms"]
            else:
                alpha, beta, uses, latency = 1.0, 1.0, 0, None
            posterior = alpha / (alpha + beta)
            bonus = exploration * math.sqrt(math.log(total_uses + 2) / (uses + 1))
            quality_ucb = min(1.0, posterior + bonus)
            capacity = 1.0
            if target_latency_ms is not None and latency and latency > target_latency_ms:
                capacity = target_latency_ms / latency
            route_rows.append(
                {
                    "resource": resource,
                    "score": round(quality_ucb * capacity, 6),
                    "posterior_quality": round(posterior, 6),
                    "exploration_bonus": round(bonus, 6),
                    "latency_capacity": round(capacity, 6),
                    "mean_latency_ms": round(latency, 3) if latency is not None else None,
                    "uses": uses,
                }
            )
        route_rows.sort(key=lambda row: (-row["score"], row["resource"].lower()))
        return {
            "task_kind": task_kind,
            "available_candidates_only": True,
            "ranking": route_rows,
            "active_lessons": self.lessons(task_kind=task_kind, tags=tags, limit=5),
        }

    @staticmethod
    def _fingerprint(statement: str, task_kind: str, tags: list[str]) -> str:
        normalized = [statement.casefold(), task_kind.casefold(), tags]
        return hashlib.sha256(
            json.dumps(normalized, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def propose(
        self,
        *,
        statement: str,
        task_kind: str,
        tags: Iterable[str] | str | None = None,
    ) -> dict[str, Any]:
        statement = clean_text(statement, name="statement", maximum=1200)
        task_kind = clean_text(task_kind, name="task kind", maximum=96).lower()
        tags = clean_tags(tags)
        fingerprint = self._fingerprint(statement, task_kind, tags)
        now = iso_now()

        def operation(state):
            for lesson in state["lessons"]:
                if lesson["fingerprint"] == fingerprint and lesson["status"] != "retired":
                    return {**lesson, "deduplicated": True}
            lesson = {
                "id": str(uuid.uuid4()),
                "fingerprint": fingerprint,
                "statement": statement,
                "task_kind": task_kind,
                "tags": tags,
                "status": "candidate",
                "confidence": 0.5,
                "evaluations": [],
                "review_streak": 0,
                "review_interval_index": 0,
                "next_review_at": None,
                "created_at": now,
                "updated_at": now,
            }
            state["lessons"].append(lesson)
            return {**lesson, "deduplicated": False}

        return self.mutate(operation)

    @staticmethod
    def _lesson(state: dict[str, Any], lesson_id: str) -> dict[str, Any]:
        for lesson in state["lessons"]:
            if lesson["id"] == lesson_id:
                return lesson
        raise KeyError(f"lesson not found: {lesson_id}")

    @staticmethod
    def _stats(lesson: dict[str, Any]) -> dict[str, Any]:
        evaluations = lesson["evaluations"]
        passes = sum(1 for row in evaluations if row["passed"])
        failures = len(evaluations) - passes
        average = sum(row["score"] for row in evaluations) / len(evaluations) if evaluations else 0.0
        contexts = len({row["context_key"] for row in evaluations})
        eligible = passes >= 3 and contexts >= 2 and failures == 0 and average >= 0.8
        return {
            "passes": passes,
            "failures": failures,
            "distinct_contexts": contexts,
            "average_score": round(average, 6),
            "eligible_for_promotion": eligible,
            "missing": {
                "passes": max(0, 3 - passes),
                "distinct_contexts": max(0, 2 - contexts),
                "requires_zero_failures": failures > 0,
                "average_score_floor": 0.8,
            },
        }

    def evaluate(
        self,
        *,
        lesson_id: str,
        passed: bool,
        score: float,
        tags: Iterable[str] | str | None,
        context_label: str,
        note: str = "",
    ) -> dict[str, Any]:
        score = bounded_number(score, name="score", low=0.0, high=1.0)
        tags = clean_tags(tags)
        note = SPACE_RE.sub(" ", note.strip())
        if len(note) > 1000:
            raise ValueError("note exceeds 1000 characters")
        now = iso_now()

        def operation(state):
            lesson = self._lesson(state, lesson_id)
            if lesson["status"] == "retired":
                raise ValueError("retired lessons cannot be evaluated")
            evaluation = {
                "id": str(uuid.uuid4()),
                "passed": bool(passed),
                "score": score if passed else 0.0,
                "context_key": context_key(lesson["task_kind"], tags, context_label),
                "tags": tags,
                "note": note,
                "created_at": now,
            }
            lesson["evaluations"].append(evaluation)
            lesson["evaluations"] = lesson["evaluations"][-MAX_EVALUATIONS:]
            rewards = [row["score"] if row["passed"] else 0.0 for row in lesson["evaluations"]]
            lesson["confidence"] = round((1.0 + sum(rewards)) / (2.0 + len(rewards)), 6)
            if lesson["status"] == "active":
                if passed:
                    lesson["review_streak"] += 1
                    lesson["review_interval_index"] = min(
                        lesson["review_interval_index"] + 1, len(REVIEW_DAYS) - 1
                    )
                else:
                    lesson["review_streak"] = 0
                    lesson["review_interval_index"] = 0
                days = REVIEW_DAYS[lesson["review_interval_index"]]
                lesson["next_review_at"] = (
                    utc_now() + timedelta(days=days)
                ).isoformat().replace("+00:00", "Z")
                if len(lesson["evaluations"]) >= 2 and not any(
                    row["passed"] for row in lesson["evaluations"][-2:]
                ):
                    lesson["status"] = "quarantined"
                    lesson["next_review_at"] = None
            lesson["updated_at"] = now
            return {"lesson": lesson, "evaluation": evaluation, "stats": self._stats(lesson)}

        return self.mutate(operation)

    def promote(self, *, lesson_id: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("explicit approval is required for promotion")
        now = iso_now()

        def operation(state):
            lesson = self._lesson(state, lesson_id)
            if lesson["status"] != "candidate":
                raise ValueError("only candidate lessons can be promoted")
            stats = self._stats(lesson)
            if not stats["eligible_for_promotion"]:
                raise ValueError(f"promotion gates not met: {stats['missing']}")
            lesson["status"] = "active"
            lesson["review_streak"] = 0
            lesson["review_interval_index"] = 0
            lesson["next_review_at"] = (
                utc_now() + timedelta(days=REVIEW_DAYS[0])
            ).isoformat().replace("+00:00", "Z")
            lesson["updated_at"] = now
            return {"lesson": lesson, "stats": stats, "approved": True}

        return self.mutate(operation)

    def retire(self, *, lesson_id: str, approved: bool, note: str) -> dict[str, Any]:
        if not approved:
            raise PermissionError("explicit approval is required for retirement")
        note = clean_text(note, name="retirement note", maximum=1000)
        now = iso_now()

        def operation(state):
            lesson = self._lesson(state, lesson_id)
            if lesson["status"] == "retired":
                raise ValueError("lesson is already retired")
            lesson["status"] = "retired"
            lesson["next_review_at"] = None
            lesson["retirement_note"] = note
            lesson["updated_at"] = now
            return lesson

        return self.mutate(operation)

    def lessons(
        self,
        *,
        task_kind: str,
        tags: Iterable[str] | str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        task_kind = clean_text(task_kind, name="task kind", maximum=96).lower()
        tags = set(clean_tags(tags))
        limit = int(bounded_number(limit, name="limit", low=1, high=20))
        now = utc_now()
        rows = []
        for lesson in self.load()["lessons"]:
            if lesson["status"] != "active":
                continue
            lesson_tags = set(lesson["tags"])
            exact = 1.0 if lesson["task_kind"] == task_kind else 0.0
            overlap = len(tags & lesson_tags) / max(1, len(tags | lesson_tags))
            if exact == 0.0 and overlap == 0.0:
                continue
            due = parse_time(lesson["next_review_at"])
            freshness = 0.0 if due and due <= now else 0.1
            relevance = 2.0 * exact + overlap + lesson["confidence"] + freshness
            rows.append(
                {
                    "id": lesson["id"],
                    "statement": lesson["statement"],
                    "task_kind": lesson["task_kind"],
                    "tags": lesson["tags"],
                    "confidence": lesson["confidence"],
                    "next_review_at": lesson["next_review_at"],
                    "relevance": round(relevance, 6),
                }
            )
        rows.sort(key=lambda row: (-row["relevance"], row["id"]))
        return rows[:limit]

    def backlog(self) -> list[dict[str, Any]]:
        state = self.load()
        now = utc_now()
        items = []
        for lesson in state["lessons"]:
            stats = self._stats(lesson)
            if lesson["status"] == "active":
                due = parse_time(lesson["next_review_at"])
                if due and due <= now:
                    items.append({"priority": 1, "kind": "rehearsal", "lesson_id": lesson["id"]})
            elif lesson["status"] == "quarantined":
                items.append({"priority": 2, "kind": "root-cause", "lesson_id": lesson["id"]})
            elif lesson["status"] == "candidate":
                items.append(
                    {
                        "priority": 3,
                        "kind": "candidate-evidence",
                        "lesson_id": lesson["id"],
                        "missing": stats["missing"],
                    }
                )
        for route in state["routes"].values():
            if route["uses"] < 3:
                items.append(
                    {
                        "priority": 4,
                        "kind": "route-exploration",
                        "task_kind": route["task_kind"],
                        "resource": route["resource"],
                        "uses": route["uses"],
                    }
                )
        failures: dict[str, list[dict[str, Any]]] = {}
        for episode in state["episodes"]:
            if not episode["success"]:
                failures.setdefault(episode["task_kind"], []).append(episode)
        for task_kind, rows in failures.items():
            if len(rows) >= 2:
                items.append(
                    {
                        "priority": 2,
                        "kind": "recurring-failure",
                        "task_kind": task_kind,
                        "failures": len(rows),
                        "resources": sorted({row["resource"] for row in rows}),
                    }
                )
        return sorted(items, key=lambda row: (row["priority"], row.get("lesson_id", ""), row.get("resource", "")))

    def audit(self) -> dict[str, Any]:
        state = self.load()
        errors: list[str] = []
        ids: set[str] = set()
        fingerprints: dict[str, str] = {}
        for lesson in state.get("lessons", []):
            if lesson.get("id") in ids:
                errors.append(f"duplicate lesson id: {lesson.get('id')}")
            ids.add(lesson.get("id"))
            if lesson.get("status") not in LESSON_STATES:
                errors.append(f"invalid lesson state: {lesson.get('status')}")
            fingerprint = lesson.get("fingerprint")
            if lesson.get("status") != "retired" and fingerprint in fingerprints:
                errors.append(f"duplicate active fingerprint: {fingerprint}")
            fingerprints[fingerprint] = lesson.get("id")
            if not 0.0 <= float(lesson.get("confidence", -1)) <= 1.0:
                errors.append(f"invalid confidence: {lesson.get('id')}")
        for route_id, route in state.get("routes", {}).items():
            expected = self._route_id(route.get("task_kind", ""), route.get("resource", ""))
            if route_id != expected:
                errors.append(f"route key mismatch: {route_id}")
            if route.get("alpha", 0) <= 0 or route.get("beta", 0) <= 0 or route.get("uses", -1) < 0:
                errors.append(f"invalid route evidence: {route_id}")
        return {
            "ok": not errors,
            "errors": errors,
            "schema_version": state.get("schema_version"),
            "revision": state.get("revision"),
            "episodes": len(state.get("episodes", [])),
            "routes": len(state.get("routes", {})),
            "lessons": len(state.get("lessons", [])),
        }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument(
        "--ledger",
        default=os.environ.get("NERO_LEARNING_LEDGER", "~/.nero/continual-learning.json"),
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("status")

    record = commands.add_parser("record")
    record.add_argument("--task-kind", required=True)
    record.add_argument("--resource", required=True)
    record.add_argument("--tags", default="")
    record.add_argument("--context-label", required=True)
    outcome = record.add_mutually_exclusive_group(required=True)
    outcome.add_argument("--success", action="store_true")
    outcome.add_argument("--failure", action="store_true")
    record.add_argument("--quality", type=float, required=True)
    record.add_argument("--latency-ms", type=float, required=True)
    record.add_argument("--note", default="")

    propose = commands.add_parser("propose")
    propose.add_argument("--statement", required=True)
    propose.add_argument("--task-kind", required=True)
    propose.add_argument("--tags", default="")

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--lesson-id", required=True)
    result = evaluate.add_mutually_exclusive_group(required=True)
    result.add_argument("--passed", action="store_true")
    result.add_argument("--failed", action="store_true")
    evaluate.add_argument("--score", type=float, required=True)
    evaluate.add_argument("--tags", default="")
    evaluate.add_argument("--context-label", required=True)
    evaluate.add_argument("--note", default="")

    promote = commands.add_parser("promote")
    promote.add_argument("--lesson-id", required=True)
    promote.add_argument("--approved", action="store_true")

    retire = commands.add_parser("retire")
    retire.add_argument("--lesson-id", required=True)
    retire.add_argument("--approved", action="store_true")
    retire.add_argument("--note", required=True)

    recommend = commands.add_parser("recommend")
    recommend.add_argument("--task-kind", required=True)
    recommend.add_argument("--candidates", required=True)
    recommend.add_argument("--tags", default="")
    recommend.add_argument("--target-latency-ms", type=float)
    recommend.add_argument("--exploration", type=float, default=0.15)

    lessons = commands.add_parser("lessons")
    lessons.add_argument("--task-kind", required=True)
    lessons.add_argument("--tags", default="")
    lessons.add_argument("--limit", type=int, default=5)
    commands.add_parser("backlog")
    commands.add_parser("audit")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    ledger = Ledger(args.ledger)
    try:
        if args.command == "status":
            output = ledger.status()
        elif args.command == "record":
            output = ledger.record(
                task_kind=args.task_kind,
                resource=args.resource,
                tags=args.tags,
                context_label=args.context_label,
                success=args.success,
                quality=args.quality,
                latency_ms=args.latency_ms,
                note=args.note,
            )
        elif args.command == "propose":
            output = ledger.propose(statement=args.statement, task_kind=args.task_kind, tags=args.tags)
        elif args.command == "evaluate":
            output = ledger.evaluate(
                lesson_id=args.lesson_id,
                passed=args.passed,
                score=args.score,
                tags=args.tags,
                context_label=args.context_label,
                note=args.note,
            )
        elif args.command == "promote":
            output = ledger.promote(lesson_id=args.lesson_id, approved=args.approved)
        elif args.command == "retire":
            output = ledger.retire(lesson_id=args.lesson_id, approved=args.approved, note=args.note)
        elif args.command == "recommend":
            output = ledger.recommend(
                task_kind=args.task_kind,
                candidates=args.candidates.split(","),
                tags=args.tags,
                target_latency_ms=args.target_latency_ms,
                exploration=args.exploration,
            )
        elif args.command == "lessons":
            output = ledger.lessons(task_kind=args.task_kind, tags=args.tags, limit=args.limit)
        elif args.command == "backlog":
            output = ledger.backlog()
        else:
            output = ledger.audit()
        print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except (KeyError, PermissionError, TimeoutError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
