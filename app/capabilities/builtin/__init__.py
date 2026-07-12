"""Built-in capabilities — the first provider behind the registry.

`register_builtins(registry)` adds Nero's own capabilities. Read-only ones land
first, one PR each — `git.status`, `fs.read`, … — before anything with a MEDIUM+
risk class (ADR-0005 / DESIGN-phase1 §6). Adding one here is the whole change:
the agent loop reasons over the registry, so no loop code moves (ADR-0007).
"""
from __future__ import annotations

from ..registry import Registry
from .fs_read import FsRead
from .git_status import GitStatus


def register_builtins(registry: Registry) -> None:
    """Register every built-in capability onto `registry`."""
    registry.register(GitStatus())
    registry.register(FsRead())
