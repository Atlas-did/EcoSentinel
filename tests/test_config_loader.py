import tempfile
import unittest
from pathlib import Path

from energy_system.config.config_loader import load_app_config
from energy_system.config.runtime_config import AppConfig


class TestConfigLoader(unittest.TestCase):
    def test_missing_file_uses_defaults_and_warns(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing_params.yaml"
            cfg, warnings = load_app_config(missing)

        self.assertIsInstance(cfg, AppConfig)
        self.assertTrue(any("Config file not found" in w for w in warnings))

    def test_trims_run_label(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "params.yaml"
            p.write_text(
                """
app:
  run_label: "  baseline  "
""".lstrip(),
                encoding="utf-8",
            )
            cfg, warnings = load_app_config(p)

        self.assertEqual(cfg.run_label, "baseline")
        self.assertEqual(warnings, [])

    def test_invalid_values_warn_and_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "params.yaml"
            p.write_text(
                """
serial:
  port: ""
  baudrate: 9999999
  timeout_s: -1
thresholds:
  illuminance_min: -10
ai:
  enabled: true
  control_mode: foo
control:
  actuate_min_interval_s: -2
  safe_mode_stale_s: -3
  max_ai_cmds_per_cycle: 999
""".lstrip(),
                encoding="utf-8",
            )
            cfg, warnings = load_app_config(p)

        self.assertEqual(cfg.serial.port, "COM3")
        self.assertEqual(cfg.serial.baudrate, 115200)
        self.assertEqual(cfg.serial.timeout_s, 2.0)
        self.assertEqual(cfg.thresholds.illuminance_min, 300.0)
        self.assertEqual(cfg.ai.enabled, True)
        self.assertEqual(cfg.ai.control_mode, "suggest")
        self.assertEqual(cfg.control.actuate_min_interval_s, 2.0)
        self.assertEqual(cfg.control.safe_mode_stale_s, 30.0)
        self.assertEqual(cfg.control.max_ai_cmds_per_cycle, 5)

        # spot-check warnings are present
        self.assertTrue(any("serial.port" in w for w in warnings))
        self.assertTrue(any("serial.baudrate" in w for w in warnings))
        self.assertTrue(any("serial.timeout_s" in w for w in warnings))
        self.assertTrue(any("thresholds.illuminance_min" in w for w in warnings))
        self.assertTrue(any("ai.control_mode" in w for w in warnings))
        self.assertTrue(any("control.actuate_min_interval_s" in w for w in warnings))
        self.assertTrue(any("control.safe_mode_stale_s" in w for w in warnings))
        self.assertTrue(any("control.max_ai_cmds_per_cycle" in w for w in warnings))

    def test_self_healing_all_fields_validation(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "params.yaml"
            p.write_text(
                """
self_healing:
  enabled: "yes"
  auto_i2c_recover: 1
  auto_reset: "no"
  action_cooldown_s: -5
  reset_cooldown_s: -10
  max_resets_per_hour: 999
  require_manual_for_actuator_cutoff: "true"
""".lstrip(),
                encoding="utf-8",
            )
            cfg, warnings = load_app_config(p)

        # all invalid -> fallback to defaults
        self.assertEqual(cfg.self_healing.enabled, True)
        self.assertEqual(cfg.self_healing.auto_i2c_recover, True)
        self.assertEqual(cfg.self_healing.auto_reset, True)
        self.assertEqual(cfg.self_healing.action_cooldown_s, 10.0)
        self.assertEqual(cfg.self_healing.reset_cooldown_s, 120.0)
        self.assertEqual(cfg.self_healing.max_resets_per_hour, 3)
        self.assertEqual(cfg.self_healing.require_manual_for_actuator_cutoff, True)

        # warning coverage
        self.assertTrue(any("self_healing.enabled" in w for w in warnings))
        self.assertTrue(any("self_healing.auto_i2c_recover" in w for w in warnings))
        self.assertTrue(any("self_healing.auto_reset" in w for w in warnings))
        self.assertTrue(any("self_healing.action_cooldown_s" in w for w in warnings))
        self.assertTrue(any("self_healing.reset_cooldown_s" in w for w in warnings))
        self.assertTrue(any("self_healing.max_resets_per_hour" in w for w in warnings))
        self.assertTrue(any("self_healing.require_manual_for_actuator_cutoff" in w for w in warnings))


    def test_cors_credentials_wildcard_conflict_is_resolved(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "params.yaml"
            p.write_text(
                """
api:
  cors_origins: ["*"]
  allow_credentials: true
""".lstrip(),
                encoding="utf-8",
            )
            cfg, warnings = load_app_config(p)

        # Credentials are forced off when a wildcard origin is present.
        self.assertFalse(cfg.api.allow_credentials)
        self.assertTrue(any("allow_credentials" in w for w in warnings))

    def test_api_defaults_are_local_dev_only(self):
        with tempfile.TemporaryDirectory() as td:
            cfg, _ = load_app_config(Path(td) / "missing.yaml")

        self.assertNotIn("*", cfg.api.cors_origins)
        self.assertFalse(cfg.api.allow_credentials)

    def test_reset_cooldown_raised_to_action_cooldown(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "params.yaml"
            p.write_text(
                """
self_healing:
  action_cooldown_s: 60
  reset_cooldown_s: 30
""".lstrip(),
                encoding="utf-8",
            )
            cfg, warnings = load_app_config(p)

        self.assertEqual(cfg.self_healing.reset_cooldown_s, 60.0)
        self.assertTrue(any("reset_cooldown_s" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
