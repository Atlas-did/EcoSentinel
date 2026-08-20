"""Control-cycle composition: enrich a sample and produce a validated decision.

A thin orchestration seam so the full "sample → enrich → decide" path can be
exercised with a fake advisor and mock actuator, independent of hardware.
"""

from __future__ import annotations

from dataclasses import dataclass

from energy_system.application.decision import DecisionResult, DecisionService
from energy_system.application.enrichment import TelemetryEnrichmentService


@dataclass(frozen=True)
class CycleResult:
    sample: dict
    decision: DecisionResult | None


class ControlCycleService:
    def __init__(
        self,
        enrichment: TelemetryEnrichmentService,
        decision: DecisionService,
    ) -> None:
        self.enrichment = enrichment
        self.decision = decision

    def process(self, sample: dict) -> CycleResult:
        enriched = self.enrichment.enrich(sample)
        decision = self.decision.decide(enriched)
        return CycleResult(sample=enriched, decision=decision)
