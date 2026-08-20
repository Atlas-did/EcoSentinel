"""Parse LLM responses into a JSON object, tolerating markdown fences."""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(content: str | None) -> dict[str, Any] | None:
    """Parse a model response into a dict, or return None when unparseable.

    Handles a leading/trailing ```markdown fence and a best-effort substring
    match for models that prepend prose before the JSON object.
    """
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    try:
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
    except Exception:
        return None

    return None


def provider_tag(api_base: str | None) -> str:
    """Tag an API base URL with a short provider label."""
    b = (api_base or "").lower()
    if "deepseek" in b:
        return "deepseek"
    if "openai" in b:
        return "openai"
    return "openai_compat"
