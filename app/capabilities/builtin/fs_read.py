"""`fs.read` — read a text file inside the project jail.

SAFE and read-only: returns a file's contents so the agent can reason about it.
A `path` that escapes the project jail is escalated to a confirmable action by the
security gate (ADR-0005), so this capability only ever runs on a path that's
either inside the jail or explicitly approved. Output is bounded — large files are
truncated and binary files are refused — so a huge or binary file can't blow up
the model's context or feed it garbage.
"""
from __future__ import annotations

from pathlib import Path

from ..registry import Context, Result
from ...security.gate import RiskClass

_MAX_BYTES = 200_000  # cap on what we feed back to the model


class FsRead:
    name = "fs.read"
    description = (
        "Read a UTF-8 text file and return its contents. Argument: path (absolute "
        "or relative to the project directory). Read-only. Large files are "
        "truncated; binary files are refused."
    )
    args_schema = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "File to read."}},
        "required": ["path"],
        "additionalProperties": False,
    }
    risk = RiskClass.SAFE
    provider = "builtin"

    def execute(self, args: dict, ctx: Context) -> Result:
        raw = str(args.get("path") or "").strip()
        if not raw:
            return Result(False, "fs.read needs a 'path' argument.")
        base = Path(ctx.allowed_dirs[0]) if ctx.allowed_dirs else Path.cwd()
        target = Path(raw)
        if not target.is_absolute():
            target = base / target
        try:
            target = target.resolve()
            if not target.exists():
                return Result(False, f"No such file: {raw}")
            if target.is_dir():
                return Result(False, f"{raw} is a directory, not a file (use fs.list).")
            data = target.read_bytes()
        except PermissionError:
            return Result(False, f"Permission denied: {raw}")
        except Exception as exc:  # noqa: BLE001 - contained; the loop observes it
            return Result(False, f"fs.read failed: {exc}")

        # A NUL byte in the head is the cheap, reliable "this is binary" tell.
        if b"\x00" in data[:4096]:
            return Result(False, f"{raw} looks binary — refusing to read it as text.")

        truncated = len(data) > _MAX_BYTES
        text = data[:_MAX_BYTES].decode("utf-8", errors="replace")
        note = (f"\n\n[... truncated at {_MAX_BYTES} of {len(data)} bytes ...]"
                if truncated else "")
        return Result(
            True,
            f"{raw} ({len(data)} bytes):\n{text}{note}",
            {"path": str(target), "bytes": len(data), "truncated": truncated},
        )
