"""Control decision layer: plans, compilation, and actuation.

This package splits "decide what to do" (a pure :class:`ControlPlan`) from "send
commands to a device" (:class:`ActuationService` + :class:`ActuatorTransport`).
The legacy :class:`RuleBasedController` remains importable from
``energy_system.core.controller`` until callers migrate.
"""

from energy_system.core.control.actuation import ActuationService
from energy_system.core.control.compiler import CommandCompiler
from energy_system.core.control.models import (
    ControlPlan,
    HvacAction,
    HvacMode,
    LightingAction,
)
from energy_system.core.control.transport import (
    ActuatorTransport,
    CommandResult,
    MockActuatorTransport,
    SerialActuatorTransport,
)

__all__ = [
    "ActuationService",
    "ActuatorTransport",
    "CommandCompiler",
    "CommandResult",
    "ControlPlan",
    "HvacAction",
    "HvacMode",
    "LightingAction",
    "MockActuatorTransport",
    "SerialActuatorTransport",
]
