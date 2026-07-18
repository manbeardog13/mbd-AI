"""Runtime lifecycle for Nero subsystems.

Nero's subsystems (Voice Director, Presence Director, and future systems like
Memory Manager, Scheduler, Vision) share a common lifecycle pattern:

    - startup:  register with the LifecycleManager, start in a defined order
    - runtime:  independently observable via a health() method
    - shutdown: stop in reverse order, cleanly, no orphan tasks

This package provides the minimal glue that makes that pattern real:

    - ``RuntimeService``   — the abstract contract every subsystem follows
    - ``ServiceHealth``    — a small dataclass every subsystem returns from health()
    - ``LifecycleManager`` — orders + drives start/stop across services

Concrete services live in ``app/runtime/services/``. The manager itself has
no knowledge of what any specific service does; it just calls ``start`` /
``stop`` / ``health`` on whatever is registered.

Design principles:
    - Lightweight: this is the pattern, not a framework. If a "kernel" is
      ever needed, it grows from here without breaking anything.
    - Failure-isolated: a broken service must not take down other services
      or the HTTP stack.
    - Runtime-agnostic: services encapsulate their internals. The manager
      never touches Kokoro, pedalboard, PresenceRuntime — those live inside
      individual services.
"""
from .lifecycle import LifecycleManager
from .service import RuntimeService, ServiceHealth

__all__ = ["RuntimeService", "ServiceHealth", "LifecycleManager"]
