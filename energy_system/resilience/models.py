"""Typed models for the resilience / self-healing layer.

State and action names become enums (str subclasses, so they compare equal to
their wire strings and serialise cleanly to JSON) to eliminate string-typo
drift between the orchestrator, the log and the API.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class _StrValue(str, Enum):
    """str enum whose str()/JSON value is the member value, not 'Name.member'."""

    def __str__(self) -> str:
        return self.value


class ResilienceState(_StrValue):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ResilienceActionName(_StrValue):
    I2C_RECOVER = "I2C_RECOVER"
    RESET = "RESET"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"


class ActionStatus(_StrValue):
    PLANNED = "planned"
    EXECUTED = "executed"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class ResilienceAction:
    """A planned recovery action. The orchestrator plans; the caller executes."""

    name: ResilienceActionName
    command: str
    requires_manual: bool = False
    reason: str | None = None
    # Idempotency key: unique per planned action so a single fault cycle can
    # never dispatch the same non-idempotent action twice.
    action_id: str | None = None


@dataclass(frozen=True)
class RecoveryEvent:
    """The audit record emitted after an action is attempted."""

    incident_id: str | None
    action: ResilienceActionName
    status: ActionStatus
    executed: bool
    requires_manual: bool
    reason: str | None
    result: object
    resilience_state: ResilienceState
    timestamp: str
    action_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "ts": self.timestamp,
            "incident_id": self.incident_id,
            "action": self.action,
            "status": self.status,
            "executed": bool(self.executed),
            "requires_manual": bool(self.requires_manual),
            "reason": self.reason,
            "result": self.result,
            "resilience_state": self.resilience_state,
            "action_id": self.action_id,
        }
