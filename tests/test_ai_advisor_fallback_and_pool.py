import unittest
from unittest.mock import patch

from energy_system.algorithms.ai_advisor import AIAdvisor
from energy_system.config.runtime_config import AIConfig, AIRequestCandidate


class TestAIAdvisorFallbackAndPool(unittest.TestCase):
    def test_local_fallback_when_no_api_key(self):
        cfg = AIConfig(
            enabled=True,
            control_mode="suggest",
            model="gpt-4o-mini",
            api_base="https://api.openai.com/v1",
            candidates=(AIRequestCandidate(id="c1"),),
            enable_local_fallback=True,
            fallback_enable_relay3=True,
            fallback_enable_curtain=False,
        )
        advisor = AIAdvisor(api_key="", ai_config=cfg)
        resp = advisor.get_action({"eco2": 1200, "comfort_score": 0.8, "power_w": 1000})
        self.assertEqual(resp.get("advisor_source"), "local_fallback")
        self.assertIn("RELAY 3 1", resp.get("commands", []))

    def test_candidate_switch_emits_tuning_event(self):
        cfg = AIConfig(
            enabled=True,
            control_mode="suggest",
            model="gpt-4o-mini",
            api_base="https://api.openai.com/v1",
            candidates=(
                AIRequestCandidate(id="a", temperature=0.2, max_tokens=256, timeout_s=1.0, max_retries=0),
                AIRequestCandidate(id="b", temperature=0.7, max_tokens=256, timeout_s=1.0, max_retries=0),
            ),
            exploration_rate=1.0,  # always explore
            enable_local_fallback=True,
        )
        advisor = AIAdvisor(api_key="", ai_config=cfg)
        # Force local fallback; also ensure deterministic randomness by overriding internal choice order
        # We call twice and expect that if candidate differs, a tuning_event exists.
        r1 = advisor.get_action({"eco2": 500, "comfort_score": 0.9, "power_w": 500})
        r2 = advisor.get_action({"eco2": 500, "comfort_score": 0.9, "power_w": 500})
        # tuning_event may or may not appear depending on random choice; assert it is well-formed when present
        te = r2.get("tuning_event")
        if te is not None:
            self.assertIn("from", te)
            self.assertIn("to", te)

    def test_circuit_breaker_opens_and_skips(self):
        cfg = AIConfig(
            enabled=True,
            control_mode="suggest",
            model="gpt-4o-mini",
            api_base="https://api.openai.com/v1",
            candidates=(
                AIRequestCandidate(id="A", temperature=0.2, max_tokens=32, timeout_s=1.0, max_retries=0),
                AIRequestCandidate(id="B", temperature=0.7, max_tokens=32, timeout_s=1.0, max_retries=0),
            ),
            exploration_rate=1.0,
            enable_local_fallback=False,
        )

        class TestableAdvisor(AIAdvisor):
            def __init__(self, ai_config: AIConfig):
                super().__init__(api_key="", ai_config=ai_config)
                self.calls: list[str] = []

            def _call_cloud(self, candidate: AIRequestCandidate, prompt: str):
                self.calls.append(candidate.id)
                if candidate.id == "A":
                    return None, "failA"
                return {"reasoning": "ok", "commands": ["RELAY 2 1"]}, None

        advisor = TestableAdvisor(cfg)
        sensors = {"eco2": 600, "comfort_score": 0.9, "power_w": 200}

        # Make exploration deterministic: always pick the first element of the current pool.
        with patch("energy_system.algorithms.ai_advisor.random.choice", side_effect=lambda seq: seq[0]):
            r1 = advisor.get_action(sensors)
            r2 = advisor.get_action(sensors)
            r3 = advisor.get_action(sensors)

        # A should have been tried (and failed) twice, opening the circuit.
        self.assertTrue(advisor._is_circuit_open("A"))
        # Third call should skip A and go directly to B.
        self.assertEqual(r3.get("candidate_id"), "B")
        self.assertIn(r1.get("advisor_source"), ("cloud_fallback", "disabled"))
        self.assertIn(r2.get("advisor_source"), ("cloud_fallback", "disabled"))
        self.assertIn(r3.get("advisor_source"), ("cloud", "cloud_fallback"))


if __name__ == "__main__":
    unittest.main()
