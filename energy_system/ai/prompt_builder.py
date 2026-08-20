"""Prompt construction with a strict field whitelist.

Only the fields a control decision actually needs are allowed into the prompt;
API keys, filesystem paths, exception stacks and full history are never sent.
"""

from __future__ import annotations

import json
from typing import Any

# The whitelist is deliberately small. Do not add keys without a control reason.
ALLOWED_PROMPT_KEYS = frozenset({
    "temperature",
    "humidity",
    "illuminance",
    "indoor_lux",
    "eco2",
    "tvoc",
    "power_w",
    "energy_wh",
    "solar_power_w",
    "solar_energy_wh",
    "soc_percent",
    "comfort_score",
    "relays",
    "curtain_steps",
    "safe_mode",
    "safe_reason",
})


def sanitize_prompt_value(value: Any) -> Any:
    """Recursively reduce an arbitrary value to prompt-safe JSON primitives."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [sanitize_prompt_value(v) for v in value[:32]]
    if isinstance(value, tuple):
        return [sanitize_prompt_value(v) for v in list(value)[:32]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in list(value.items())[:32]:
            out[str(k)] = sanitize_prompt_value(v)
        return out
    return str(value)


def prompt_sensor_payload(sensor_data: dict[str, Any]) -> dict[str, Any]:
    """Project a sensor dict down to the whitelisted fields."""
    safe: dict[str, Any] = {}
    for key in ALLOWED_PROMPT_KEYS:
        if key in sensor_data:
            safe[key] = sanitize_prompt_value(sensor_data.get(key))
    return safe


def build_prompt(sensor_data: dict[str, Any]) -> str:
    """Build the user prompt from whitelisted sensor fields only."""
    safe_sensor_data = prompt_sensor_payload(sensor_data)
    return (
        "Current indoor environment data: "
        + json.dumps(safe_sensor_data, ensure_ascii=False)
        + "\nGoals: Maximize comfort while minimizing energy consumption.\n\n"
        + "Controls available:\n"
        + "- RELAY 1 (Air Conditioner)\n"
        + "- RELAY 2 (Living Room Lights)\n"
        + "- RELAY 3 (Ventilation/Fresh Air)\n"
        + "- CURTAIN (OPEN/CLOSE/STOP)\n\n"
        + "Return a JSON object with:\n"
        + "1. 'reasoning': concise explanation.\n"
        + "2. 'commands': a list of raw ESP32 commands to execute.\n"
        + 'Example: {"reasoning":"High CO2 detected.","commands":["RELAY 3 1"]}'
    )
