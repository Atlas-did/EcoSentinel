"""Control-plan domain model.

A control strategy produces a :class:`ControlPlan` — a pure description of intent.
The plan is *not* wire output; :class:`CommandCompiler` later turns it into
validated device commands. This keeps decision-making (testable, deterministic)
separate from actuation (side-effectful).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class HvacMode(str, Enum):
    OFF = "off"
    COOLING = "cooling"
    HEATING = "heating"


@dataclass(frozen=True)
class HvacAction:
    mode: HvacMode = HvacMode.OFF
    power_w: float = 0.0
    target_temperature_c: float = 24.0


@dataclass(frozen=True)
class LightingAction:
    power_w: float = 0.0
    relay_on: bool = False


@dataclass(frozen=True)
class ControlPlan:
    """The outcome of one control-strategy evaluation."""

    policy_name: str = "rule"
    hvac: HvacAction = field(default_factory=HvacAction)
    lighting: LightingAction = field(default_factory=LightingAction)
    reason_codes: tuple[str, ...] = ()
    blocked_actions: tuple[str, ...] = ()
    requires_confirmation: bool = False
    generated_at: datetime | None = None

    @property
    def wants_hvac(self) -> bool:
        return self.hvac.mode is not HvacMode.OFF
