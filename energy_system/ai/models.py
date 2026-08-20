"""Typed models for the AI advisor layer.

The legacy :class:`~energy_system.algorithms.ai_advisor.AIAdvisor` returns plain
dicts for backward compatibility; these models are the migration target so the
advisory result and the circuit-breaker state stop living in free-form dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

SCHEMA_VERSION = "1.0"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AIAdvisorSource(str, Enum):
    CLOUD = "cloud"
    CLOUD_FALLBACK = "cloud_fallback"
    LOCAL_FALLBACK = "local_fallback"
    DISABLED = "disabled"


@dataclass(frozen=True)
class AIRecommendation:
    """Structured output of one advisory cycle.

    ``requested_actions`` are still raw command strings at this layer; command
    parsing/validation happens later in the domain command pipeline, never here.
    """

    reasoning_summary: str = ""
    requested_actions: list[str] = field(default_factory=list)
    confidence: float | None = None
    source: str = AIAdvisorSource.DISABLED.value
    candidate_id: str | None = None
    latency_ms: int | None = None
    recommendation_id: str | None = None
    schema_version: str = SCHEMA_VERSION
    warnings: list[str] = field(default_factory=list)

    def to_legacy_dict(self) -> dict:
        """Map back to the legacy dict shape consumed by main.py."""
        return {
            "reasoning": self.reasoning_summary,
            "commands": list(self.requested_actions),
            "advisor_source": self.source,
            "candidate_id": self.candidate_id,
            "latency_ms": self.latency_ms,
            "score": self.confidence,
        }
