"""Unit tests for the command parser, policy, and validation pipeline."""

import unittest

from energy_system.core.command_parser import parse_command
from energy_system.core.command_policy import (
    REASON_NOT_A_LIST,
    REASON_RELAY_CHANNEL_OUT_OF_RANGE,
    REASON_RELAY_RESERVED,
    REASON_TOO_MANY,
    CommandPolicy,
    validate_commands,
)
from energy_system.core.errors import CommandValidationError
from energy_system.core.models.commands import (
    BuzzerCommand,
    CurtainAction,
    CurtainCommand,
    RelayCommand,
)


class TestCommandParser(unittest.TestCase):
    def test_parse_relay(self):
        self.assertEqual(parse_command("RELAY 3 1"), RelayCommand(channel=3, state=True))
        self.assertEqual(parse_command("relay 4 0"), RelayCommand(channel=4, state=False))

    def test_parse_curtain(self):
        self.assertEqual(parse_command("CURTAIN OPEN"), CurtainCommand(action=CurtainAction.OPEN))
        self.assertEqual(parse_command("curtain close"), CurtainCommand(action=CurtainAction.CLOSE))

    def test_parse_buzzer(self):
        self.assertEqual(parse_command("BUZZER 1"), BuzzerCommand(state=True))
        self.assertEqual(parse_command("BUZZER 0"), BuzzerCommand(state=False))

    def test_parse_rejects_malformed(self):
        for bad in ["RELAY 3", "RELAY x 1", "RELAY 3 2", "CURTAIN UP", "BUZZER 5", "FOO 1 1"]:
            with self.assertRaises(CommandValidationError):
                parse_command(bad)

    def test_parse_rejects_non_string(self):
        with self.assertRaises(CommandValidationError):
            parse_command(123)  # type: ignore[arg-type]


class TestCommandPolicy(unittest.TestCase):
    def test_relay_channel_out_of_range(self):
        policy = CommandPolicy()
        self.assertEqual(policy.check(RelayCommand(channel=5, state=True)),
                         REASON_RELAY_CHANNEL_OUT_OF_RANGE)
        self.assertEqual(policy.check(RelayCommand(channel=0, state=True)),
                         REASON_RELAY_CHANNEL_OUT_OF_RANGE)

    def test_reserved_relays_rejected(self):
        policy = CommandPolicy()
        self.assertEqual(policy.check(RelayCommand(channel=1, state=True)),
                         REASON_RELAY_RESERVED)
        self.assertEqual(policy.check(RelayCommand(channel=2, state=False)),
                         REASON_RELAY_RESERVED)

    def test_allowed_relays_and_others_pass(self):
        policy = CommandPolicy()
        self.assertIsNone(policy.check(RelayCommand(channel=3, state=True)))
        self.assertIsNone(policy.check(RelayCommand(channel=4, state=False)))
        self.assertIsNone(policy.check(CurtainCommand(action=CurtainAction.OPEN)))
        self.assertIsNone(policy.check(BuzzerCommand(state=True)))


class TestValidateCommands(unittest.TestCase):
    def test_non_list_input(self):
        result = validate_commands("RELAY 3 1", CommandPolicy())
        self.assertEqual(result.reasons, (REASON_NOT_A_LIST,))
        self.assertEqual(result.accepted, ())

    def test_too_many_commands_rate_limited(self):
        cmds = ["RELAY 3 1"] * 6
        result = validate_commands(cmds, CommandPolicy(max_cmds_per_cycle=5))
        self.assertTrue(result.rate_limited)
        self.assertIn(REASON_TOO_MANY, result.reasons)
        self.assertEqual(len(result.accepted), 5)

    def test_reserved_relay_rejected_with_reason(self):
        result = validate_commands(["RELAY 1 1"], CommandPolicy())
        self.assertEqual(result.accepted, ())
        self.assertEqual(result.rejected[0].reason, REASON_RELAY_RESERVED)

    def test_out_of_range_relay_rejected_with_reason(self):
        result = validate_commands(["RELAY 5 1"], CommandPolicy())
        self.assertEqual(result.accepted, ())
        self.assertEqual(result.rejected[0].reason, REASON_RELAY_CHANNEL_OUT_OF_RANGE)

    def test_mixed_batch_splits_accepted_and_rejected(self):
        result = validate_commands(
            ["RELAY 3 1", "RELAY 1 1", "CURTAIN OPEN", "GARBAGE"],
            CommandPolicy(),
        )
        self.assertEqual(result.accepted_wire, ("RELAY 3 1", "CURTAIN OPEN"))
        self.assertEqual([r.raw for r in result.rejected], ["RELAY 1 1", "GARBAGE"])


if __name__ == "__main__":
    unittest.main()
