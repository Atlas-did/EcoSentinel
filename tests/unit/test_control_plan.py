"""Unit tests for ControlPlan, CommandCompiler, and transport adapters."""

import unittest

from energy_system.core.control.actuation import ActuationService
from energy_system.core.control.compiler import CommandCompiler
from energy_system.core.control.models import (
    ControlPlan,
    HvacAction,
    HvacMode,
    LightingAction,
)
from energy_system.core.control.transport import MockActuatorTransport, SerialActuatorTransport
from energy_system.core.clock import FakeClock
from energy_system.core.models.commands import RelayCommand


def _plan(hvac_on: bool = False, lights_on: bool = False) -> ControlPlan:
    mode = HvacMode.COOLING if hvac_on else HvacMode.OFF
    return ControlPlan(
        policy_name="rule",
        hvac=HvacAction(mode=mode, power_w=500.0 if hvac_on else 0.0),
        lighting=LightingAction(relay_on=lights_on),
    )


class TestCommandCompiler(unittest.TestCase):
    def test_compiles_hvac_and_lighting(self):
        compiler = CommandCompiler()
        cmds = compiler.compile(_plan(hvac_on=True, lights_on=True))
        self.assertEqual(cmds, [
            RelayCommand(channel=1, state=True),
            RelayCommand(channel=2, state=True),
        ])

    def test_off_plan_compiles_both_off(self):
        cmds = CommandCompiler().compile(_plan())
        self.assertEqual(cmds, [
            RelayCommand(channel=1, state=False),
            RelayCommand(channel=2, state=False),
        ])


class TestActuationService(unittest.TestCase):
    def test_sends_only_changed_states(self):
        transport = MockActuatorTransport()
        svc = ActuationService(transport, min_interval_s=0.0, clock=FakeClock())

        svc.apply(_plan(hvac_on=True, lights_on=True))
        # Second identical plan: no change, nothing sent.
        svc.apply(_plan(hvac_on=True, lights_on=True))
        self.assertEqual(len(transport.sent), 2)  # only the first cycle's 2 commands

    def test_respects_min_interval(self):
        transport = MockActuatorTransport()
        clock = FakeClock()
        svc = ActuationService(transport, min_interval_s=5.0, clock=clock)

        svc.apply(_plan(hvac_on=True))
        self.assertEqual(len(transport.sent), 2)

        # A different plan within the interval is rate-limited.
        svc.apply(_plan(hvac_on=False))
        self.assertEqual(len(transport.sent), 2)

        clock.advance(6.0)
        svc.apply(_plan(hvac_on=False))
        # HVAC off + lighting off (already off) => only HVAC relay changes.
        self.assertEqual(len(transport.sent), 3)

    def test_failed_send_not_recorded_as_success(self):
        transport = MockActuatorTransport(fail=True)
        svc = ActuationService(transport, min_interval_s=0.0, clock=FakeClock())
        results = svc.apply(_plan(hvac_on=True))
        self.assertTrue(all(not r.ok for r in results))
        # Failed sends are not cached, so retrying re-sends.
        self.assertEqual(svc.last_states, {})


class TestSerialActuatorTransport(unittest.TestCase):
    def test_wraps_raw_bridge(self):
        class FakeBridge:
            def send_command(self, raw: str):
                return {"ok": True, "response": {"echo": raw}}

            def get_health(self):
                return {"connected": True}

        transport = SerialActuatorTransport(FakeBridge())
        result = transport.send(RelayCommand(channel=3, state=True))
        self.assertTrue(result.ok)
        self.assertEqual(result.command.to_wire(), "RELAY 3 1")


if __name__ == "__main__":
    unittest.main()
