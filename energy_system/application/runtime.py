"""Edge runtime: the hardware-mode control loop.

M4 起拆为三段职责：
- **装配**（composition root）→ ``application/wiring.py``
- **循环与用例** → 本模块（后续继续外移 ``loop.py`` / ``usecases.py``）
- 对外门面 → ``EnergySystemApp``（``main.py`` 仍 re-export 它，属性保持不变）

``main.py`` re-exports this class for backward compatibility.
"""

from __future__ import annotations

import time
from datetime import datetime

from energy_system.application.wiring import AI_ADVICE_MAX_AGE_S, build_services
from energy_system.core.data_acquisition import no_data_heartbeat_fields
from energy_system.utils.file_io import append_jsonl
from energy_system.utils.logger import setup_logger

logger = setup_logger("Main")

#: 兼容旧引用点（真正的定义在 wiring.py）
__all__ = ["AI_ADVICE_MAX_AGE_S", "EnergySystemApp"]


class EnergySystemApp:
    """Orchestrates the hardware-mode control loop.

    Responsibilities (delegated):
        - 装配              → application/wiring.py
        - Data acquisition   → DataAcquisition
        - Metric enrichment  → TelemetryEnrichmentService
        - AI decision        → DecisionService（经 AiWorker 异步）
        - Rule actuation     → RuleActuationController
        - Logging & summaries → LogManager
        - Self-healing       → ResilienceOrchestrator
    """

    def __init__(self, config, api_key: str | None = None):
        self.config = config
        services = build_services(config, api_key)

        # 公开属性保持与拆分前一致（main.py 再导出、测试直接改这些属性）
        self.use_hardware = services.use_hardware
        self.run_label = services.run_label
        self.enable_ai = services.enable_ai
        self.ai_control_mode = services.ai_control_mode

        self.serial_bridge = services.serial_bridge
        self.acquisition = services.acquisition
        self.ai_advisor = services.ai_advisor
        self.decision = services.decision
        self.ai_worker = services.ai_worker
        self.enrichment = services.enrichment
        self.log_mgr = services.log_mgr
        self.resilience = services.resilience
        self.rule_controller = services.rule_controller
        self.actuation = services.actuation
        self.scheduler = services.scheduler
        self._start_mono = services.start_mono

        # ── Resilience / self-healing 运行期状态 ───────────────────
        self.safe_mode = False
        self.safe_reason: str | None = None
        self._last_good_sample_mono: float | None = None
        self._last_ai_exec_mono: float = 0.0
        self._last_no_data_log_mono: float = 0.0

        # running flag
        self.system_running = True

        #: 循环周期（秒）。提成属性以便测试用短周期驱动（真实线程测试）与 M4 调整。
        self.loop_interval_s = 5.0

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
                    next_tick = self.scheduler.wait_until_next_tick(next_tick, self.loop_interval_s)
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

                # AI 决策：两步都**不阻塞主回路**
                #   1) 先把上一轮算完且仍未过期的建议落到本轮（可能没有）
                #   2) 再为本轮发起一次异步计算
                self._apply_ai_advice(sensor_data)
                self._request_ai_cycle(sensor_data)

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

                next_tick = self.scheduler.wait_until_next_tick(next_tick, self.loop_interval_s)

        except KeyboardInterrupt:
            logger.info("Shutting down system...")
        finally:
            self._shutdown_ai_worker()
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

    def _request_ai_cycle(self, sensor_data: dict):
        """把本轮的 AI 计算交给 worker（非阻塞）；结果由后续轮次的 poll 取回。"""
        if self.ai_worker is not None:
            self.ai_worker.submit(sensor_data)

    def _apply_ai_advice(self, sensor_data: dict):
        """取回已完成且未过期的 AI 建议并落地/执行；没有则什么都不做。

        过期建议由 AiWorker.poll 丢弃（按**请求时刻**计龄），因此这里拿到的
        一定在 max_age_s 之内 —— 不会用陈旧快照去驱动硬件。
        """
        if self.ai_worker is None:
            return
        advice = self.ai_worker.poll(time.monotonic())
        if advice is None:
            return

        result = advice.result
        logger.info(f"AI Reasoning: {result.reasoning} (age={advice.age_s(time.monotonic()):.1f}s)")
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

    def _shutdown_ai_worker(self):
        if self.ai_worker is not None:
            self.ai_worker.shutdown()

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
