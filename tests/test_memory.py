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


def test_strip_think_then_parse():
    # A <think> block (even with brackets inside) must be removed before parsing,
    # so reflection still recovers the real JSON array.
    raw = '<think>Let me consider [option A] vs [option B]…</think>\n[{"content":"Toni codes in Rust","type":"semantic"}]'
    assert memory.strip_think(raw).startswith("[")
    out = memory.parse_memories(raw)
    assert len(out) == 1 and out[0]["content"] == "Toni codes in Rust"


def test_parse_trailing_brackets():
    # A valid array followed by bracketed prose must still parse (greedy-regex bug).
    tricky = '[{"content":"Toni plays guitar","type":"semantic"}]\nNote: [nothing else durable]'
    out = memory.parse_memories(tricky)
    assert len(out) == 1 and out[0]["content"] == "Toni plays guitar"


def test_score_scale_is_unified():
    cfg = type("C", (), {"memory_half_life_days": 30.0})()
    now = datetime.now(timezone.utc).isoformat()
    embedded_relevant = {"confidence": 0.7, "importance": 0.5, "last_reinforced": now,
                         "content": "prefers Python", "embedding": [0, 1, 0]}
    nonembedded_irrelevant = {"confidence": 0.7, "importance": 0.5, "last_reinforced": now,
                              "content": "weather was nice", "embedding": None}
    q = [0, 1, 0]  # query resembles the embedded memory
    # An embedded, relevant memory must outrank a non-embedded irrelevant one.
    assert memory.score_memory(embedded_relevant, cfg, "language", q) > \
        memory.score_memory(nonembedded_irrelevant, cfg, "language", q)


def test_dimension_mismatch_falls_back():
    cfg = type("C", (), {"memory_half_life_days": 30.0})()
    now = datetime.now(timezone.utc).isoformat()
    # Stored embedding is 2-dim (old model), query is 4-dim (new model): must not
    # crash and must fall back to lexical relevance (> 0 because "hiking" overlaps).
    mem = {"confidence": 0.8, "importance": 0.5, "last_reinforced": now,
           "content": "enjoys hiking on weekends", "embedding": [1, 0]}
    score = memory.score_memory(mem, cfg, "what hiking does Toni enjoy", [0.1, 0.2, 0.3, 0.4])
    assert score > 0


def test_reflection_enabled_blank_defaults_true():
    import tempfile
    from app import config as cfgmod
    tmp = Path(tempfile.mkdtemp()) / "config.yaml"
    tmp.write_text("reflection_enabled:\nmodel: qwen3:14b\n", encoding="utf-8")
    old = cfgmod.CONFIG_PATH
    cfgmod.CONFIG_PATH = tmp
    try:
        assert cfgmod.load_config().reflection_enabled is True
    finally:
        cfgmod.CONFIG_PATH = old


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} unit tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
