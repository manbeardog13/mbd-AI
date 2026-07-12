"""`git.status` — the first capability: the repo's working-tree state.

Deterministic and read-only, so it's `SAFE` and runs without confirmation. This
is the Principle of Least Intelligence in a capability: the branch and the list
of changed files are *knowable*, so we read them from git rather than asking the
model to guess. The model calls this and reasons about the *result*.
"""
from __future__ import annotations

import subprocess

from ..registry import Context, Result
from ...security.gate import RiskClass


def _git(args: list[str], cwd: str) -> tuple[int, str, str]:
    """Run a git command in `cwd`. Returns (returncode, stdout, stderr)."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


class GitStatus:
    name = "git.status"
    description = (
        "Report the git working-tree status of the project: the current branch "
        "and the list of changed, staged, and untracked files. Read-only; takes "
        "no arguments."
    )
    args_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    risk = RiskClass.SAFE
    provider = "builtin"

    def execute(self, args: dict, ctx: Context) -> Result:
        cwd = ctx.allowed_dirs[0] if ctx.allowed_dirs else "."
        try:
            rc, branch, err = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
            if rc != 0:
                return Result(False, f"Not a git repository (or git failed): {err}")
            _, porcelain, _ = _git(["status", "--porcelain"], cwd)
        except FileNotFoundError:
            return Result(False, "git is not installed or not on PATH.")
        except subprocess.TimeoutExpired:
            return Result(False, "git timed out.")
        except Exception as exc:  # noqa: BLE001 - contained; the loop observes it
            return Result(False, f"git.status failed: {exc}")

        files = [ln for ln in porcelain.splitlines() if ln.strip()]
        if files:
            listing = "\n".join(files)
            output = f"On branch {branch}. {len(files)} change(s):\n{listing}"
        else:
            output = f"On branch {branch}. Working tree clean."
        return Result(True, output, {"branch": branch, "changed": len(files)})
