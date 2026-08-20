"""Unit tests for the TelemetrySample normalization model."""

import unittest
from datetime import datetime

from energy_system.core.models.telemetry import SampleQuality, TelemetrySample


class TestTelemetrySample(unittest.TestCase):
    def test_maps_legacy_aliases(self):
        sample = TelemetrySample.from_dict({
            "temperature": 24.5,
            "humidity": 50.0,
            "illuminance": 300.0,
            "eco2": 600,
            "tvoc": 50,
        }, source="serial")
        self.assertEqual(sample.temperature_c, 24.5)
        self.assertEqual(sample.humidity_pct, 50.0)
        self.assertEqual(sample.illuminance_lux, 300.0)
        self.assertEqual(sample.eco2_ppm, 600.0)
        self.assertEqual(sample.tvoc_ppb, 50.0)

    def test_missing_fields_are_none_not_defaults(self):
        sample = TelemetrySample.from_dict({"eco2": 600})
        self.assertIsNone(sample.temperature_c)
        self.assertIsNone(sample.humidity_pct)
        self.assertEqual(sample.quality, SampleQuality.MISSING_FIELDS)

    def test_quality_ok_when_critical_present(self):
        sample = TelemetrySample.from_dict({"temperature": 24.0, "humidity": 50.0})
        self.assertEqual(sample.quality, SampleQuality.OK)

    def test_non_dict_is_invalid(self):
        sample = TelemetrySample.from_dict("garbage")  # type: ignore[arg-type]
        self.assertEqual(sample.quality, SampleQuality.INVALID)

    def test_relay_states_normalized_to_int(self):
        sample = TelemetrySample.from_dict({"relays": [1, 0, 1]})
        self.assertEqual(sample.relay_states, (1, 0, 1))

    def test_timestamp_parsed(self):
        sample = TelemetrySample.from_dict({"timestamp": "2026-01-01T08:00:00"})
        self.assertEqual(sample.timestamp, datetime(2026, 1, 1, 8, 0, 0))

    def test_roundtrip_to_dict(self):
        sample = TelemetrySample.from_dict({
            "temperature": 24.0, "humidity": 50.0, "source": "mock",
        })
        data = sample.to_dict()
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["temperature_c"], 24.0)
        self.assertEqual(data["quality"], "ok")

    def test_field_estimated_marks_non_numeric(self):
        sample = TelemetrySample.from_dict({"temperature": "warm", "humidity": 50.0})
        self.assertIsNone(sample.temperature_c)
        self.assertIn("temperature_c", sample.field_estimated)


if __name__ == "__main__":
    unittest.main()
