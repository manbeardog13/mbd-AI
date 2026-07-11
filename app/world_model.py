"""Nero's World Model — a live, structured picture of what her person is doing.

This is the substrate of *continuity* (the project's North Star): instead of
re-inferring context every conversation, Nero keeps a small evolving record
(current project, task, blockers, next steps…) that she updates in the
background after each exchange and reads at the start of every reply. So she
resumes already knowing where you left off.

Storage lives in `app/db.py` (the `world_state` key/value table); this module is
the cognitive layer — updating the picture and rendering it for the prompt.
Synchronous and pure-Python; the web layer calls it from a worker thread.
"""
from __future__ import annotations

import json
import logging
import re
import threading

from . import db
from .config import Config
from .llm import complete_chat
from .memory import _first_balanced_json, strip_think

log = logging.getLogger("nero.world")

METRICS: dict[str, float] = {"updates": 0, "fields_changed": 0}
# Serializes the in-process metric counters across concurrent background
# updates (the world_state writes themselves are serialized by SQLite).
_lock = threading.RLock()


def _bump(key: str, n: float = 1) -> None:
    with _lock:
        METRICS[key] = METRICS.get(key, 0) + n

# The fields Nero tracks, in the order they read best.
KEY_LABELS = {
    "current_project": "Current project",
    "current_task": "Current task",
    "working_context": "Working context",
    "blockers": "Blockers",
    "next_steps": "Next",
    "recent_focus": "Recent focus",
}
STANDARD_KEYS = list(KEY_LABELS.keys())

# Structured-output schema (Ollama `format`). Without this, a small reasoning
# model reasons in prose and never emits the object — so the world would never
# update on a real machine. The grammar restricts output to a JSON object of the
# known string fields (all optional, so "only what changed" — or {} — is valid).
WORLD_FORMAT = {
    "type": "object",
    "properties": {k: {"type": "string"} for k in STANDARD_KEYS},
    "additionalProperties": False,
}

_WORLD_SYSTEM = (
    "You maintain a compact, living picture of what a person (the user) is "
    "currently working on, so their AI has continuity across conversations. You "
    "are given the current picture and the latest exchange. Respond with ONLY a "
    "JSON object of the fields that should CHANGE, using these keys where they "
    "apply: current_project, current_task, working_context, blockers, next_steps, "
    "recent_focus. Values are short phrases. Include a field only if it should "
    "change; set a field to \"\" to clear it. If nothing meaningful changed, "
    "respond with {}."
)


def _user_prompt(owner: str, state: dict, user_text: str, assistant_text: str) -> str:
    current = json.dumps(state, ensure_ascii=False) if state else "{}"
    return (
        f"The user is {owner}.\n\n"
        f"Current picture:\n{current}\n\n"
        f"{owner} said:\n{user_text}\n\n"
        f"Nero replied:\n{assistant_text}\n\n"
        "Output the JSON object of fields to update (only what changed)."
    )


def _extract_json_object(text: str) -> dict | None:
    """Pull the first balanced {...} JSON object out of a model reply."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        whole = json.loads(text)
        if isinstance(whole, dict):
            return whole
    except json.JSONDecodeError:
        pass

    value = _first_balanced_json(text, "{", "}")
    return value if isinstance(value, dict) else None


def _clean_value(value) -> str:
    """Normalize a field value to a single short line.

    Collapses all internal whitespace/newlines to single spaces (so an embedded
    newline can't break render()'s "- Label: value" contract or inject an
    unlabelled line into the system prompt) and caps the length. A structured
    value is rendered as readable JSON rather than a Python repr.
    """
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return " ".join(str(value).split())[:200]


def parse_world_updates(raw: str) -> dict:
    """Parse the model's JSON object of world-state changes (tolerant of prose)."""
    data = _extract_json_object(strip_think(raw or ""))
    if not isinstance(data, dict):
        return {}
    updates: dict = {}
    for key, value in data.items():
        key = str(key).strip().lower().replace(" ", "_")
        if key not in STANDARD_KEYS:
            continue  # keep the world model clean and predictable
        if value is None:
            updates[key] = ""  # explicit clear
        else:
            updates[key] = _clean_value(value)
    return updates


def render(state: dict, owner: str) -> str:
    """Render the world state as a prompt block, or '' if empty."""
    lines = [
        f"- {KEY_LABELS[k]}: {state[k]}"
        for k in STANDARD_KEYS
        if state.get(k)
    ]
    if not lines:
        return ""
    return (
        f"Your live picture of what {owner} is working on right now — use it for "
        "continuity, and keep refining it as you learn more:\n" + "\n".join(lines)
    )


def update(cfg: Config, user_text: str, assistant_text: str) -> dict:
    """Update the world model from the latest exchange. Best-effort; never raises."""
    summary = {"updated": 0, "skipped": False}
    if not cfg.world_model_enabled or not user_text.strip():
        summary["skipped"] = True
        return summary
    try:
        model = cfg.reflection_model or cfg.model  # a small model is plenty
        keep_alive = "0" if model != cfg.model else None
        state = db.get_world()
        raw = complete_chat(
            cfg,
            [
                {"role": "system", "content": _WORLD_SYSTEM},
                {"role": "user", "content": _user_prompt(
                    cfg.owner_name, state, user_text, assistant_text)},
            ],
            temperature=0.0,
            model=model,
            num_predict=300,
            keep_alive=keep_alive,
            think=False,
            response_format=WORLD_FORMAT,  # grammar-forces the JSON object
        )
        updates = parse_world_updates(raw)
        if updates:
            db.upsert_world(updates)
            _bump("updates", 1)
            _bump("fields_changed", len(updates))
            summary["updated"] = len(updates)
            log.info("world update -> %s", list(updates.keys()))
    except Exception as exc:  # noqa: BLE001 - never break chat
        log.warning("world update failed: %s", exc)
        summary["skipped"] = True
    return summary
