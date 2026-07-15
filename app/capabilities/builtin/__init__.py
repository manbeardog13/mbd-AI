"""Built-in capabilities — the first provider behind the registry.

`register_builtins(registry)` adds Nero's own capabilities. Phase 1 ships one:
`git.status` (read-only). More read-only capabilities land next, one PR each,
before anything with a MEDIUM+ risk class (ADR-0005 / DESIGN-phase1 §6).
"""
from __future__ import annotations

from ..registry import Registry
from .git_status import GitStatus
from ..integrations import register_integration_capabilities


def register_builtins(registry: Registry) -> None:
    """Register every built-in capability onto `registry`."""
    registry.register(GitStatus())
    register_integration_capabilities(registry)
