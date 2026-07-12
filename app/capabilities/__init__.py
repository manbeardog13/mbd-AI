"""Capabilities: what Nero can *do*, discovered through one registry (ADR-0007).

The agent reasons about capabilities the registry lists at runtime — never a
hard-coded tool list. Built-ins, and later MCP servers and Skills, all register
here; every call is dispatched through `Registry.dispatch`, which routes it past
the security gate and records metrics. That single choke point is why no
provider — present or future — can bypass safety or observability.
"""
from .registry import Capability, Context, Registry, Result, METRICS

__all__ = ["Capability", "Context", "Registry", "Result", "METRICS"]
