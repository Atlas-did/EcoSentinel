"""Edge runtime: the hardware-mode control loop.

Moved out of ``main.py`` so the loop can be imported without side effects and
the metric/decision/scheduling pieces are injected services that can be tested
in isolation. ``main.py`` re-exports this class for backward compatibility.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

from energy_system.application.decision import DecisionService
from energy_system.application.enrichment import TelemetryEnrichmentService
from energy_system.application.scheduler import Scheduler
from energy_system.core.command_dispatcher import RuleActuationController
from energy_system.core.controller import RuleBasedController
from energy_system.core.data_acquisition import DataAcquisition, no_data_heartbeat_fields
from energy_system.core.log_manager import LogManager
from energy_system.hardware.serial_bridge import SerialBridge
from energy_system.resilience.orchestrator import ResilienceOrchestrator
from energy_system.utils.file_io import append_jsonl
from energy_system.utils.logger import setup_logger

logger = setup_logger("Main")


class EnergySystemApp:
    """Orchestrates the hardware-mode control loop.

    Responsibilities (delegated):
        - Data acquisition   → DataAcquisition
        - Metric enrichment  → TelemetryEnrichmentService
        - AI decision        → DecisionService
        - Rule actuation     → RuleActuationController
        - Logging & summaries → LogManager
        - Self-healing       → ResilienceOrchestrator
    """

    def __init__(self, config, api_key: str | None = None):
        self.config = config
        self.use_hardware = bool(config.use_hardware)
        self.run_label = (config.run_label or "saving").strip() or "saving"
        self.enable_ai = bool(config.ai.enabled)
        self.ai_control_mode = (config.ai.control_mode or "suggest").lower()
        if self.ai_control_mode not in {"suggest", "execute"}:
            self.ai_control_mode = "suggest"

        # ── Hardware layer ─────────────────────────────────────────
        self.serial_bridge = None
        if self.use_hardware:
            self.serial_bridge = SerialBridge(
                port=config.serial.port,
                baudrate=int(config.serial.baudrate),
                timeout=float(config.serial.timeout_s),
            )
            if self.serial_bridge.connect():
                logger.info("Hardware initialization successful.")
            else:
                logger.warning(
                    "Hardware connection failed at startup; will keep retrying. "
                    "Make sure no other process is holding the COM port."
                )

        # ── Data acquisition ───────────────────────────────────────
        self.acquisition = DataAcquisition(
            use_hardware=self.use_hardware,
            serial_bridge=self.serial_bridge,
        )

        # ── AI Advisor ─────────────────────────────────────────────
        self.ai_advisor = None
        if self.enable_ai:
            try:
                from energy_system.algorithms.ai_advisor import AIAdvisor

                self.ai_advisor = AIAdvisor(api_key=(api_key or ""), ai_config=self.config.ai)
                if api_key:
                    logger.info(f"AI Advisor initialized (mode={self.ai_control_mode}).")
                else:
                    logger.warning(
                        "AI enabled but missing API key env: cloud calls disabled; "
                        "using local fallback only."
                    )
            except Exception as e:
                self.ai_advisor = None
                logger.error(f"AI Advisor unavailable, disabled: {e}")
        else:
            logger.info("AI disabled by config.")

        # ── Rule controller + actuation ────────────────────────────
        self.rule_controller = RuleBasedController(mode=self.run_label)
        self.actuation = RuleActuationController(
            serial_bridge=self.serial_bridge,
            rule_controller=self.rule_controller,
            actuate_min_interval_s=float(config.control.actuate_min_interval_s),
            illuminance_min=float(config.thresholds.illuminance_min),
            run_label=self.run_label,
        )

        # ── Metric enrichment + AI decision ────────────────────────
        self.enrichment = TelemetryEnrichmentService(
            battery_capacity_mah=float(os.getenv("BATTERY_CAPACITY_MAH", "10000") or 10000),
            battery_initial_soc=float(os.getenv("BATTERY_INITIAL_SOC", "80") or 80),
        )
        self.decision = DecisionService(
            self.ai_advisor,
            max_cmds_per_cycle=int(config.control.max_ai_cmds_per_cycle),
        )

        # ── Logging ────────────────────────────────────────────────
        self.log_mgr = LogManager(run_label=self.run_label)

        # ── Resilience / self-healing ──────────────────────────────
        self.safe_mode = False
        self.safe_reason: str | None = None
        self._last_good_sample_mono: float | None = None
        self._last_ai_exec_mono: float = 0.0
        self._last_no_data_log_mono: float = 0.0
        self.resilience = ResilienceOrchestrator(config=self.config)
        self._start_mono = time.monotonic()

        # ── Scheduler ──────────────────────────────────────────────
        self.scheduler = Scheduler()

        # running flag
        self.system_running = True

    # ── main loop ──────────────────────────────────────────────────
    def run(self):
        logger.info("System startup complete. Ready for real-time monitoring.")
        logger.info(f"Run label: {self.run_label} (log: {self.log_mgr.log_path})")
        next_tick = time.monotonic()

        try:
            while self.system_running:
                sensor_data = self.acquisition.read()

                if not sensor_data:
                    self._handle_no_data()
                    next_tick = self.scheduler.wait_until_next_tick(next_tick, 5.0)
                    continue

                self._last_good_sample_mono = time.monotonic()
                self.safe_mode = False
                self.safe_reason = None
                self.resilience.on_sample_ok()

                # Normalize timestamp
                sensor_data.setdefault("timestamp", datetime.now().isoformat())

                # Sync rule controller from hardware after restart
                self._sync_controller_state(sensor_data)

                # Compute metrics
                self.enrichment.enrich(sensor_data)

                # AI decision
                self._run_ai_cycle(sensor_data)

                # Rule-based actuation
                if (
                    self.use_hardware
                    and self.serial_bridge
                    and self.config.control.enable_rule_control
                    and not self.safe_mode
                ):
                    self.actuation.apply(sensor_data)

                # Log
                self._enrich_and_log(sensor_data)

                next_tick = self.scheduler.wait_until_next_tick(next_tick, 5.0)

        except KeyboardInterrupt:
            logger.info("Shutting down system...")
        finally:
            if self.serial_bridge:
                self.serial_bridge.close()

    # ── internal helpers ──────────────────────────────────────────
    def _handle_no_data(self):
        now_mono = time.monotonic()
        bridge_health = self.serial_bridge.get_health() if self.serial_bridge else None

        # Heartbeat logging
        if now_mono - self._last_no_data_log_mono >= 5.0:
            row = no_data_heartbeat_fields(
                safe_reason=self.safe_reason or "no_sample_yet",
                resilience=self.resilience,
                bridge_health=bridge_health,
            )
            append_jsonl(str(self.log_mgr.log_path), row)
            self._last_no_data_log_mono = now_mono

        # Stale detection → safe_mode + self-healing
        if self._last_good_sample_mono is not None:
            stale_s = now_mono - self._last_good_sample_mono
            if stale_s >= float(self.config.control.safe_mode_stale_s):
                self.safe_mode = True
                self.safe_reason = f"stale_data_{stale_s:.1f}s"
                self._trigger_self_healing(stale_s)

    def _trigger_self_healing(self, stale_s: float):
        bridge_health = self.serial_bridge.get_health() if self.serial_bridge else None
        actions, summary = self.resilience.plan_for_stale(stale_s=stale_s)

        for act in actions:
            executed = False
            result = None
            if self.use_hardware and self.serial_bridge and not act.requires_manual:
                try:
                    result = self.serial_bridge.send_command(act.command)
                    executed = True
                except Exception as e:
                    result = {"error": str(e)}
            event = self.resilience.record_action_result(act, executed=executed, result=result)
            if bridge_health is not None:
                event["bridge_health"] = bridge_health
            self.log_mgr.log_incident(event)

        # Compact state row
        now_mono = time.monotonic()
        if now_mono - self._last_no_data_log_mono >= 5.0:
            row = {
                "timestamp": datetime.now().isoformat(),
                "safe_mode": True,
                "safe_reason": self.safe_reason,
                "bridge_health": bridge_health,
                "resilience": {
                    **(summary or {}),
                    "last_action": self.resilience.last_action,
                    "last_action_reason": self.resilience.last_action_reason,
                },
            }
            append_jsonl(str(self.log_mgr.log_path), row)
            self._last_no_data_log_mono = now_mono

    def _sync_controller_state(self, sensor_data: dict):
        if self.use_hardware and isinstance(sensor_data.get("relays"), list):
            relays = sensor_data.get("relays") or []
            if len(relays) >= 1:
                relay1_on = bool(relays[0])
                if self.rule_controller.ac_running != relay1_on:
                    self.rule_controller.sync_from_hardware(
                        ac_running=relay1_on,
                        current_time_s=float(time.monotonic() - self._start_mono),
                    )

    def _run_ai_cycle(self, sensor_data: dict):
        result = self.decision.decide(sensor_data)
        if result is None:
            return

        logger.info(f"AI Reasoning: {result.reasoning}")
        result.apply_to(sensor_data)

        # Execute AI commands (only in execute mode, only if not in safe_mode)
        if self.ai_control_mode == "execute" and not self.safe_mode:
            now_mono = time.monotonic()
            if now_mono - self._last_ai_exec_mono < float(self.config.control.actuate_min_interval_s):
                sensor_data.setdefault("ai_reject_reasons", []).append("rate_limited")
            elif self.use_hardware and self.serial_bridge:
                for cmd in result.accepted_commands:
                    res = self.serial_bridge.send_command(cmd)
                    logger.info(f"HW Exec(AI): {cmd} -> {res}")
                self._last_ai_exec_mono = now_mono

    def _enrich_and_log(self, sensor_data: dict):
        if self.serial_bridge:
            sensor_data["bridge_health"] = self.serial_bridge.get_health()
        sensor_data["safe_mode"] = self.safe_mode
        sensor_data["safe_reason"] = self.safe_reason
        sensor_data["resilience"] = {
            "state": self.resilience.breaker_state,
            "incident_id": self.resilience.last_incident_id,
            "last_action": self.resilience.last_action,
            "last_action_reason": self.resilience.last_action_reason,
        }
        self.log_mgr.log_sample(sensor_data)
        self.log_mgr.update_daily_energy(sensor_data)
