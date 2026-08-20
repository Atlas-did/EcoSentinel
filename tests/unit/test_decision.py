"""Unit tests for DecisionService (extracted AI decision seam)."""

import unittest

from energy_system.application.decision import DecisionService


class _FakeAdvisor:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_action(self, sensor_data):
        self.calls.append(dict(sensor_data))
        return self.response


class TestDecisionService(unittest.TestCase):
    def _svc(self, advisor, max_cmds=2):
        return DecisionService(advisor, max_cmds_per_cycle=max_cmds)

    def test_no_advisor_returns_none(self):
        svc = self._svc(None)
        self.assertIsNone(svc.decide({}))

    def test_splits_accepted_and_rejected_commands(self):
        advisor = _FakeAdvisor({
            "reasoning": "ventilate",
            "commands": ["RELAY 3 1", "RELAY 1 1"],  # relay 1 is reserved
            "advisor_source": "cloud",
            "latency_ms": 123,
        })
        result = self._svc(advisor).decide({"temperature": 25.0})

        self.assertEqual(result.accepted_commands, ["RELAY 3 1"])
        self.assertEqual(result.rejected_commands, ["RELAY 1 1"])
        self.assertEqual(result.reasoning, "ventilate")
        self.assertEqual(result.source, "cloud")
        self.assertEqual(result.latency_ms, 123)
        self.assertTrue(result.reject_reasons)

    def test_max_commands_enforced(self):
        advisor = _FakeAdvisor({
            "commands": ["RELAY 3 1", "CURTAIN OPEN", "BUZZER 1"],
        })
        result = self._svc(advisor, max_cmds=1).decide({})
        # The excess commands are dropped (rate-limited), not individually rejected.
        self.assertEqual(result.accepted_commands, ["RELAY 3 1"])
        self.assertEqual(result.rejected_commands, [])
        self.assertIn("too_many_commands", result.reject_reasons)

    def test_apply_to_writes_legacy_fields(self):
        advisor = _FakeAdvisor({
            "reasoning": "ok",
            "commands": ["RELAY 3 1"],
            "advisor_source": "local_fallback",
        })
        result = self._svc(advisor).decide({})
        sensor = {}
        out = result.apply_to(sensor)
        self.assertIs(out, sensor)
        self.assertEqual(sensor["ai_reasoning"], "ok")
        self.assertEqual(sensor["ai_commands"], ["RELAY 3 1"])
        self.assertEqual(sensor["ai_source"], "local_fallback")
        self.assertEqual(sensor["ai_accepted_commands"], ["RELAY 3 1"])


if __name__ == "__main__":
    unittest.main()
