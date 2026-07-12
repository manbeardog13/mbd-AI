"""Executive Memory — Nero's working-state register (ADR-0008).

A small, always-current answer to "what am *I* doing now, and where?" — distinct
from long-term memory (facts over time) and the World Model (what's true about
Toni). Six fields, deliberately: a register, not a log.

  goal · project · branch · task · blocker · next_action

The deterministic fields — `project` and `branch` — are **observed** from the
filesystem and git on every read, never reasoned or stored-then-trusted (the
Principle of Least Intelligence: read the branch, don't ask the model for it).
The intent fields — `goal`, `task`, `blocker`, `next_action` — are set by the
agent as work progresses and persisted in the `executive_state` table.

Reading this register is what makes *"Continue."* cheap: the state is looked up,
not reconstructed from history. Pure and synchronous.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, fields
from pathlib import Path

from .. import db

# The fields the register tracks, in the order they read best.
EXEC_KEYS = ("goal", "project", "branch", "task", "blocker", "next_action")
# Observed fresh from the machine each read — never taken from storage.
OBSERVED_KEYS = ("project", "branch")
# Set by the agent and persisted — the "intent" the loop carries across steps.
INTENT_KEYS = tuple(k for k in EXEC_KEYS if k not in OBSERVED_KEYS)

_LABELS = {
    "goal": "Goal",
    "project": "Project",
    "branch": "Branch",
    "task": "Task",
    "blocker": "Blocker",
    "next_action": "Next action",
}


@dataclass
class WorkingState:
    goal: str | None = None
    project: str | None = None
    branch: str | None = None
    task: str | None = None
    blocker: str | None = None
    next_action: str | None = None

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _git_branch(project_dir: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_dir, capture_output=True, text=True, timeout=10,
        )
        if proc.returncode == 0:
            branch = proc.stdout.strip()
            return branch or None
    except Exception:  # noqa: BLE001 - not a repo / no git / timeout ⇒ no branch
        return None
    return None


def observe(project_dir: str) -> dict:
    """The deterministic fields, read fresh from the machine (never guessed)."""
    project = None
    try:
        project = Path(project_dir).resolve().name or None
    except Exception:  # noqa: BLE001
        project = None
    return {"project": project, "branch": _git_branch(project_dir)}


def read(project_dir: str) -> WorkingState:
    """The current working state: stored intent, plus freshly-observed reality.

    Observed fields always win over anything stored — the branch on disk is the
    truth, not a value we wrote earlier and might now be stale.
    """
    stored = db.get_executive()
    merged = {k: (stored.get(k) or None) for k in EXEC_KEYS}
    merged.update(observe(project_dir))
    return WorkingState(**{k: merged.get(k) for k in EXEC_KEYS})


def update(fields_in: dict) -> dict:
    """Persist intent fields (goal/task/blocker/next_action). Returns what changed.

    Observed fields (project/branch) are ignored here — they're never stored,
    only observed. Unknown keys are dropped to keep the register clean.
    """
    updates = {
        k: ("" if v is None else str(v).strip())
        for k, v in (fields_in or {}).items()
        if k in INTENT_KEYS
    }
    if updates:
        db.upsert_executive(updates)
    return updates


def clear() -> None:
    """Reset the register — used when a new goal begins."""
    db.clear_executive()


def render(state: WorkingState) -> str:
    """Render the register as a prompt block, or '' if nothing is set."""
    lines = [
        f"- {_LABELS[k]}: {getattr(state, k)}"
        for k in EXEC_KEYS
        if getattr(state, k)
    ]
    if not lines:
        return ""
    return "Your current working state (what you're doing right now):\n" + "\n".join(lines)
