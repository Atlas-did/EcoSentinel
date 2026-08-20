"""Strongly-typed domain command model.

External input (AI model text, serial strings, API bodies) is first parsed into
these immutable value objects, then validated against :class:`CommandPolicy`,
and only then compiled to a wire string for the transport layer. No module should
parse command strings independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommandType(str, Enum):
    RELAY = "relay"
    CURTAIN = "curtain"
    BUZZER = "buzzer"


class CurtainAction(str, Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    STOP = "STOP"


@dataclass(frozen=True)
class RelayCommand:
    channel: int
    state: bool

    def to_wire(self) -> str:
        return f"RELAY {self.channel} {1 if self.state else 0}"


@dataclass(frozen=True)
class CurtainCommand:
    action: CurtainAction

    def to_wire(self) -> str:
        return f"CURTAIN {self.action.value}"


@dataclass(frozen=True)
class BuzzerCommand:
    state: bool

    def to_wire(self) -> str:
        return f"BUZZER {1 if self.state else 0}"


# Union of all device commands that may reach an actuator transport.
DeviceCommand = RelayCommand | CurtainCommand | BuzzerCommand
