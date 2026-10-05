"""主回路（M4）：节拍 + 每轮用例编排。

从 ``runtime.py.run()`` **逐字搬迁**（含日志文案、异常处理、tick 计算），
只把方法体换成 ``usecases.*(app, ...)`` 调用。时序语义未改 ——
``tests/unit/test_loop_latency_budget.py`` 的"12 轮 / 零 overrun"断言仍是守门人。
"""

from __future__ import annotations

import time
from datetime import datetime

from energy_system.application import usecases
from energy_system.utils.logger import setup_logger

logger = setup_logger("Main")


def run_loop(app) -> None:
    """跑主回路直到 ``app.system_running`` 变为 False（或 Ctrl-C）。"""
    logger.info("System startup complete. Ready for real-time monitoring.")
    logger.info(f"Run label: {app.run_label} (log: {app.log_mgr.log_path})")
    next_tick = time.monotonic()

    try:
        while app.system_running:
            sensor_data = app.acquisition.read()

            if not sensor_data:
                usecases.handle_no_data(app)
                next_tick = app.scheduler.wait_until_next_tick(next_tick, app.loop_interval_s)
                continue

            app._last_good_sample_mono = time.monotonic()
            app.safe_mode = False
            app.safe_reason = None
            app.resilience.on_sample_ok()

            # Normalize timestamp
            sensor_data.setdefault("timestamp", datetime.now().isoformat())

            # Sync rule controller from hardware after restart
            usecases.sync_controller_state(app, sensor_data)

            # Compute metrics
            app.enrichment.enrich(sensor_data)

            # AI 决策：两步都**不阻塞主回路**
            #   1) 先把上一轮算完且仍未过期的建议落到本轮（可能没有）
            #   2) 再为本轮发起一次异步计算
            usecases.apply_ai_advice(app, sensor_data)
            usecases.request_ai_cycle(app, sensor_data)

            # Rule-based actuation
            if (
                app.use_hardware
                and app.serial_bridge
                and app.config.control.enable_rule_control
                and not app.safe_mode
            ):
                app.actuation.apply(sensor_data)

            # Log
            usecases.enrich_and_log(app, sensor_data)

            next_tick = app.scheduler.wait_until_next_tick(next_tick, app.loop_interval_s)

    except KeyboardInterrupt:
        logger.info("Shutting down system...")
    finally:
        usecases.shutdown_ai_worker(app)
        if app.serial_bridge:
            app.serial_bridge.close()
