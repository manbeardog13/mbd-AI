"""Unit tests for the World Model's pure logic.

Run directly:  python tests/test_world_model.py
Or with pytest: pytest tests/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import world_model


def test_parse_keeps_known_keys_only():
    updates = world_model.parse_world_updates(
        '{"current_task":"ship phase 2","unknown_key":"x","next_steps":"review"}'
    )
    assert updates["current_task"] == "ship phase 2"
    assert updates["next_steps"] == "review"
    assert "unknown_key" not in updates


def test_parse_survives_think_and_prose():
    raw = ('<think>Let me weigh {option A} vs {option B}</think>\n'
           'Here is the update: {"current_project":"Nero"} and nothing else.')
    updates = world_model.parse_world_updates(raw)
    assert updates == {"current_project": "Nero"}


def test_parse_fenced_json():
    updates = world_model.parse_world_updates(
        '```json\n{"blockers":"VRAM contention"}\n```'
    )
    assert updates["blockers"] == "VRAM contention"


def test_parse_junk_is_empty():
    assert world_model.parse_world_updates("no json here") == {}
    assert world_model.parse_world_updates("") == {}
    assert world_model.parse_world_updates(None) == {}


def test_parse_null_clears_field():
    # A null value is an explicit "clear this field" instruction.
    updates = world_model.parse_world_updates('{"blockers":null}')
    assert updates["blockers"] == ""


def test_parse_key_normalization():
    # Spaces / casing in a key must map onto the standard snake_case key.
    updates = world_model.parse_world_updates('{"Current Project":"Nero"}')
    assert updates.get("current_project") == "Nero"


def test_parse_truncates_long_values():
    long = "x" * 500
    updates = world_model.parse_world_updates('{"current_task":"' + long + '"}')
    assert len(updates["current_task"]) == 200


def test_parse_ignores_non_dict_json():
    # A JSON array (not an object) is not a valid update payload.
    assert world_model.parse_world_updates('["a","b"]') == {}


def test_render_empty_is_blank():
    assert world_model.render({}, "Toni") == ""
    # A state with only empty/blank values is also blank.
    assert world_model.render({"blockers": ""}, "Toni") == ""


def test_render_includes_labels_and_owner():
    rendered = world_model.render(
        {"current_project": "Nero", "next_steps": "adversarial review"}, "Toni"
    )
    assert "Current project: Nero" in rendered
    assert "Next: adversarial review" in rendered
    assert "Toni" in rendered


def test_render_orders_by_key_labels():
    # Fields render in KEY_LABELS order regardless of dict insertion order.
    state = {"next_steps": "review", "current_project": "Nero"}
    rendered = world_model.render(state, "Toni")
    assert rendered.index("Current project") < rendered.index("Next:")


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} unit tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
