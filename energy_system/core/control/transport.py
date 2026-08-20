"""Actuator transport boundary.

The decision layer depends on :class:`ActuatorTransport`, not on ``serial.Serial``
or any concrete device. Implementations send strongly-typed :class:`DeviceCommand`
objects and return a :class:`CommandResult`, so sending a command and observing
its outcome are explicit and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from energy_system.core.models.commands import DeviceCommand


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    command: DeviceCommand | None = None
    error: str | None = None
    response: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "command": self.command.to_wire() if self.command else None,
            "error": self.error,
            "response": self.response,
        }


class ActuatorTransport(Protocol):
    def send(self, command: DeviceCommand) -> CommandResult: ...
    def health(self) -> dict: ...


class MockActuatorTransport:
    """In-memory transport for tests and dry-runs; records every sent command."""

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.sent: list[DeviceCommand] = []

    def send(self, command: DeviceCommand) -> CommandResult:
        if self.fail:
            return CommandResult(ok=False, command=command, error="mock_failure")
        self.sent.append(command)
        return CommandResult(ok=True, command=command, response={"mock": True})

    def health(self) -> dict:
        return {"connected": True, "mock": True}


class SerialActuatorTransport:
    """Adapts an existing serial bridge (raw-string API) to the typed protocol."""

    def __init__(self, serial_bridge: Any):
        self.serial_bridge = serial_bridge

    def send(self, command: DeviceCommand) -> CommandResult:
        result = self.serial_bridge.send_command(command.to_wire())
        ok = bool(result.get("ok")) if isinstance(result, dict) else False
        error = result.get("error") if isinstance(result, dict) else None
        return CommandResult(ok=ok, command=command, error=error, response=result)

    def health(self) -> dict:
        get = getattr(self.serial_bridge, "get_health", None)
        return get() if callable(get) else {"connected": False}
