"""AIAdvisorService — a thin, testable facade over the AI building blocks.

Composes prompt construction, a pluggable :class:`AIProvider`, response parsing
and the local fallback. It intentionally does NOT own candidate-pool selection
or multi-layer cloud fallback; the legacy ``AIAdvisor`` still handles that and
will be migrated to this facade once behaviour parity is proven.
"""

from __future__ import annotations

import time
from typing import Any

from energy_system.ai.fallback_policy import local_fallback
from energy_system.ai.models import AIRecommendation
from energy_system.ai.prompt_builder import build_prompt
from energy_system.ai.provider import AIProvider
from energy_system.ai.response_parser import parse_json_object, provider_tag
from energy_system.config.runtime_config import AIConfig


class AIAdvisorService:
    def __init__(
        self,
        provider: AIProvider,
        cfg: AIConfig,
        *,
        hour_fn=None,
    ) -> None:
        self.provider = provider
        self.cfg = cfg
        # hour_fn injects the local hour for the fallback policy; defaults to
        # the wall clock and is overridden in tests.
        self._hour_fn = hour_fn or (lambda: time.localtime().tm_hour)

    def recommend(self, sensor_data: dict[str, Any]) -> AIRecommendation:
        t0 = time.monotonic()
        try:
            content = self.provider.complete(
                system="You are a smart home energy consultant.",
                user=build_prompt(sensor_data),
                temperature=float(self.cfg.candidates[0].temperature) if self.cfg.candidates else 0.2,
                max_tokens=int(self.cfg.candidates[0].max_tokens) if self.cfg.candidates else 512,
                model=self.cfg.model,
            )
        except Exception as exc:  # network / provider error → fallback
            return self._fallback(sensor_data, latency_ms=int((time.monotonic() - t0) * 1000), warning=str(exc))

        latency_ms = int((time.monotonic() - t0) * 1000)
        obj = parse_json_object(content)
        if obj is None:
            return self._fallback(sensor_data, latency_ms=latency_ms, warning="json_parse_failed")

        commands = obj.get("commands")
        if not isinstance(commands, list):
            commands = []
        confidence = obj.get("score") if isinstance(obj.get("score"), (int, float)) else None

        return AIRecommendation(
            reasoning_summary=obj.get("reasoning") or "",
            requested_actions=commands,
            confidence=confidence,
            source="cloud",
            candidate_id=None,
            latency_ms=latency_ms,
        )

    def _fallback(self, sensor_data: dict[str, Any], *, latency_ms: int, warning: str) -> AIRecommendation:
        if not self.cfg.enable_local_fallback:
            return AIRecommendation(
                reasoning_summary=f"AI disabled or failed: {warning}",
                source="disabled",
                latency_ms=latency_ms,
                warnings=[warning],
            )
        fb = local_fallback(
            sensor_data,
            enable_relay3=self.cfg.fallback_enable_relay3,
            enable_curtain=self.cfg.fallback_enable_curtain,
            hour=self._hour_fn(),
        )
        return AIRecommendation(
            reasoning_summary=fb["reasoning"],
            requested_actions=list(fb["commands"]),
            source="local_fallback",
            latency_ms=latency_ms,
            warnings=[warning],
        )
