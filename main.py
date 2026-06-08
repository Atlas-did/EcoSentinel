"""环境监测与 AI 节能调控系统 — 硬件模式主入口。

Usage:
    python main.py

This is the main entry point for hardware-connected operation.
For simulation-only comparison, see energy_system/simulation/compare.py.
"""

# ── stdlib imports ────────────────────────────────────────────────
import logging
import os
import time
from datetime import datetime
from pathlib import Path

# ── third-party imports ────────────────────────────────────────────
# (none required; pyserial is loaded lazily in serial_bridge)

# ── project imports ────────────────────────────────────────────────
from energy_system.algorithms.comfort_eval import evaluate_comfort
from energy_system.config.config_loader import load_app_config
from energy_system.core.command_dispatcher import RuleActuationController, validate_ai_commands
from energy_system.core.controller import RuleBasedController
from energy_system.core.data_acquisition import DataAcquisition, no_data_heartbeat_fields
from energy_system.core.log_manager import LogManager
from energy_system.hardware.serial_bridge import SerialBridge
from energy_system.power.energy_accounting import BatterySOC, EnergyAccumulator
from energy_system.resilience.orchestrator import ResilienceOrchestrator
from energy_system.utils.env_loader import load_dotenv_if_present
from energy_system.utils.file_io import append_jsonl
from energy_system.utils.helpers import pick
from energy_system.utils.logger import setup_logger

# ── module state ───────────────────────────────────────────────────
_INSTANCE_LOCK_FH = None
logger = setup_logger("Main")


