"""Parse raw command strings into strongly-typed domain commands.

Parsing is strictly syntactic: it turns text into a :class:`DeviceCommand` and
raises :class:`CommandValidationError` (carrying a machine-readable ``reason``)
on malformed input. Domain-range and permission checks live in
:mod:`energy_system.core.command_policy`.
"""

from __future__ import annotations

from energy_system.core.errors import CommandValidationError
from energy_system.core.models.commands import (
    BuzzerCommand,
    CurtainAction,
    CurtainCommand,
    DeviceCommand,
    RelayCommand,
)

# Rejection reason codes emitted by the parser (syntax layer).
REASON_MALFORMED_RELAY = "malformed_relay_command"
REASON_UNKNOWN_CURTAIN_ACTION = "unknown_curtain_action"
REASON_MALFORMED_CURTAIN = "malformed_curtain_command"
REASON_MALFORMED_BUZZER = "malformed_buzzer_command"
REASON_UNKNOWN_COMMAND = "unknown_command"
REASON_EMPTY_COMMAND = "empty_command"
REASON_NON_STRING = "non_string_command"


def parse_command(text: str) -> DeviceCommand:
    """Parse a single wire-format command string into a domain command.

    Accepted forms (case-insensitive head, whitespace-separated):
        RELAY <channel> <0|1>
        CURTAIN <OPEN|CLOSE|STOP>
        BUZZER <0|1>

    Raises:
        CommandValidationError: if the string is not a well-formed command.
    """
    if not isinstance(text, str):
        raise CommandValidationError(
            f"command must be a string, got {type(text).__name__}",
            reason=REASON_NON_STRING, operation="parse_command", recoverable=True,
        )
    parts = text.strip().split()
    if not parts:
        raise CommandValidationError(
            "empty command", reason=REASON_EMPTY_COMMAND,
            operation="parse_command", recoverable=True,
        )

    head = parts[0].upper()

    if head == "RELAY":
        if len(parts) != 3 or not parts[1].isdigit() or parts[2] not in {"0", "1"}:
            raise CommandValidationError(
                f"malformed RELAY command: {text!r}",
                reason=REASON_MALFORMED_RELAY, operation="parse_command",
                recoverable=True,
            )
        return RelayCommand(channel=int(parts[1]), state=parts[2] == "1")

    if head == "CURTAIN":
        if len(parts) != 2:
            raise CommandValidationError(
                f"malformed CURTAIN command: {text!r}",
                reason=REASON_MALFORMED_CURTAIN, operation="parse_command",
                recoverable=True,
            )
        action = parts[1].upper()
        try:
            return CurtainCommand(action=CurtainAction(action))
        except ValueError:
            raise CommandValidationError(
                f"unknown CURTAIN action: {parts[1]!r}",
                reason=REASON_UNKNOWN_CURTAIN_ACTION, operation="parse_command",
                recoverable=True,
            ) from None

    if head == "BUZZER":
        if len(parts) != 2 or parts[1] not in {"0", "1"}:
            raise CommandValidationError(
                f"malformed BUZZER command: {text!r}",
                reason=REASON_MALFORMED_BUZZER, operation="parse_command",
                recoverable=True,
            )
        return BuzzerCommand(state=parts[1] == "1")

    raise CommandValidationError(
        f"unknown command: {head!r}", reason=REASON_UNKNOWN_COMMAND,
        operation="parse_command", recoverable=True,
    )
