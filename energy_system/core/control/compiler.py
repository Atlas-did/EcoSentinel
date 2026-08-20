"""Compile a ControlPlan into validated device commands.

The compiler is the only place that maps control intent onto concrete channels.
The channel mapping is centralized here so changing wiring only happens once:

- HVAC  → RELAY 1
- Lights → RELAY 2
"""

from __future__ import annotations

from energy_system.core.control.models import ControlPlan, HvacMode
from energy_system.core.models.commands import DeviceCommand, RelayCommand

HVAC_RELAY_CHANNEL = 1
LIGHTING_RELAY_CHANNEL = 2


class CommandCompiler:
    """Turns a :class:`ControlPlan` into a list of device commands."""

    def compile(self, plan: ControlPlan) -> list[DeviceCommand]:
        commands: list[DeviceCommand] = [
            RelayCommand(
                channel=HVAC_RELAY_CHANNEL,
                state=plan.wants_hvac,
            ),
            RelayCommand(
                channel=LIGHTING_RELAY_CHANNEL,
                state=plan.lighting.relay_on,
            ),
        ]
        return commands


def hvac_relay_state(mode: HvacMode) -> bool:
    """Return the relay state for a given HVAC mode."""
    return mode is not HvacMode.OFF