# ── single-instance lock ───────────────────────────────────────────
def _acquire_single_instance_lock(
    lock_path: str = os.path.join("logs", "main.lock"),
) -> bool:
    """Best-effort single-instance lock (Windows-friendly).

    Prevents accidentally running multiple `main.py` processes which would
    contend for the COM port and cause PermissionError/ClearCommError.
    """
    global _INSTANCE_LOCK_FH
    try:
        from msvcrt import LK_NBLCK, locking  # type: ignore
    except Exception:
        return True  # Non-Windows or unavailable: skip

    try:
        p = Path(lock_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = open(p, "a+", encoding="utf-8")
        try:
            locking(fh.fileno(), LK_NBLCK, 1)
        except OSError:
            try:
                fh.seek(0)
                other = fh.read().strip()
            except Exception:
                other = ""
            try:
                fh.close()
            except Exception:
                pass
            logger.error(
                "Detected another running main.py instance; refusing to start. "
                f"If you are sure it's stale, delete {p} (content={other!r})."
            )
            return False

        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        _INSTANCE_LOCK_FH = fh
        return True
    except Exception:
        return True


# ── application class ───────────────────────────────────────────────
class EnergySystemApp:
    """Orchestrates the hardware-mode control loop.

    Responsibilities (delegated):
        - Data acquisition  → DataAcquisition
        - Command validation → validate_ai_commands()
        - Rule actuation     → RuleActuationController
        - Logging & summaries → LogManager
        - Self-healing       → ResilienceOrchestrator
        - AI advisor         → AIAdvisor (lazy)
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

        # ── Energy accounting ──────────────────────────────────────
        self.acc = EnergyAccumulator()
        self.solar_acc = EnergyAccumulator(
            pwr_mw_key="solar_pwr_mw",
            bus_v_key="solar_bus_v",
            current_ma_key="solar_current_ma",
        )
        self.battery_soc = BatterySOC(
            capacity_mah=float(os.getenv("BATTERY_CAPACITY_MAH", "10000") or 10000),
            initial_soc_percent=float(os.getenv("BATTERY_INITIAL_SOC", "80") or 80),
            current_key="solar_current_ma",
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
                    next_tick = self._sleep_until(next_tick, 5.0)
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
                self._compute_comfort(sensor_data)
                self._compute_energy(sensor_data)

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

                next_tick = self._sleep_until(next_tick, 5.0)

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

    def _compute_comfort(self, sensor_data: dict):
        temp_c = pick(sensor_data, ["temperature", "temp"], default=25.0)
        hum_pct = pick(sensor_data, ["humidity", "hum"], default=50.0)
        sensor_data["comfort_score"] = evaluate_comfort(temp_c, hum_pct)

    def _compute_energy(self, sensor_data: dict):
        stats = self.acc.update(sensor_data)
        if stats.power_w is not None:
            sensor_data["power_w"] = stats.power_w
        sensor_data["energy_wh"] = stats.energy_wh

        solar_stats = self.solar_acc.update(sensor_data)
        if solar_stats.power_w is not None:
            sensor_data["solar_power_w"] = solar_stats.power_w
        sensor_data["solar_energy_wh"] = solar_stats.energy_wh

        soc_stats = self.battery_soc.update_from_sample(sensor_data)
        sensor_data["soc_percent"] = soc_stats.soc_percent

    def _run_ai_cycle(self, sensor_data: dict):
        if not self.ai_advisor:
            return

        ai_response = self.ai_advisor.get_action(sensor_data)
        logger.info(f"AI Reasoning: {ai_response.get('reasoning')}")

        sensor_data["ai_reasoning"] = ai_response.get("reasoning")
        sensor_data["ai_commands"] = ai_response.get("commands", [])
        sensor_data["ai_source"] = ai_response.get("advisor_source")
        sensor_data["ai_candidate_id"] = ai_response.get("candidate_id")
        sensor_data["ai_latency_ms"] = ai_response.get("latency_ms")
        sensor_data["ai_score"] = ai_response.get("score")
        sensor_data["ai_tuning_event"] = ai_response.get("tuning_event")
        sensor_data["ai_cloud_error"] = ai_response.get("cloud_error")

        ai_accept, ai_reject, ai_reasons = validate_ai_commands(
            sensor_data.get("ai_commands"),
            max_cmds=int(self.config.control.max_ai_cmds_per_cycle),
        )
        sensor_data["ai_accepted_commands"] = ai_accept
        sensor_data["ai_rejected_commands"] = ai_reject
        sensor_data["ai_reject_reasons"] = ai_reasons

        if ai_reject and isinstance(ai_response, dict):
            ai_response["reject_reasons"] = ai_reasons

        # Execute AI commands (only in execute mode, only if not in safe_mode)
        if self.ai_control_mode == "execute" and not self.safe_mode:
            now_mono = time.monotonic()
            if now_mono - self._last_ai_exec_mono < float(self.config.control.actuate_min_interval_s):
                sensor_data.setdefault("ai_reject_reasons", []).append("rate_limited")
            elif self.use_hardware and self.serial_bridge:
                for cmd in ai_accept:
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

    @staticmethod
    def _sleep_until(next_tick: float, interval: float) -> float:
        """Sleep to maintain a fixed-interval loop cadence."""
        next_tick += interval
        sleep_t = next_tick - time.monotonic()
        if sleep_t > 0:
            time.sleep(sleep_t)
        else:
            logger.warning(f"Loop overrun by {-sleep_t:.1f}s")
        return next_tick


# ── entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    if not _acquire_single_instance_lock():
        raise SystemExit(3)

    cfg, warnings = load_app_config()
    for w in warnings:
        logger.warning(w)

    # Load .env files (including legacy ai_workspace/von.env)
    load_dotenv_if_present(".env", "ai_workspace/von.env")

    API_KEY = (
        os.getenv("DEEPSEEK_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("AI_API_KEY", "").strip()
        or None
    )

    if os.getenv("DEEPSEEK_API_KEY", "").strip():
        if "openai.com" in (cfg.ai.api_base or "") and (cfg.ai.model or "").startswith("gpt-"):
            logger.warning(
                "Detected DEEPSEEK_API_KEY but ai.api_base/model still look like OpenAI defaults. "
                "For DeepSeek, set ai.api_base=https://api.deepseek.com/v1 and "
                "ai.model=deepseek-chat (see params.yaml example)."
            )

    app = EnergySystemApp(config=cfg, api_key=API_KEY)
    app.run()
