"""Concrete RuntimeService implementations for Nero's subsystems.

Each service adapts a Nero subsystem (Presence Director today, future
Memory Manager / Scheduler / Vision) to the RuntimeService contract.

Services live here — not in the subsystem packages themselves — so that:
    1. The subsystem packages (voice/, presence/) can be tested and used
       independently of the app lifecycle. Nothing in voice/ or presence/
       imports from app/.
    2. Adding a new service is a single-file change under this directory.
"""
from .presence_service import PresenceService

__all__ = ["PresenceService"]
