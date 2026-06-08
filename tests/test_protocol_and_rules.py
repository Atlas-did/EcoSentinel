import unittest

from energy_system.core.command_dispatcher import validate_ai_commands
from energy_system.hardware.serial_bridge import parse_sensor_line
from energy_system.config import settings


def decide_light_relay(run_label: str, hour: int, lux: float | None) -> int:
    """二值灯光规则：baseline 白天开灯；saving 白天且照度不足才开灯。"""
    if not (9 <= hour < 18):
        return 0
    if run_label == "baseline":
        return 1
    if lux is None:
        return 0
    return 1 if float(lux) < settings.COMFORT_ILLUMINANCE_MIN else 0


class TestProtocolParsing(unittest.TestCase):
    def test_parse_valid_json(self):
        obj = parse_sensor_line('{"temperature":25.0,"humidity":50}')
        self.assertIsInstance(obj, dict)
        self.assertEqual(obj.get("temperature"), 25.0)

    def test_parse_empty(self):
        self.assertIsNone(parse_sensor_line(""))
        self.assertIsNone(parse_sensor_line("   "))

    def test_parse_error_token(self):
        self.assertIsNone(parse_sensor_line("DHT_NAN"))
        self.assertIsNone(parse_sensor_line("DHT_TIMEOUT"))

    def test_parse_non_json(self):
        self.assertIsNone(parse_sensor_line("ESP32 Ready"))
        self.assertIsNone(parse_sensor_line("{not json}"))


class TestRuleLightDecision(unittest.TestCase):
    def test_baseline_day_on(self):
        self.assertEqual(decide_light_relay("baseline", 10, lux=1000.0), 1)

    def test_saving_day_low_lux_on(self):
        self.assertEqual(decide_light_relay("saving", 10, lux=0.0), 1)
        self.assertEqual(decide_light_relay("saving", 10, lux=settings.COMFORT_ILLUMINANCE_MIN - 1), 1)

    def test_saving_day_high_lux_off(self):
        self.assertEqual(decide_light_relay("saving", 10, lux=settings.COMFORT_ILLUMINANCE_MIN), 0)
        self.assertEqual(decide_light_relay("saving", 10, lux=settings.COMFORT_ILLUMINANCE_MIN + 1), 0)

    def test_night_off(self):
        self.assertEqual(decide_light_relay("baseline", 2, lux=0.0), 0)
        self.assertEqual(decide_light_relay("saving", 23, lux=0.0), 0)


class TestAICommandValidation(unittest.TestCase):
    def test_invalid_relay_index_rejected(self):
        accepted, rejected, reasons = validate_ai_commands(["RELAY 5 1"], max_cmds=5)
        self.assertEqual(accepted, [])
        self.assertEqual(rejected, ["RELAY 5 1"])
        self.assertIn("command_not_allowed", reasons)


if __name__ == "__main__":
    unittest.main()
