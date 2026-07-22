"""voice.local_tts.engine_health — "should we attempt this engine right now?"

A **lightweight state tracker** — and deliberately nothing more. It is NOT a
monitoring daemon, an engine manager, a recovery executor, a VRAM controller, or a
second capability graph. Given an engine's recent runtime outcomes, it answers one
question: *should the Voice Manager attempt this engine now, or is it cooling down
after failures?*

Backoff is a **protection mechanism, not intelligence** — predictable, no learning,
no prediction: after a failure the engine waits a growing (capped) cooldown before
it's eligible again; a success clears the failure history.

**Boundaries (locked):**
- Voice-only. This module imports **nothing** from `app/` — not the agent loop,
  the security gate, the Capability Registry, the Action Journal, or any memory
  system.
- It makes **no routing decisions**. Routing is the future Voice Manager's job,
  combining this ("healthy enough to attempt now?") with the Voice Capability
  Graph ("can this voice perform with the available engine?"). Two separate
  questions, two separate systems.
- `snapshot()` is **Voice Telemetry**, never the Action Journal.

Distinct from `base.EngineHealth`: that is an engine's per-call *self-report*;
this is the cross-time *attempt/cooldown policy* the Manager consults.

Lifecycle:  UNKNOWN → AVAILABLE → FAILING → COOLDOWN → RECOVERING → AVAILABLE
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class HealthStatus(str, Enum):
    UNKNOWN = "unknown"        # no outcomes recorded yet
    AVAILABLE = "available"    # last outcome healthy
    FAILING = "failing"        # a failure was just recorded (base state)
    COOLDOWN = "cooldown"      # failed recently, within the backoff window — do not attempt
    RECOVERING = "recovering"  # cooldown expired, eligible to attempt again (unconfirmed)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


@dataclass
class EngineHealthRecord:
    """The lightweight operational state of one engine. No unnecessary metadata."""

    engine_name: str
    state: HealthStatus = HealthStatus.UNKNOWN   # stored base state: UNKNOWN | AVAILABLE | FAILING
    last_check: datetime | None = None
    last_success: datetime | None = None
    last_failure: datetime | None = None
    failure_reason: str = ""
    consecutive_failures: int = 0
    retry_after: datetime | None = None          # before this, do not attempt (cooldown)

    def status(self, now: datetime | None = None) -> HealthStatus:
        """The effective status at `now`: FAILING resolves to COOLDOWN (still
        waiting) or RECOVERING (window expired, eligible)."""
        now = now or _utcnow()
        if self.state is HealthStatus.FAILING:
            if self.retry_after and now < self.retry_after:
                return HealthStatus.COOLDOWN
            return HealthStatus.RECOVERING
        return self.state

    def cooldown_remaining(self, now: datetime | None = None) -> float:
        now = now or _utcnow()
        if self.retry_after and now < self.retry_after:
            return (self.retry_after - now).total_seconds()
        return 0.0

    def as_dict(self, now: datetime | None = None) -> dict:
        return {
            "engine_name": self.engine_name,
            "status": self.status(now).value,
            "last_check": _iso(self.last_check),
            "last_success": _iso(self.last_success),
            "last_failure": _iso(self.last_failure),
            "failure_reason": self.failure_reason,
            "consecutive_failures": self.consecutive_failures,
            "retry_after": _iso(self.retry_after),
            "cooldown_remaining_s": round(self.cooldown_remaining(now), 3),
        }


class EngineHealthCache:
    """Per-engine outcome tracker that gates attempts with a predictable backoff.

    One record per engine; pure Python; no threads, no engine calls, no `app/`
    imports, no routing. The whole surface is: record an outcome, ask
    `should_attempt`.
    """

    def __init__(self, base_cooldown_s: float = 5.0, max_cooldown_s: float = 300.0) -> None:
        self._records: dict[str, EngineHealthRecord] = {}
        self._base = max(0.0, float(base_cooldown_s))
        self._max = max(self._base, float(max_cooldown_s))

    def _rec(self, engine_name: str) -> EngineHealthRecord:
        r = self._records.get(engine_name)
        if r is None:
            r = EngineHealthRecord(engine_name=engine_name)
            self._records[engine_name] = r
        return r

    def _backoff_seconds(self, consecutive_failures: int) -> float:
        """base * 2^(n-1), capped at max. Predictable protection — never learned."""
        n = max(1, consecutive_failures)
        try:
            grown = self._base * (2 ** (n - 1))
        except OverflowError:  # absurdly many failures — just use the cap
            grown = self._max
        return min(self._max, grown)

    def record_success(self, engine_name: str, *, now: datetime | None = None) -> None:
        """A success clears failure history (recovery) and marks the engine healthy."""
        now = now or _utcnow()
        r = self._rec(engine_name)
        r.state = HealthStatus.AVAILABLE
        r.consecutive_failures = 0
        r.retry_after = None
        r.failure_reason = ""
        r.last_success = now
        r.last_check = now

    def record_failure(self, engine_name: str, reason: str = "", *, now: datetime | None = None) -> None:
        """Record a failure and start (or extend) the cooldown via capped backoff."""
        now = now or _utcnow()
        r = self._rec(engine_name)
        r.state = HealthStatus.FAILING
        r.consecutive_failures += 1
        r.failure_reason = (reason or "")[:200]
        r.last_failure = now
        r.last_check = now
        r.retry_after = now + timedelta(seconds=self._backoff_seconds(r.consecutive_failures))

    def should_attempt(self, engine_name: str, *, now: datetime | None = None) -> bool:
        """Should the Voice Manager attempt this engine now? False only in COOLDOWN.

        An unknown engine is optimistically attemptable — the attempt itself
        records the outcome. This never makes a routing decision; it answers a
        single yes/no about one engine.
        """
        now = now or _utcnow()
        r = self._records.get(engine_name)
        if r is None:
            return True
        return r.status(now) is not HealthStatus.COOLDOWN

    def status(self, engine_name: str, *, now: datetime | None = None) -> HealthStatus:
        r = self._records.get(engine_name)
        return r.status(now) if r is not None else HealthStatus.UNKNOWN

    def get(self, engine_name: str) -> EngineHealthRecord | None:
        return self._records.get(engine_name)

    def snapshot(self, *, now: datetime | None = None) -> list[dict]:
        """Telemetry view of every tracked engine (Voice Telemetry, never the Journal)."""
        now = now or _utcnow()
        return [r.as_dict(now) for r in self._records.values()]
