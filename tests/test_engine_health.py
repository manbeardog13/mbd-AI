"""Voice Platform tests — Stage 3: the Engine Health Cache (model-independent).

Deterministic: an injected clock (a fixed base time + timedelta) drives all
cooldown/recovery behaviour — no sleeps. Proves the lifecycle
UNKNOWN → AVAILABLE → FAILING → COOLDOWN → RECOVERING → AVAILABLE, and the
invariants Toni required (zero deps, engine isolation, recovery, no app/ imports).

Run directly:  python tests/test_engine_health.py
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice.local_tts.engine_health import (
    EngineHealthCache, EngineHealthRecord, HealthStatus,
)

T0 = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


def _at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def test_unknown_engine_is_attemptable():
    c = EngineHealthCache()
    assert c.should_attempt("kokoro", now=T0) is True
    assert c.status("kokoro", now=T0) == HealthStatus.UNKNOWN


def test_healthy_after_success():
    c = EngineHealthCache()
    c.record_success("kokoro", now=T0)
    assert c.status("kokoro", now=T0) == HealthStatus.AVAILABLE
    assert c.should_attempt("kokoro", now=T0) is True


def test_failure_enters_cooldown_and_blocks_attempts():
    c = EngineHealthCache(base_cooldown_s=5.0)
    c.record_failure("kokoro", "no audio", now=T0)
    # within the 5s cooldown window
    assert c.status("kokoro", now=_at(2)) == HealthStatus.COOLDOWN
    assert c.should_attempt("kokoro", now=_at(2)) is False
    # repeated queries during cooldown stay blocked — no re-probe, cached decision
    assert c.should_attempt("kokoro", now=_at(4)) is False
    assert c.get("kokoro").failure_reason == "no audio"


def test_becomes_eligible_after_cooldown():
    c = EngineHealthCache(base_cooldown_s=5.0)
    c.record_failure("kokoro", now=T0)
    assert c.should_attempt("kokoro", now=_at(6)) is True           # window passed
    assert c.status("kokoro", now=_at(6)) == HealthStatus.RECOVERING


def test_recovery_clears_failure_history():
    c = EngineHealthCache(base_cooldown_s=5.0)
    c.record_failure("kokoro", "boom", now=T0)
    c.record_success("kokoro", now=_at(6))                          # recovered
    r = c.get("kokoro")
    assert r.status(_at(6)) == HealthStatus.AVAILABLE
    assert r.consecutive_failures == 0 and r.retry_after is None and r.failure_reason == ""


def test_backoff_grows_and_is_capped():
    c = EngineHealthCache(base_cooldown_s=5.0, max_cooldown_s=30.0)
    c.record_failure("e", now=T0)
    assert abs(c.get("e").cooldown_remaining(T0) - 5.0) < 0.01      # 1st: base
    c.record_failure("e", now=T0)
    assert abs(c.get("e").cooldown_remaining(T0) - 10.0) < 0.01     # 2nd: base*2
    c.record_failure("e", now=T0)
    assert abs(c.get("e").cooldown_remaining(T0) - 20.0) < 0.01     # 3rd: base*4
    for _ in range(10):
        c.record_failure("e", now=T0)
    assert c.get("e").cooldown_remaining(T0) <= 30.0                # capped, never runaway


def test_one_broken_engine_does_not_affect_another():
    c = EngineHealthCache(base_cooldown_s=5.0)
    c.record_failure("kokoro", now=T0)
    c.record_success("mms_hr", now=T0)
    assert c.should_attempt("kokoro", now=_at(1)) is False          # kokoro cooling
    assert c.should_attempt("mms_hr", now=_at(1)) is True           # unaffected
    assert c.status("mms_hr", now=_at(1)) == HealthStatus.AVAILABLE


def test_works_with_zero_installed_tts_packages():
    # Pure Python; no engine/model import — constructs and operates standalone.
    c = EngineHealthCache()
    c.record_failure("xtts", "package missing", now=T0)
    c.record_success("kokoro", now=T0)
    assert c.should_attempt("xtts", now=T0) is False
    assert c.should_attempt("kokoro", now=T0) is True


def test_snapshot_is_telemetry_and_corruption_safe():
    c = EngineHealthCache(base_cooldown_s=5.0)
    c.record_failure("kokoro", now=T0)
    snap = {row["engine_name"]: row for row in c.snapshot(now=_at(2))}
    assert snap["kokoro"]["status"] == "cooldown" and snap["kokoro"]["consecutive_failures"] == 1
    # a hand-corrupted record (FAILING with no retry_after) must not crash
    bad = EngineHealthRecord("weird", state=HealthStatus.FAILING, retry_after=None)
    assert bad.status(T0) == HealthStatus.RECOVERING and isinstance(bad.as_dict(T0), dict)


def test_no_forbidden_imports():
    # Structural boundary: the module must not reach into the executive path.
    src = (Path(__file__).resolve().parent.parent
           / "voice" / "local_tts" / "engine_health.py").read_text(encoding="utf-8")
    for forbidden in ("app.security", "app.capabilities", "app.agent",
                      "app.memory", "from app", "import app"):
        assert forbidden not in src, f"engine_health.py must not reference {forbidden!r}"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} engine-health tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
