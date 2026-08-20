"""AI advisor layer: provider seam, prompt/response parsing, circuit breaker,
fallback policy, and a testable service facade."""

from energy_system.ai.circuit_breaker import CandidateStats, CircuitBreaker
from energy_system.ai.fallback_policy import local_fallback
from energy_system.ai.models import AIRecommendation, AIAdvisorSource, CircuitState
from energy_system.ai.prompt_builder import ALLOWED_PROMPT_KEYS, build_prompt
from energy_system.ai.provider import AIProvider
from energy_system.ai.response_parser import parse_json_object, provider_tag
from energy_system.ai.service import AIAdvisorService

__all__ = [
    "AIAdvisorService",
    "AIAdvisorSource",
    "AIProvider",
    "AIRecommendation",
    "ALLOWED_PROMPT_KEYS",
    "CandidateStats",
    "CircuitBreaker",
    "CircuitState",
    "build_prompt",
    "local_fallback",
    "parse_json_object",
    "provider_tag",
]
