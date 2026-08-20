"""Unit tests for the extracted AI advisor building blocks."""

import unittest

from energy_system.ai.circuit_breaker import CircuitBreaker
from energy_system.ai.fallback_policy import local_fallback
from energy_system.ai.prompt_builder import build_prompt
from energy_system.ai.response_parser import parse_json_object, provider_tag
from energy_system.ai.service import AIAdvisorService
from energy_system.config.runtime_config import AIConfig


class _FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += float(s)


class TestResponseParser(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_json_object('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(parse_json_object('```json\n{"a": 1}\n```'), {"a": 1})

    def test_prose_prefix(self):
        self.assertEqual(parse_json_object('Here you go: {"a": 1}'), {"a": 1})

    def test_invalid(self):
        self.assertIsNone(parse_json_object("not json"))
        self.assertIsNone(parse_json_object(""))
        self.assertIsNone(parse_json_object(None))

    def test_non_dict_json(self):
        self.assertIsNone(parse_json_object("[1, 2, 3]"))

    def test_provider_tag(self):
        self.assertEqual(provider_tag("https://api.deepseek.com/v1"), "deepseek")
        self.assertEqual(provider_tag("https://api.openai.com/v1"), "openai")
        self.assertEqual(provider_tag("https://example.com"), "openai_compat")
        self.assertEqual(provider_tag(None), "openai_compat")


class TestPromptBuilder(unittest.TestCase):
    def test_whitelist_drops_secrets(self):
        prompt = build_prompt({
            "temperature": 25.0,
            "api_key": "sk-secret",
            "file_path": "/etc/passwd",
            "stack_trace": "Traceback (most recent call last): ...",
        })
        self.assertIn("temperature", prompt)
        self.assertNotIn("sk-secret", prompt)
        self.assertNotIn("/etc/passwd", prompt)
        self.assertNotIn("Traceback", prompt)

    def test_whitelist_keeps_control_fields(self):
        prompt = build_prompt({"temperature": 25.0, "eco2": 1200, "comfort_score": 0.8})
        self.assertIn("25.0", prompt)
        self.assertIn("1200", prompt)
        self.assertIn("0.8", prompt)


class TestFallbackPolicy(unittest.TestCase):
    def test_eco2_high_enables_ventilation(self):
        out = local_fallback({"eco2": 1200}, enable_relay3=True, enable_curtain=False, hour=12)
        self.assertIn("RELAY 3 1", out["commands"])

    def test_tvoc_high(self):
        out = local_fallback({"tvoc": 400}, enable_relay3=True, enable_curtain=False, hour=12)
        self.assertIn("RELAY 3 1", out["commands"])

    def test_curtain_close_hot_and_bright(self):
        out = local_fallback(
            {"temperature": 28.0, "illuminance": 900},
            enable_relay3=False, enable_curtain=True, hour=12,
        )
        self.assertIn("CURTAIN CLOSE", out["commands"])

    def test_curtain_open_when_dark(self):
        out = local_fallback(
            {"temperature": 22.0, "illuminance": 100},
            enable_relay3=False, enable_curtain=True, hour=12,
        )
        self.assertIn("CURTAIN OPEN", out["commands"])

    def test_night_no_curtain_action(self):
        out = local_fallback(
            {"temperature": 28.0, "illuminance": 900},
            enable_relay3=False, enable_curtain=True, hour=2,
        )
        self.assertEqual(out["commands"], [])


class TestCircuitBreaker(unittest.TestCase):
    def test_opens_after_threshold_and_half_opens(self):
        clock = _FakeClock()
        cb = CircuitBreaker(now_fn=clock, threshold=2)
        self.assertFalse(cb.is_open("a"))
        cb.record("a", ok=False)
        self.assertFalse(cb.is_open("a"))
        cb.record("a", ok=False)  # second consecutive failure opens circuit
        self.assertTrue(cb.is_open("a"))
        self.assertGreater(cb.seconds_until_closed("a"), 0)
        clock.advance(cb.seconds_until_closed("a") + 1.0)
        self.assertFalse(cb.is_open("a"))

    def test_success_resets(self):
        clock = _FakeClock()
        cb = CircuitBreaker(now_fn=clock, threshold=2)
        cb.record("a", ok=False)
        cb.record("a", ok=True)
        cb.record("a", ok=False)
        self.assertFalse(cb.is_open("a"))  # consecutive failure reset

    def test_ema_updated_only_with_score(self):
        cb = CircuitBreaker(now_fn=_FakeClock())
        cb.record("a", ok=True, score=0.5)
        cb.record("a", ok=True, score=0.9)
        st = cb.stats("a")
        self.assertAlmostEqual(st.ema_score, 0.2 * 0.9 + 0.8 * 0.5, places=6)


class _FixedProvider:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def complete(self, *, system, user, temperature, max_tokens, model):
        self.calls.append({"system": system, "user": user})
        if isinstance(self.content, Exception):
            raise self.content
        return self.content


class TestAIAdvisorService(unittest.TestCase):
    def _cfg(self, **kw):
        return AIConfig(enabled=True, control_mode="suggest", enable_local_fallback=True, **kw)

    def test_cloud_success(self):
        provider = _FixedProvider('{"reasoning": "ok", "commands": ["RELAY 3 1"]}')
        svc = AIAdvisorService(provider, self._cfg())
        rec = svc.recommend({"temperature": 25.0})
        self.assertEqual(rec.source, "cloud")
        self.assertEqual(rec.requested_actions, ["RELAY 3 1"])
        self.assertEqual(rec.reasoning_summary, "ok")

    def test_json_parse_failure_falls_back(self):
        provider = _FixedProvider("not json at all")
        svc = AIAdvisorService(provider, self._cfg(), hour_fn=lambda: 12)
        rec = svc.recommend({"eco2": 1200})
        self.assertEqual(rec.source, "local_fallback")
        self.assertIn("json_parse_failed", rec.warnings)

    def test_provider_exception_falls_back(self):
        provider = _FixedProvider(TimeoutError("boom"))
        svc = AIAdvisorService(provider, self._cfg(), hour_fn=lambda: 12)
        rec = svc.recommend({"eco2": 1200})
        self.assertEqual(rec.source, "local_fallback")

    def test_fallback_disabled_yields_disabled(self):
        cfg = AIConfig(enabled=True, control_mode="suggest", enable_local_fallback=False)
        provider = _FixedProvider(TimeoutError("boom"))
        svc = AIAdvisorService(provider, cfg)
        rec = svc.recommend({})
        self.assertEqual(rec.source, "disabled")
        self.assertEqual(rec.requested_actions, [])


if __name__ == "__main__":
    unittest.main()
