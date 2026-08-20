"""Unit tests for the resilience models and pure rate-limit policies."""

import json
import unittest

from energy_system.resilience.models import (
    ActionStatus,
    RecoveryEvent,
    ResilienceAction,
    ResilienceActionName,
    ResilienceState,
)
from energy_system.resilience.policies import can_act, can_auto_reset, prune_reset_history


class TestResilienceEnums(unittest.TestCase):
    def test_state_equality_and_serialization(self):
        self.assertEqual(ResilienceState.OPEN, "OPEN")
        self.assertEqual(str(ResilienceState.OPEN), "OPEN")
        self.assertEqual(json.dumps({"s": ResilienceState.OPEN}), '{"s": "OPEN"}')

    def test_action_name_equality(self):
        self.assertEqual(ResilienceActionName.RESET, "RESET")
        self.assertIn(ResilienceActionName.I2C_RECOVER, ["I2C_RECOVER"])

    def test_action_id_is_unique(self):
        a1 = ResilienceAction(name=ResilienceActionName.RESET, command="RESET", action_id="inc-1:RESET:1")
        a2 = ResilienceAction(name=ResilienceActionName.RESET, command="RESET", action_id="inc-1:RESET:2")
        self.assertNotEqual(a1.action_id, a2.action_id)

    def test_recovery_event_to_dict(self):
        ev = RecoveryEvent(
            incident_id="inc-1",
            action=ResilienceActionName.RESET,
            status=ActionStatus.EXECUTED,
            executed=True,
            requires_manual=False,
            reason="stale_35.0s",
            result={"ok": True},
            resilience_state=ResilienceState.OPEN,
            timestamp="2026-08-20T08:00:00",
            action_id="inc-1:RESET:1",
        )
        d = ev.to_dict()
        self.assertEqual(d["action"], "RESET")
        self.assertEqual(d["resilience_state"], "OPEN")
        self.assertEqual(d["status"], "executed")
        self.assertTrue(d["executed"])


class TestPruneResetHistory(unittest.TestCase):
    def test_removes_old_entries(self):
        history = [100.0, 5000.0, 10000.0]
        # cutoff = 11000 - 3600 = 7400 → only 10000.0 survives
        self.assertEqual(prune_reset_history(history, now=11000.0, window_s=3600.0), [10000.0])


class TestCanAct(unittest.TestCase):
    def test_no_prior_action(self):
        self.assertTrue(can_act(None, 10.0, 0.0))

    def test_within_cooldown(self):
        self.assertFalse(can_act(0.0, 10.0, 5.0))

    def test_after_cooldown(self):
        self.assertTrue(can_act(0.0, 10.0, 10.0))


class TestCanAutoReset(unittest.TestCase):
    def test_disabled(self):
        ok, why = can_auto_reset(auto_reset=False, reset_history=[], max_resets_per_hour=3,
                                 last_action=None, last_action_ts=None, reset_cooldown_s=120.0, now=0.0)
        self.assertFalse(ok)
        self.assertEqual(why, "auto_reset_disabled")

    def test_rate_limited(self):
        ok, why = can_auto_reset(auto_reset=True, reset_history=[1.0, 2.0], max_resets_per_hour=2,
                                 last_action=None, last_action_ts=None, reset_cooldown_s=0.0, now=10.0)
        self.assertFalse(ok)
        self.assertEqual(why, "reset_rate_limit_manual_required")

    def test_reset_cooldown(self):
        ok, why = can_auto_reset(auto_reset=True, reset_history=[], max_resets_per_hour=3,
                                 last_action="RESET", last_action_ts=0.0, reset_cooldown_s=120.0, now=30.0)
        self.assertFalse(ok)
        self.assertEqual(why, "reset_cooldown")

    def test_allowed(self):
        ok, why = can_auto_reset(auto_reset=True, reset_history=[], max_resets_per_hour=3,
                                 last_action=None, last_action_ts=None, reset_cooldown_s=120.0, now=0.0)
        self.assertTrue(ok)
        self.assertIsNone(why)


if __name__ == "__main__":
    unittest.main()
