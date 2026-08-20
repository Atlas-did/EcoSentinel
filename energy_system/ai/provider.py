"""Provider abstraction for the AI advisor.

Defines the narrow seam between the advisory service and a concrete LLM client
so the service can be tested with a fake provider and swapped without touching
decision logic.
"""

from __future__ import annotations

from typing import Protocol


class AIProvider(Protocol):
    """Minimal chat-completions seam.

    Returns the raw assistant text; parsing and validation are the caller's job.
    """

    def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> str: ...
