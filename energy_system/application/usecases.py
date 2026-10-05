"""控制回路的用例（M4）：无数据/自愈/同步/AI 周期/落盘。

从 ``runtime.py`` 逐字搬迁而来，只把 ``self`` 换成显式的 ``app`` 参数：
- 这些用例只依赖 app 的**公开属性**（services、state、config），因此能被单独测试；
- ``runtime.py`` 只剩门面与装配接线，扇出从 15 降到 3～4。

注意：时序语义**未改**（`time.monotonic()` 的调用点、日志文案、速率限制判定都保持原样），
`tests/unit/test_loop_latency_budget.py` 的 12 轮 / 零 overrun 断言仍是这套语义的守门人。
"""

from __future__ import annotations

import time
from datetime import datetime

from energy_system.core.data_acquisition import no_data_heartbeat_fields
from energy_system.utils.file_io import append_jsonl
from energy_system.utils.logger import setup_logger

logger = setup_logger("Main")


def handle_no_data(app) -> None:
    """没有采样时的心跳日志 + 陈旧检测（触发安全模式与自愈）。"""
    now_mono = time.monotonic()
    bridge_health = app.serial_bridge.get_health() if app.serial_bridge else None

    # Heartbeat logging
    if now_mono - app._last_no_data_log_mono >= 5.0:
        row = no_data_heartbeat_fields(
            safe_reason=app.safe_reason or "no_sample_yet",
            resilience=app.resilience,
            bridge_health=bridge_health,
        )
        append_jsonl(str(app.log_mgr.log_path), row)
        app._last_no_data_log_mono = now_mono

    # Stale detection → safe_mode + self-healing
    if app._last_good_sample_mono is not None:
        stale_s = now_mono - app._last_good_sample_mono
        if stale_s >= float(app.config.control.safe_mode_stale_s):
            app.safe_mode = True
            app.safe_reason = f"stale_data_{stale_s:.1f}s"
            trigger_self_healing(app, stale_s)


def trigger_self_healing(app, stale_s: float) -> None:
    bridge_health = app.serial_bridge.get_health() if app.serial_bridge else None
    actions, summary = app.resilience.plan_for_stale(stale_s=stale_s)

    for act in actions:
        executed = False
        result = None
        if app.use_hardware and app.serial_bridge and not act.requires_manual:
            try:
                result = app.serial_bridge.send_command(act.command)
                executed = True
            except Exception as e:
                result = {"error": str(e)}
        event = app.resilience.record_action_result(act, executed=executed, result=result)
        if bridge_health is not None:
            event["bridge_health"] = bridge_health
        app.log_mgr.log_incident(event)

    # Compact state row
    now_mono = time.monotonic()
    if now_mono - app._last_no_data_log_mono >= 5.0:
        row = {
            "timestamp": datetime.now().isoformat(),
            "safe_mode": True,
            "safe_reason": app.safe_reason,
            "bridge_health": bridge_health,
            "resilience": {
                **(summary or {}),
                "last_action": app.resilience.last_action,
                "last_action_reason": app.resilience.last_action_reason,
            },
        }
        append_jsonl(str(app.log_mgr.log_path), row)
        app._last_no_data_log_mono = now_mono


def sync_controller_state(app, sensor_data: dict) -> None:
    """重启后按硬件实际状态同步规则控制器（避免与实际继电器状态打架）。"""
    if app.use_hardware and isinstance(sensor_data.get("relays"), list):
        relays = sensor_data.get("relays") or []
        if len(relays) >= 1:
            relay1_on = bool(relays[0])
            if app.rule_controller.ac_running != relay1_on:
                app.rule_controller.sync_from_hardware(
                    ac_running=relay1_on,
                    current_time_s=float(time.monotonic() - app._start_mono),
                )


def request_ai_cycle(app, sensor_data: dict) -> None:
    """把本轮的 AI 计算交给 worker（非阻塞）；结果由后续轮次的 poll 取回。"""
    if app.ai_worker is not None:
        app.ai_worker.submit(sensor_data)


def apply_ai_advice(app, sensor_data: dict) -> None:
    """取回已完成且未过期的 AI 建议并落地/执行；没有则什么都不做。

    过期建议由 AiWorker.poll 丢弃（按**请求时刻**计龄），因此这里拿到的
    一定在 max_age_s 之内 —— 不会用陈旧快照去驱动硬件。
    """
    if app.ai_worker is None:
        return
    advice = app.ai_worker.poll(time.monotonic())
    if advice is None:
        return

    result = advice.result
    logger.info(f"AI Reasoning: {result.reasoning} (age={advice.age_s(time.monotonic()):.1f}s)")
    result.apply_to(sensor_data)

    # Execute AI commands (only in execute mode, only if not in safe_mode)
    if app.ai_control_mode == "execute" and not app.safe_mode:
        now_mono = time.monotonic()
        if now_mono - app._last_ai_exec_mono < float(app.config.control.actuate_min_interval_s):
            sensor_data.setdefault("ai_reject_reasons", []).append("rate_limited")
        elif app.use_hardware and app.serial_bridge:
            for cmd in result.accepted_commands:
                res = app.serial_bridge.send_command(cmd)
                logger.info(f"HW Exec(AI): {cmd} -> {res}")
            app._last_ai_exec_mono = now_mono


def shutdown_ai_worker(app) -> None:
    if app.ai_worker is not None:
        app.ai_worker.shutdown()


def enrich_and_log(app, sensor_data: dict) -> None:
    """补齐诊断字段后落盘（样本 + 当日能耗汇总）。"""
    if app.serial_bridge:
        sensor_data["bridge_health"] = app.serial_bridge.get_health()
    sensor_data["safe_mode"] = app.safe_mode
    sensor_data["safe_reason"] = app.safe_reason
    sensor_data["resilience"] = {
        "state": app.resilience.breaker_state,
        "incident_id": app.resilience.last_incident_id,
        "last_action": app.resilience.last_action,
        "last_action_reason": app.resilience.last_action_reason,
    }
    app.log_mgr.log_sample(sensor_data)
    app.log_mgr.update_daily_energy(sensor_data)
