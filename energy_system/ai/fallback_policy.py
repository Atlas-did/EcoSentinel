"""Deterministic local fallback policy used when cloud AI is unavailable.

Pure functions only — no network, no randomness — so the fallback behaviour is
stable and testable in isolation.
"""

from __future__ import annotations

from typing import Any


def local_fallback(
    sensor_data: dict[str, Any],
    *,
    enable_relay3: bool,
    enable_curtain: bool,
    hour: int,
) -> dict[str, Any]:
    """Return a fallback recommendation as a legacy dict.

    ``hour`` is injected (rather than read from the wall clock) so tests can
    pin the daytime/night-time branches.
    """
    cmds: list[str] = []
    reasons: list[str] = []

    eco2 = sensor_data.get("eco2")
    tvoc = sensor_data.get("tvoc")
    temp = sensor_data.get("temperature")
    lux = sensor_data.get("illuminance")

    if enable_relay3:
        if isinstance(eco2, (int, float)) and float(eco2) >= 1000:
            cmds.append("RELAY 3 1")
            reasons.append("eco2_high")
        elif isinstance(tvoc, (int, float)) and float(tvoc) >= 300:
            cmds.append("RELAY 3 1")
            reasons.append("tvoc_high")
        elif isinstance(eco2, (int, float)) and float(eco2) <= 650:
            cmds.append("RELAY 3 0")
            reasons.append("eco2_normal")

    if enable_curtain:
        if isinstance(temp, (int, float)) and isinstance(lux, (int, float)):
            if 9 <= hour < 18 and float(temp) >= 27.5 and float(lux) >= 800:
                cmds.append("CURTAIN CLOSE")
                reasons.append("hot_and_bright")
            elif 9 <= hour < 18 and float(lux) <= 200:
                cmds.append("CURTAIN OPEN")
                reasons.append("too_dark")

    return {
        "reasoning": "local_fallback:" + ("/".join(reasons) if reasons else "no_action"),
        "commands": cmds,
    }
