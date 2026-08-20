"""Command dispatcher for EnergySystemApp.

Handles AI command validation, rule-based actuation, and hardware command
dispatch with anti-jitter / rate-limiting guards.
"""

import logging
import time
from datetime import datetime
from typing import Any

from energy_system.core.command_policy import (
    REASON_NON_STRING,
    REASON_NOT_A_LIST,
    REASON_RELAY_RESERVED,
    REASON_TOO_MANY,
    CommandPolicy,
    validate_commands,
)
from energy_system.utils.helpers import pick

logger = logging.getLogger("CommandDispatcher")

# Legacy rejection reasons returned by validate_ai_commands for backward
# compatibility. New callers should use validate_commands() for the richer,
# machine-readable reason codes.
LEGACY_REASON_NOT_ALLOWED = "command_not_allowed"

# Rich reason codes that map 1:1 onto the legacy reasons.
_LEGACY_PASSTHROUGH = {
    REASON_NOT_A_LIST,
    REASON_TOO_MANY,
    REASON_NON_STRING,
    REASON_RELAY_RESERVED,
}


def _to_legacy_reason(reason: str) -> str:
    """Map a rich rejection reason to the legacy coarse reason string."""
    return reason if reason in _LEGACY_PASSTHROUGH else LEGACY_REASON_NOT_ALLOWED


def validate_ai_commands(
    commands: Any,
    max_cmds: int,
) -> tuple[list[str], list[str], list[str]]:
    """Validate AI-suggested commands against the safety allowlist.

    Deprecated compatibility entry point. It delegates to the authoritative
    :func:`energy_system.core.command_policy.validate_commands` and preserves the
    legacy string-list contract. New code should call ``validate_commands()``
    directly to obtain strongly-typed ``DeviceCommand`` objects and rich reasons.

    Returns:
        (accepted, rejected, reasons) tuple of strings.
        - Relay 1/2 are reserved for rule-based control — AI cannot touch them.
        - Relay 3/4, CURTAIN, and BUZZER are allowed.
    """
    result = validate_commands(commands, CommandPolicy(max_cmds_per_cycle=max_cmds))

    accepted = list(result.accepted_wire)
    rejected = [r.raw for r in result.rejected]
    reasons = sorted({_to_legacy_reason(r) for r in result.reasons})

    return accepted, rejected, reasons


class RuleActuationController:
    """Manages relay actuation with anti-jitter / rate-limiting guards.

    Only sends hardware commands when relay state actually changes.
    """

    def __init__(
        self,
        serial_bridge: Any,
        rule_controller: Any,
        actuate_min_interval_s: float = 2.0,
        illuminance_min: float = 300.0,
        run_label: str = "saving",
    ) -> None:
        self.serial_bridge = serial_bridge
        self.rule_controller = rule_controller
        self.actuate_min_interval_s = actuate_min_interval_s
        self.illuminance_min = illuminance_min
        self.run_label = run_label

        self._start_mono = time.monotonic()
        self._last_actuate_mono = 0.0
        self._last_relay1: int | None = None
        self._last_relay2: int | None = None

    def apply(self, sensor_data: dict) -> bool:
        """Evaluate rule-based control and dispatch relay commands if state changed.

        Returns:
            True if any command was sent.
        """
        now_mono = time.monotonic()
        if now_mono - self._last_actuate_mono < self.actuate_min_interval_s:
            return False

        temp_c = pick(sensor_data, ["temperature", "temp"])
        lux = pick(sensor_data, ["illuminance", "lux"])
        if not isinstance(temp_c, (int, float)):
            return False

        hour = datetime.now().hour
        elapsed_s = now_mono - self._start_mono

        action = self.rule_controller.compute_action(
            float(temp_c),
            0.0,
            int(hour),
            current_time_s=float(elapsed_s),
            indoor_lux=(float(lux) if isinstance(lux, (int, float)) else None),
        )
        relay1 = 1 if (action.power_ac > 0.0) else 0

        relay2 = 0
        if 9 <= hour < 18:
            if self.run_label == "baseline":
                relay2 = 1
            else:
                if isinstance(lux, (int, float)) and float(lux) < float(self.illuminance_min):
                    relay2 = 1

        bridge = self.serial_bridge
        if not bridge:
            return False

        changed = False
        if self._last_relay1 is None or relay1 != self._last_relay1:
            bridge.send_command(f"RELAY 1 {relay1}")
            self._last_relay1 = relay1
            changed = True

        if self._last_relay2 is None or relay2 != self._last_relay2:
            bridge.send_command(f"RELAY 2 {relay2}")
            self._last_relay2 = relay2
            changed = True

        if changed:
            self._last_actuate_mono = now_mono

        return changed
