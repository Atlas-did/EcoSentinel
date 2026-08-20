"""Command safety policy: domain-range and permission validation.

Separates "what is syntactically a command" (:mod:`command_parser`) from "what is
allowed to execute". This is the single source of truth for the command allowlist,
so the API, AI advisor and serial bridge do not each reimplement their own rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from energy_system.core.command_parser import parse_command
from energy_system.core.errors import CommandValidationError
from energy_system.core.models.commands import (
    BuzzerCommand,
    CurtainCommand,
    DeviceCommand,
    RelayCommand,
)

# Domain-range / permission rejection reasons (policy layer).
REASON_NOT_A_LIST = "commands_not_list"
REASON_TOO_MANY = "too_many_commands"
REASON_NON_STRING = "non_string_command"
REASON_RELAY_CHANNEL_OUT_OF_RANGE = "relay_channel_out_of_range"
REASON_RELAY_STATE_INVALID = "relay_state_invalid"
REASON_RELAY_RESERVED = "relay1_2_reserved_for_rules"

# Rule-based control keeps exclusive ownership of relays 1 and 2.
DEFAULT_RELAY_CHANNELS = (1, 2, 3, 4)
DEFAULT_RESERVED_RELAY_CHANNELS = frozenset({1, 2})
DEFAULT_MAX_CMDS_PER_CYCLE = 5


@dataclass(frozen=True)
class RejectedCommand:
    """A sanitized record of a command that failed validation."""

    raw: str
    reason: str


@dataclass(frozen=True)
class CommandValidationResult:
    """Outcome of validating a batch of proposed commands."""

    accepted: tuple[DeviceCommand, ...] = ()
    rejected: tuple[RejectedCommand, ...] = ()
    reasons: tuple[str, ...] = ()
    rate_limited: bool = False

    @property
    def accepted_wire(self) -> tuple[str, ...]:
        """Accepted commands rendered back to wire strings (for logging/execution)."""
        return tuple(cmd.to_wire() for cmd in self.accepted)


@dataclass(frozen=True)
class CommandPolicy:
    """Safety rules applied to every proposed command."""

    max_cmds_per_cycle: int = DEFAULT_MAX_CMDS_PER_CYCLE
    relay_channels: tuple[int, ...] = DEFAULT_RELAY_CHANNELS
    reserved_relay_channels: frozenset[int] = field(
        default_factory=lambda: DEFAULT_RESERVED_RELAY_CHANNELS
    )

    def check(self, command: DeviceCommand) -> str | None:
        """Return a rejection reason for a parsed command, or ``None`` if allowed."""
        if isinstance(command, RelayCommand):
            if command.channel not in self.relay_channels:
                return REASON_RELAY_CHANNEL_OUT_OF_RANGE
            if command.channel in self.reserved_relay_channels:
                return REASON_RELAY_RESERVED
            # state is bool by construction; guard against future misuse.
            if not isinstance(command.state, bool):
                return REASON_RELAY_STATE_INVALID
            return None
        # CURTAIN and BUZZER are syntactically constrained already.
        return None


def validate_commands(raw_commands: Any, policy: CommandPolicy) -> CommandValidationResult:
    """Validate a batch of proposed commands against the policy.

    This is the authoritative entry point for command safety. It performs the
    four-step pipeline described in the refactor plan:
        1. parse external model output,
        2. syntax validation,
        3. domain-range validation,
        4. permission validation.
    """
    if not isinstance(raw_commands, list):
        return CommandValidationResult(
            rejected=(RejectedCommand(raw=str(raw_commands), reason=REASON_NOT_A_LIST),),
            reasons=(REASON_NOT_A_LIST,),
        )

    reasons: list[str] = []
    rate_limited = False
    limited: list[Any] = raw_commands

    if len(raw_commands) > policy.max_cmds_per_cycle:
        rate_limited = True
        reasons.append(REASON_TOO_MANY)
        limited = raw_commands[: policy.max_cmds_per_cycle]

    accepted: list[DeviceCommand] = []
    rejected: list[RejectedCommand] = []

    for item in limited:
        if not isinstance(item, str) or not item.strip():
            rejected.append(RejectedCommand(raw=str(item), reason=REASON_NON_STRING))
            reasons.append(REASON_NON_STRING)
            continue

        raw = item.strip()
        try:
            command = parse_command(raw)
        except CommandValidationError as e:
            reason = e.reason or REASON_RELAY_CHANNEL_OUT_OF_RANGE
            rejected.append(RejectedCommand(raw=raw, reason=reason))
            reasons.append(reason)
            continue

        reason = policy.check(command)
        if reason is None:
            accepted.append(command)
        else:
            rejected.append(RejectedCommand(raw=raw, reason=reason))
            reasons.append(reason)

    return CommandValidationResult(
        accepted=tuple(accepted),
        rejected=tuple(rejected),
        reasons=tuple(sorted(set(reasons))),
        rate_limited=rate_limited,
    )
