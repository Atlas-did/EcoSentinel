import unittest

from energy_system.config.runtime_config import AppConfig
from energy_system.resilience.orchestrator import ResilienceOrchestrator


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def advance(self, s: float):
        self.t += float(s)


class TestResilienceOrchestrator(unittest.TestCase):
    def test_no_actions_below_stale_trigger(self):
        cfg = AppConfig()
        clock = FakeClock()
        orch = ResilienceOrchestrator(config=cfg, time_fn=clock.now)

        actions, summary = orch.plan_for_stale(stale_s=float(cfg.control.safe_mode_stale_s) - 0.1)
        self.assertEqual(actions, [])
        self.assertEqual(summary.get("note"), "stale_below_trigger")

    def test_plans_i2c_and_reset_when_stale(self):
        cfg = AppConfig()
        clock = FakeClock()
        orch = ResilienceOrchestrator(config=cfg, time_fn=clock.now)

        # first call: stage 1 (I2C recover)
        actions, summary = orch.plan_for_stale(stale_s=float(cfg.control.safe_mode_stale_s) + 1.0)
        names = [a.name for a in actions]
        self.assertIn("I2C_RECOVER", names)
        self.assertNotIn("RESET", names)
        self.assertEqual(summary.get("resilience_state"), "OPEN")
        self.assertTrue(summary.get("incident_id"))

        # record I2C attempt
        i2c_action = [a for a in actions if a.name == "I2C_RECOVER"][0]
        orch.record_action_result(i2c_action, executed=True, result={"ok": True})

        # after cooldown: stage 2 (reset)
        clock.advance(float(cfg.self_healing.action_cooldown_s) + 0.1)
        actions2, _ = orch.plan_for_stale(stale_s=float(cfg.control.safe_mode_stale_s) + 5.0)
        names2 = [a.name for a in actions2]
        self.assertIn("RESET", names2)

    def test_reset_rate_limit_requires_manual(self):
        cfg = AppConfig()
        # tighten to make test simple
        cfg = cfg.__class__(
            use_hardware=cfg.use_hardware,
            run_label=cfg.run_label,
            serial=cfg.serial,
            ai=cfg.ai,
            thresholds=cfg.thresholds,
            control=cfg.control,
            self_healing=cfg.self_healing.__class__(
                enabled=True,
                auto_i2c_recover=True,
                auto_reset=True,
                action_cooldown_s=0.0,
                reset_cooldown_s=0.0,
                max_resets_per_hour=1,
                require_manual_for_actuator_cutoff=True,
            ),
        )

        clock = FakeClock()
        orch = ResilienceOrchestrator(config=cfg, time_fn=clock.now)

        # First stale -> would execute reset
        actions, _ = orch.plan_for_stale(stale_s=float(cfg.control.safe_mode_stale_s) + 10.0)
        i2c_action = [a for a in actions if a.name == "I2C_RECOVER"][0]
        orch.record_action_result(i2c_action, executed=True, result={"ok": True})
        clock.advance(0.01)

        actions_reset, _ = orch.plan_for_stale(stale_s=float(cfg.control.safe_mode_stale_s) + 11.0)
        reset_action = [a for a in actions_reset if a.name == "RESET"][0]
        orch.record_action_result(reset_action, executed=True, result={"ok": True})

        # Immediately stale again; rate-limited => manual reset required
        clock.advance(1.0)
        actions2, _ = orch.plan_for_stale(stale_s=float(cfg.control.safe_mode_stale_s) + 20.0)
        reset2 = [a for a in actions2 if a.name == "RESET"][0]
        self.assertTrue(reset2.requires_manual)
        self.assertEqual(reset2.reason, "reset_rate_limit_manual_required")

    def test_no_action_available_when_reset_in_cooldown_and_no_i2c(self):
        cfg = AppConfig()
        cfg = cfg.__class__(
            use_hardware=cfg.use_hardware,
            run_label=cfg.run_label,
            serial=cfg.serial,
            ai=cfg.ai,
            thresholds=cfg.thresholds,
            control=cfg.control,
            self_healing=cfg.self_healing.__class__(
                enabled=True,
                auto_i2c_recover=False,
                auto_reset=True,
                action_cooldown_s=0.0,
                reset_cooldown_s=9999.0,
                max_resets_per_hour=3,
                require_manual_for_actuator_cutoff=True,
            ),
        )

        clock = FakeClock()
        orch = ResilienceOrchestrator(config=cfg, time_fn=clock.now)

        # First stale -> reset can be planned and executed.
        actions1, _ = orch.plan_for_stale(stale_s=float(cfg.control.safe_mode_stale_s) + 5.0)
        reset1 = [a for a in actions1 if a.name == "RESET"][0]
        orch.record_action_result(reset1, executed=True, result={"ok": True})

        # During reset cooldown with no i2c path -> no action available.
        clock.advance(1.0)
        actions2, summary2 = orch.plan_for_stale(stale_s=float(cfg.control.safe_mode_stale_s) + 8.0)
        self.assertEqual(actions2, [])
        self.assertEqual(summary2.get("note"), "no_action_available")


if __name__ == "__main__":
    unittest.main()
