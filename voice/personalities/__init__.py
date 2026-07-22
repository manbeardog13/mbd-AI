"""voice.personalities — delivery interpretation (how a response is delivered).

The Performance Director decides *how* Nero delivers a response; it never decides
*what* is said (Brain), *who* says it (Voice Manager), or *whether* it may run
(the executive path). Pure, deterministic, output-only.
"""
from .performance_director import (
    CANONICAL_EFFECTS, CANONICAL_EMOTIONS, DeliveryPlan, PerformanceDirector, direct,
)

__all__ = [
    "PerformanceDirector", "DeliveryPlan", "direct",
    "CANONICAL_EMOTIONS", "CANONICAL_EFFECTS",
]
