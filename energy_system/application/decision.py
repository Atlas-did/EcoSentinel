"""AI decision service: turn advisor output into a validated DecisionResult.

The service only decides and validates; it never sends commands to hardware —
execution stays in the caller. It is invoked by ``application/ai_worker.py``
(off the control loop), and the loop applies the result via
``EnergySystemApp._apply_ai_advice`` only while it is still fresh.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from energy_system.core.command_dispatcher import validate_ai_commands


@dataclass(frozen=True)
class DecisionResult:
    reasoning: str | None = None
    commands: list[str] = field(default_factory=list)
    source: str | None = None
    candidate_id: str | None = None
    latency_ms: int | None = None
    score: float | None = None
    tuning_event: Any = None
    cloud_error: str | None = None
    accepted_commands: list[str] = field(default_factory=list)
    rejected_commands: list[str] = field(default_factory=list)
    reject_reasons: list[str] = field(default_factory=list)

    def apply_to(self, sensor_data: dict) -> dict:
        """Copy the ai_* fields onto the sensor dict (legacy wire shape)."""
        sensor_data["ai_reasoning"] = self.reasoning
        sensor_data["ai_commands"] = self.commands
        sensor_data["ai_source"] = self.source
        sensor_data["ai_candidate_id"] = self.candidate_id
        sensor_data["ai_latency_ms"] = self.latency_ms
        sensor_data["ai_score"] = self.score
        sensor_data["ai_tuning_event"] = self.tuning_event
        sensor_data["ai_cloud_error"] = self.cloud_error
        sensor_data["ai_accepted_commands"] = self.accepted_commands
        sensor_data["ai_rejected_commands"] = self.rejected_commands
        sensor_data["ai_reject_reasons"] = self.reject_reasons
        return sensor_data


class DecisionService:
    def __init__(self, ai_advisor, max_cmds_per_cycle: int) -> None:
        self.ai_advisor = ai_advisor
        self.max_cmds_per_cycle = int(max_cmds_per_cycle)

    def decide(self, sensor_data: dict) -> DecisionResult | None:
        """Run one advisory cycle; return None when no advisor is configured."""
        if not self.ai_advisor:
            return None

        ai_response = self.ai_advisor.get_action(sensor_data)
        accepted, rejected, reasons = validate_ai_commands(
            ai_response.get("commands"),
            max_cmds=self.max_cmds_per_cycle,
        )
        return DecisionResult(
            reasoning=ai_response.get("reasoning"),
            commands=ai_response.get("commands", []),
            source=ai_response.get("advisor_source"),
            candidate_id=ai_response.get("candidate_id"),
            latency_ms=ai_response.get("latency_ms"),
            score=ai_response.get("score"),
            tuning_event=ai_response.get("tuning_event"),
            cloud_error=ai_response.get("cloud_error"),
            accepted_commands=accepted,
            rejected_commands=rejected,
            reject_reasons=reasons,
        )
