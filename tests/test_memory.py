"""Unit tests for the memory subsystem's pure logic.

Run directly:  python tests/test_memory.py
Or with pytest: pytest tests/
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import memory


def test_decay_factor():
    now = datetime.now(timezone.utc).isoformat()
    assert abs(memory.decay_factor(now, 30) - 1.0) < 0.01
    two_hl = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    assert memory.decay_factor(two_hl, 30) < 0.30  # ~0.25 after two half-lives
    assert memory.decay_factor(now, 0) == 1.0       # guard against div-by-zero


def test_cosine():
    assert abs(memory.cosine([1, 2, 3], [1, 2, 3]) - 1.0) < 1e-6
    assert abs(memory.cosine([1, 0], [0, 1])) < 1e-6
    assert memory.cosine(None, [1, 2]) == 0.0
    assert memory.cosine([1, 2], [1, 2, 3]) == 0.0  # length mismatch is safe


def test_parse_memories():
    fenced = '```json\n[{"content":"likes tea","type":"preference"}]\n```'
    out = memory.parse_memories(fenced)
    assert len(out) == 1 and out[0]["type"] == "preference"
    assert memory.parse_memories("") == []
    assert memory.parse_memories("no json here") == []
    # Unknown type is coerced to a valid one.
    assert memory.parse_memories('[{"content":"x","type":"weird"}]')[0]["type"] == "semantic"
    # Items without content are dropped.
    assert memory.parse_memories('[{"type":"semantic"}]') == []


def test_keyword_overlap():
    assert memory._keyword_overlap("dark mode theme", "prefers dark mode") > 0
    assert memory._keyword_overlap("", "anything") == 0.0


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} unit tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
